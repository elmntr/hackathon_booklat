import csv
import io
import numpy as np
import pytest
from fastapi.testclient import TestClient
from server.main import app, COLUMNS
from server.aligner import HeardWord


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('BOOKLAT_SKIP_MODEL', '1')
    monkeypatch.setenv('BOOKLAT_RESULTS_PATH', str(tmp_path / 'results.csv'))
    with TestClient(app) as c:
        yield c


def body(**changes):
    result = dict(session_id='session-1', learner='Mina', passage_id='en-g3-1',
                  marks=[dict(status='correct', repeats=0)] * 48,
                  first_t=1, last_t=31, teacher_edited=False, save=False)
    result.update(changes)
    return result


def test_health_passages(client):
    assert client.get('/api/health').json() == dict(status='ok', model='small', loaded=False, error=None, network_needed=False)
    assert [p['word_count'] for p in client.get('/api/passages').json()] == [48, 44]


@pytest.mark.parametrize('changes', [dict(marks=[]), dict(marks=[dict(status='bad', repeats=0)]*48),
                                    dict(learner='  '), dict(learner='a'*61), dict(passage_id='bad'),
                                    dict(marks=[dict(status='correct', repeats=-1)]*48),
                                    dict(marks=[dict(status='correct', repeats=1.5)]*48),
                                    dict(first_t=100, last_t=1)])
def test_validation(client, changes):
    response = client.post('/api/score', json=body(**changes))
    assert response.status_code == 422 and response.json()['detail']


def test_save_replace_and_injection(client):
    assert client.post('/api/score', json=body(save=True)).json()['saved']
    assert client.post('/api/score', json=body(save=True, learner='=cmd')).json()['saved']
    rows = list(csv.DictReader(io.StringIO(client.get('/api/export.csv').text)))
    assert len(rows) == 1 and rows[0]['learner'] == "'=cmd"
    assert list(rows[0]) == COLUMNS
    assert rows[0]['wpm'] == '96'


def test_formula_session_id_replaces(client):
    for _ in range(2):
        assert client.post('/api/score', json=body(save=True, session_id='=one')).status_code == 200
    assert len(client.get('/api/results').json()) == 1


def test_empty_export_and_order(client):
    assert client.get('/api/results').json() == []
    assert next(csv.reader(io.StringIO(client.get('/api/export.csv').text))) == COLUMNS
    assert len(client.get('/api/export.csv').text.splitlines()) == 1
    for i in range(22):
        client.post('/api/score', json=body(save=True, session_id=str(i)))
    rows = client.get('/api/results').json()
    assert len(rows) == 20 and rows[0]['session_id'] == '21' and rows[-1]['session_id'] == '2'


def test_unknown_passage_and_missing_model(client):
    for passage in ['unknown', 'en-g3-1']:
        with client.websocket_connect('/ws/read?passage_id=' + passage) as ws:
            assert ws.receive_json()['type'] == 'error'


def test_full_socket_pipeline(client):
    class Fake:
        loaded = True
        def transcribe(self, audio, language, start):
            assert language == 'en'
            return [HeardWord('Mina', start, start+.5), HeardWord('has', start+.5, start+1)]
    app.state.transcriber = Fake()
    with client.websocket_connect('/ws/read?passage_id=en-g3-1') as ws:
        ws.send_bytes(np.zeros(16000, dtype='<i2').tobytes())
        assert ws.receive_json()['type'] == 'ready'
        ws.send_bytes(np.full(4000, 1000, dtype='<i2').tobytes())
        ws.send_json(dict(type='stop'))
        update = ws.receive_json()
        assert update['type'] == 'update' and update['pointer'] == 2
        done = ws.receive_json()
        assert done['type'] == 'done' and done['marks'][0]['status'] == 'correct'
        assert done['marks'][2]['status'] == 'not_reached' and done['first_t'] == 1


