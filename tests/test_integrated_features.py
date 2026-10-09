"""Frontend-facing APIs: saved voice, rubric exports, book sections and resumed sockets."""
import csv
import io
import sqlite3
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient
from server.main import app
from server.aligner import HeardWord


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('BOOKLAT_SKIP_MODEL', '1')
    monkeypatch.setenv('BOOKLAT_DB_PATH', str(tmp_path / 'history.sqlite3'))
    monkeypatch.setenv('BOOKLAT_RESULTS_PATH', str(tmp_path / 'legacy.csv'))
    with TestClient(app) as c:
        yield c


def reading(client, **overrides):
    p = client.post('/api/passages', json=dict(title='A short passage', text='Mina has a garden', language='en')).json()
    body = dict(session_id='integrated', learner='<script>learner</script>', passage_id=p['id'], engine='vosk',
                marks=[dict(status='correct', heard=w, repeats=0, t0=i*.25, t1=(i+1)*.25) for i,w in enumerate(p['tokens'])],
                first_t=0, last_t=1, save=True)
    body.update(overrides)
    return body


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(bytes(32000))
    return output.getvalue()


def test_voice_roundtrip_backup_ranges_and_deletion(client, tmp_path):
    body = reading(client)
    assert client.post('/api/score', json=body).status_code == 200
    audio = wav_bytes(); path = '/api/results/integrated/recordings/portion'
    response = client.put(path, content=audio, params={'offset': 1.5})
    assert response.status_code == 200 and response.json()['duration'] == 1
    assert client.put(path, content=audio, params={'offset': 1.5}).status_code == 200
    detail = client.get('/api/results/integrated').json()
    assert len(detail['recordings']) == 1 and detail['recordings'][0]['time_offset'] == 1.5
    assert client.get('/api/results').json()[0]['has_recording']
    assert client.get(path).content == audio
    partial = client.get(path, headers={'Range': 'bytes=12-31'})
    assert partial.status_code == 206 and partial.content == audio[12:32]
    assert client.get(path, headers={'Range': 'bytes=-10'}).content == audio[-10:]
    assert client.get(path, headers={'Range': 'bytes=999999-'}).status_code == 416
    backup = tmp_path / 'backup.sqlite3'; backup.write_bytes(client.get('/api/backup.sqlite3').content)
    with sqlite3.connect(backup) as db:
        assert db.execute('SELECT wav FROM recordings').fetchone()[0] == audio
    assert client.delete('/api/results/integrated/recordings').status_code == 200
    assert client.get(path).status_code == 404
    assert client.get('/api/results/integrated').json()['reading']['marks'] == detail['reading']['marks']


def test_voice_rejects_invalid_wav_and_unsaved_sessions(client):
    assert client.put('/api/results/missing/recordings/portion', content=wav_bytes()).status_code == 404
    assert client.put('/api/results/missing/recordings/portion', content=b'not wav').status_code == 422


def test_grading_report_csv_and_validation(client):
    body = reading(client, comprehension_correct=3, comprehension_total=5, reviewed_miscues=1)
    result = client.post('/api/score', json=body).json()
    assert result['philiri_word_score_pct'] == 75 and result['philiri_word_level'] == 'frustration'
    assert result['comprehension_pct'] == 60 and result['comprehension_level'] == 'instructional'
    stored = client.get('/api/results/integrated').json()['reading']
    assert stored['grading']['rubric'] == client.get('/api/rubric').json()
    exported = next(csv.DictReader(io.StringIO(client.get('/api/export.csv').text)))
    assert exported['word_independent_criteria'] == '97–100%'
    assert exported['comprehension_instructional_criteria'] == '59–79%'
    assert exported['comprehension_correct'] == '3' and exported['philiri_word_level'] == 'frustration'
    report = client.get('/api/results/integrated/report.html').text
    assert '&lt;script&gt;learner&lt;/script&gt;' in report and '<script>learner' not in report
    assert '59–79%' in report and '75.0' in report
    for changes in [dict(comprehension_correct=6), dict(comprehension_total=None),
                    dict(marks=[dict(status='correct', t0=2, t1=1)]*4),
                    dict(marks=[dict(status='correct', t0=1)]*4)]:
        assert client.post('/api/score', json=dict(body, **changes)).status_code == 422
    body['marks'][3]['status'] = 'not_reached'
    result = client.post('/api/score', json=body).json()
    assert result['grading_status'] == 'incomplete_reading' and result['philiri_word_level'] is None


def test_book_sections_and_resume_socket(client):
    book = client.post('/api/books', json=dict(title='Book', text=' '.join(['word']*105), language='en', section_words=50)).json()
    assert [p['word_count'] for p in book['passages']] == [50,50,5]
    assert len({p['book_id'] for p in book['passages']}) == 1
    assert all(p['id'] in {q['id'] for q in client.get('/api/passages').json()} for p in book['passages'])
    p = client.post('/api/passages', json=dict(title='Resume', text='Mina has a garden', language='en')).json()
    class Fake:
        loaded=True
        def transcribe(self, audio, language, start):
            return [HeardWord('a', start, start+.25), HeardWord('garden', start+.25, start+.5)]
    app.state.transcriber=Fake()
    with client.websocket_connect('/ws/read?engine=whisper&passage_id='+p['id']+'&start_index=2') as ws:
        ws.send_bytes(bytes(32000));assert ws.receive_json()['type'] == 'ready'
        ws.send_bytes(np.full(4000,1000,dtype='<i2').tobytes());ws.send_json({'type':'stop'})
        update=ws.receive_json();done=ws.receive_json()
        assert update['final'] and update['pointer'] == 2
        assert len(done['marks']) == 2 and all(m['status']=='correct' for m in done['marks'])
    with client.websocket_connect('/ws/read?passage_id='+p['id']+'&start_index=4') as ws:
        assert ws.receive_json()['type'] == 'error'
