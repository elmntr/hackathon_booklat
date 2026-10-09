"""Streaming hypotheses must be revisable without corrupting final scoring."""
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from server.config import load_config
from server.main import app
from server.streaming import StreamingAlignment, VoskModels
from scripts.download_vosk import extract_model


def result(text, start=0):
    return dict(text=text, result=[dict(word=w, start=start+i*.3, end=start+(i+1)*.3, conf=.9)
                                   for i, w in enumerate(text.split())])


def test_partial_revisions_do_not_count_as_repeats_or_commit_errors():
    session = StreamingAlignment('Mina has a garden', load_config())
    first = session.update(dict(partial='Mina had'), False, 1)
    assert first['marks'][1]['status'] == 'substitution' and first['provisional'] == [0, 1]
    assert session.update(dict(partial='Mina had'), False, 1.1) is None
    corrected = session.update(dict(partial='Mina has'), False, 1.2)
    assert corrected['marks'][1]['status'] == 'correct'
    shorter = session.update(dict(partial='Mina'), False, 1.3)
    assert shorter['marks'][1]['status'] == 'not_reached'
    assert all(m.status == 'not_reached' for m in session.committed.marks)
    final = session.update(result('Mina has'), True, 1.5)
    assert final['provisional'] == []
    assert all(m['repeats'] == 0 and not m['self_corrected'] for m in final['marks'])
    assert session.committed.last_t == .6
    # FinalResult after an endpoint must not replay that endpoint.
    session.update(result(''), True, 2)
    assert session.committed.p == 2


def test_new_phrase_preview_preserves_confirmed_words_and_real_repeat():
    session = StreamingAlignment('Mina has a garden', load_config())
    session.update(result('Mina'), True, 1)
    for text in ['Mina', 'Mina has']:
        preview = session.update(dict(partial=text), False, 2)
        assert preview['marks'][0]['repeats'] == 1
    assert session.committed.marks[0].repeats == 0
    final = session.update(result('Mina has', 1), True, 2)
    assert final['marks'][0]['repeats'] == 1
    assert session.committed.p == 2


def test_partial_text_can_lead_partial_word_timestamps():
    session = StreamingAlignment('Si Ben ay may pusa', load_config())
    preview = session.update(dict(partial='Si Ben ay', partial_result=[dict(word='Si', start=0, end=.2, conf=.9)]), False, 1)
    assert preview['pointer'] == 3
    assert session.committed.first_t is None
    final = session.update(result('Si Ben ay'), True, 1)
    assert final['marks'][2]['t1'] == pytest.approx(.9)


class Recognizer:
    def __init__(self):
        self.frames = 0
        self.sizes = []
    def SetWords(self, value):
        pass
    def SetPartialWords(self, value):
        pass
    def AcceptWaveform(self, data):
        self.frames += 1
        self.sizes.append(len(data))
        return False
    def PartialResult(self):
        return json.dumps(dict(partial='Mina' if self.frames == 1 else 'Mina has'))
    def FinalResult(self):
        return json.dumps(result('Mina has'))


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('BOOKLAT_SKIP_MODEL', '1')
    monkeypatch.setenv('BOOKLAT_RESULTS_PATH', str(tmp_path/'results.csv'))
    with TestClient(app) as client:
        yield client


def test_streaming_socket_processes_quiet_frames_without_gate(client):
    recognizer = Recognizer()
    app.state.vosk.models['en'] = object()
    app.state.vosk.recognizer = lambda *args: recognizer
    with client.websocket_connect('/ws/read?passage_id=en-g3-1&engine=vosk&debug=true') as ws:
        assert ws.receive_json() == dict(type='ready', streaming=True)
        # Zero-volume PCM still reaches the recognizer; no calibration discard.
        ws.send_bytes(bytes(3200))
        while (event := ws.receive_json())['type'] != 'update':
            assert event['type'] == 'debug_audio' and event['threshold'] is None
        assert event['provisional'] == [0] and event['marks'][0]['status'] == 'correct'
        ws.send_bytes(bytes(3200))
        ws.send_json(dict(type='stop'))
        while (event := ws.receive_json())['type'] != 'done':
            assert event['type'] != 'error', event
        assert event['marks'][0]['repeats'] == 0 and event['marks'][1]['status'] == 'correct'
        assert event['last_t'] == .6
        assert recognizer.sizes == [3200, 3200]


def test_vosk_missing_model_and_unknown_engine_are_recoverable(client):
    for engine in ['vosk', 'unknown']:
        with client.websocket_connect('/ws/read?passage_id=en-g3-1&engine='+engine) as ws:
            assert ws.receive_json()['type'] == 'error'
    assert client.get('/api/engines').json()['vosk']['tl']['loaded'] is False


def test_streaming_worker_failure_is_reported_without_more_audio(client):
    class Broken(Recognizer):
        def AcceptWaveform(self, data):
            raise RuntimeError('stream failed')
    app.state.vosk.models['en'] = object()
    app.state.vosk.recognizer = lambda *args: Broken()
    with client.websocket_connect('/ws/read?passage_id=en-g3-1&engine=vosk&debug=true') as ws:
        assert ws.receive_json()['type'] == 'ready'
        ws.send_bytes(bytes(3200))
        while (event := ws.receive_json())['type'] != 'error':
            assert event['type'] == 'debug_audio'
        assert event['diagnostic_error']['message'] == 'stream failed'


def test_missing_vosk_paths_never_trigger_model_download(monkeypatch, tmp_path):
    import sys
    from types import SimpleNamespace
    import server.streaming as streaming
    monkeypatch.setattr(streaming, 'ROOT', tmp_path)
    def unexpected(**kwargs):
        pytest.fail('No local model path exists; constructor must not run')
    monkeypatch.setitem(sys.modules, 'vosk', SimpleNamespace(Model=unexpected, SetLogLevel=lambda _: None))
    bank = VoskModels()
    bank.load()
    assert bank.finished and len(bank.errors) == 2 and not bank.models


def test_model_archive_rejects_traversal(tmp_path):
    archive = tmp_path/'model.zip'
    with ZipFile(archive, 'w') as f:
        f.writestr('model/../../outside', 'bad')
    with pytest.raises(ValueError, match='Unexpected path'):
        extract_model(archive, tmp_path/'output', 'model')
    assert not (tmp_path/'outside').exists()