def test_worker_failure_does_not_hang(client):
    class Fake:
        loaded = True
        def transcribe(self, *args):
            raise RuntimeError('test failure')
    app.state.transcriber = Fake()
    with client.websocket_connect('/ws/read?passage_id=en-g3-1') as ws:
        ws.send_bytes(np.zeros(16000, dtype='<i2').tobytes())
        assert ws.receive_json()['type'] == 'ready'
        ws.send_bytes(np.full(4000, 1000, dtype='<i2').tobytes())
        ws.send_json(dict(type='stop'))
        assert ws.receive_json()['type'] == 'error'


def test_debug_reports_audio_recognition_and_alignment(client):
    class Fake:
        loaded = True
        def transcribe(self, audio, language, start, diagnostics=None):
            if diagnostics is not None:
                diagnostics.extend([dict(text='Mina', t0=start, t1=start+.5, probability=.9, accepted=True),
                                    dict(text='noise', t0=start+.5, t1=start+.6, probability=.01, accepted=False)])
            return [HeardWord('Mina', start, start+.5)]
    app.state.transcriber = Fake()
    def reading(debug):
        events = []
        with client.websocket_connect('/ws/read?passage_id=en-g3-1&debug='+str(debug).lower()) as ws:
            ws.send_bytes(np.zeros(16000, dtype='<i2').tobytes())
            ws.send_bytes(np.full(4000, 1000, dtype='<i2').tobytes())
            ws.send_json(dict(type='stop'))
            while True:
                event = ws.receive_json()
                events.append(event)
                if event['type'] == 'done':
                    return events
    normal, debug = reading(False), reading(True)
    assert normal[-1] == debug[-1]
    assert not any(e['type'] == 'debug_audio' or 'debug' in e for e in normal)
    audio = [e for e in debug if e['type'] == 'debug_audio'][-1]
    assert audio['rms'] == 1000 and audio['threshold'] == 250 and audio['calibrated']
    diagnostic = next(e['debug'] for e in debug if 'debug' in e)
    assert diagnostic['duration_s'] == .25
    assert diagnostic['queue_ms'] >= 0 and diagnostic['processing_ms'] >= 0
    assert diagnostic['words'][1]['accepted'] is False
    assert diagnostic['decisions'][0]['expected'] == 'Mina'
    assert diagnostic['decisions'][0]['marks'][0]['status'] == 'correct'


def test_debug_serializes_real_recognizer_numpy_types(client):
    from types import SimpleNamespace
    from server.asr import Transcriber
    from server.config import load_config
    class Model:
        def transcribe(self, *args, **kwargs):
            return [SimpleNamespace(words=[SimpleNamespace(word=' Mina', start=np.float32(.1),
                         end=np.float32(.4), probability=np.float64(.9))])], None
    transcriber = Transcriber(load_config())
    transcriber.model = Model()
    transcriber.loaded = True
    app.state.transcriber = transcriber
    with client.websocket_connect('/ws/read?passage_id=en-g3-1&debug=true') as ws:
        ws.send_bytes(np.zeros(16000, dtype='<i2').tobytes())
        ws.send_bytes(np.full(4000, 1000, dtype='<i2').tobytes())
        ws.send_json(dict(type='stop'))
        updates = []
        while True:
            event = ws.receive_json()
            assert event['type'] != 'error', event
            if event['type'] == 'update':
                updates.append(event)
            if event['type'] == 'done':
                break
        assert updates[0]['debug']['words'][0]['accepted'] is True
        assert updates[0]['marks'][0]['status'] == 'correct'


def test_debug_reports_underlying_failure(client):
    class Fake:
        loaded = True
        def transcribe(self, *args, **kwargs):
            raise ValueError('recognizer test failure')
    app.state.transcriber = Fake()
    with client.websocket_connect('/ws/read?passage_id=en-g3-1&debug=true') as ws:
        ws.send_bytes(np.zeros(16000, dtype='<i2').tobytes())
        ws.send_bytes(np.full(4000, 1000, dtype='<i2').tobytes())
        ws.send_json(dict(type='stop'))
        while True:
            event = ws.receive_json()
            if event['type'] == 'error':
                assert event['diagnostic_error'] == dict(kind='ValueError', message='recognizer test failure')
                break
