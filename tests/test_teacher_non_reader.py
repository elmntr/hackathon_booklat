"""Teacher status is independent of automated word-reading scores."""
import csv
import io

from fastapi.testclient import TestClient

from server.main import app


def test_teacher_non_reader_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv('BOOKLAT_SKIP_MODEL', '1')
    monkeypatch.setenv('BOOKLAT_DB_PATH', str(tmp_path / 'readings.sqlite3'))
    monkeypatch.setenv('BOOKLAT_RESULTS_PATH', str(tmp_path / 'legacy.csv'))
    with TestClient(app) as client:
        payload = dict(session_id='zero-score', learner='Learner', passage_id='en-g3-1',
                       marks=[dict(status='substitution', repeats=0)] * 48,
                       first_t=0, last_t=30, engine='vosk', save=True)
        automatic = client.post('/api/score', json=payload).json()
        assert automatic['accuracy_pct'] == 0 and automatic['level'] == 'frustration'
        assert automatic['teacher_non_reader'] is False
        assert client.post('/api/score', json=dict(payload, teacher_non_reader='yes')).status_code == 422

        reviewed = client.post('/api/score', json=dict(payload, teacher_non_reader=True, teacher_edited=True)).json()
        assert reviewed['level'] == 'frustration' and reviewed['philiri_word_level'] == 'frustration'
        assert reviewed['teacher_non_reader'] is True and reviewed['overall_philiri_level'] is None
        assert client.get('/api/results').json()[0]['teacher_non_reader'] is True
        saved = client.get('/api/results/zero-score').json()
        assert saved['reading']['teacher_non_reader'] is True
        assert 'Teacher-confirmed Non-Reader</th><td>Yes' in client.get('/api/results/zero-score/report.html').text
        exported = next(csv.DictReader(io.StringIO(client.get('/api/export.csv').text)))
        assert exported['teacher_non_reader'] == 'True' and exported['level'] == 'frustration'

        cleared = client.post('/api/score', json=dict(payload, teacher_non_reader=False, teacher_edited=True)).json()
        assert cleared['teacher_non_reader'] is False
        assert client.get('/api/results').json()[0]['teacher_non_reader'] is False
