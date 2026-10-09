"""Persistence, migration, backup, and local document import behavior."""
import io
import sqlite3
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from server.main import app
from server.imports import extract
from server.storage import Store


@pytest.fixture
def local_store(monkeypatch, tmp_path):
    monkeypatch.setenv('BOOKLAT_SKIP_MODEL', '1')
    monkeypatch.setenv('BOOKLAT_DB_PATH', str(tmp_path / 'booklat.sqlite3'))
    monkeypatch.setenv('BOOKLAT_RESULTS_PATH', str(tmp_path / 'results.csv'))
    return tmp_path


def test_library_and_word_history_survive_restart(local_store):
    with TestClient(app) as client:
        passage = client.post('/api/passages', json=dict(title='My notes', text='Mina has a garden', language='en')).json()
        marks = [dict(status='correct', repeats=0, heard=w, t0=i, t1=i+1) for i, w in enumerate(passage['tokens'])]
        payload = dict(session_id='offline-reading', learner='Test learner', passage_id=passage['id'], marks=marks,
                       first_t=0, last_t=4, engine='vosk', validation_mode='after_stop', save=True)
        assert client.post('/api/score', json=payload).status_code == 200
        payload['marks'][1]['status'] = 'substitution'
        payload['teacher_edited'] = True
        assert client.post('/api/score', json=payload).status_code == 200
        backup = client.get('/api/backup.sqlite3').content
    with TestClient(app) as client:
        assert passage['id'] in [p['id'] for p in client.get('/api/passages').json()]
        history = client.get('/api/results?q=notes').json()
        assert len(history) == 1 and history[0]['device'] == 'cpu'
        stored = client.get('/api/results/offline-reading').json()['reading']
        assert stored['validation_mode'] == 'after_stop' and stored['teacher_edited']
        assert stored['marks'][1]['status'] == 'substitution' and stored['marks'][1]['heard'] == 'has'
        assert client.get('/api/results?q=missing').json() == []
    restored = local_store / 'restored.sqlite3'
    restored.write_bytes(backup)
    with sqlite3.connect(restored) as db:
        assert db.execute('SELECT COUNT(*) FROM readings').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM passages').fetchone()[0] == 1


def test_csv_migration_is_once_and_preserves_original(local_store):
    source = local_store / 'results.csv'
    source.write_text('session_id,timestamp,learner,passage_id\nold,2026-01-01T12:00:00+08:00,Legacy,en-g3-1\n', encoding='utf-8')
    original = source.read_bytes()
    for _ in range(2):
        with TestClient(app) as client:
            rows = client.get('/api/results').json()
            assert len(rows) == 1 and rows[0]['learner'] == 'Legacy'
            assert client.get('/api/results/old').json()['reading'] is None
    assert source.read_bytes() == original


def zip_document(files):
    output = io.BytesIO()
    with ZipFile(output, 'w') as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return output.getvalue()


def test_docx_and_epub_extract_words_in_reading_order():
    docx = zip_document({'word/document.xml': '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Mina </w:t></w:r><w:r><w:t>has</w:t></w:r></w:p><w:p><w:r><w:t>a garden</w:t></w:r></w:p></w:body></w:document>'})
    assert extract(docx, 'notes.docx')['text'] == 'Mina has a garden'
    epub = zip_document({
        'META-INF/container.xml': '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="book/package.opf"/></rootfiles></container>',
        'book/package.opf': '<package xmlns="http://www.idpf.org/2007/opf"><manifest><item id="one" href="one.xhtml"/><item id="two" href="two.xhtml"/></manifest><spine><itemref idref="two"/><itemref idref="one"/></spine></package>',
        'book/one.xhtml': '<p>a garden</p><script>hidden text</script>',
        'book/two.xhtml': '<p>Mina has</p>',
    })
    assert extract(epub, 'book.epub')['text'] == 'Mina has a garden'


def pdf_bytes(text=True):
    writer = PdfWriter()
    page = writer.add_blank_page(300, 300)
    if text:
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 20 200 Td (Mina has a garden) Tj ET')
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        page[NameObject('/Contents')] = stream
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def test_pdf_and_text_import_and_errors(local_store):
    with TestClient(app) as client:
        for filename, data in [('notes.txt', b'Mina\n has  a garden'), ('reading.pdf', pdf_bytes())]:
            reply = client.post('/api/import', params={'filename': filename}, content=data)
            assert reply.status_code == 200, reply.text
            assert reply.json()['text'] == 'Mina has a garden'
        scanned = client.post('/api/import?filename=scan.pdf', content=pdf_bytes(False))
        assert scanned.status_code == 422 and 'OCR' in scanned.json()['detail']
        assert client.post('/api/import?filename=broken.docx', content=b'bad').status_code == 422
        assert client.post('/api/import?filename=program.exe', content=b'bad').status_code == 422
        assert client.post('/api/passages', json=dict(title='Too long', language='en', text='word ' * 2001)).status_code == 422
        assert client.get('/api/results/not-found').status_code == 404


def test_history_search_treats_percent_as_literal(tmp_path):
    store = Store(tmp_path / 'history.sqlite3')
    for idx, name in enumerate(['100% reader', 'Another reader']):
        store.save(dict(session_id=str(idx), timestamp='2026', learner=name, passage_title='Notes'), {})
    assert [row['learner'] for row in store.history('%')] == ['100% reader']
