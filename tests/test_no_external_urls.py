from pathlib import Path
import re


def test_no_external_urls():
    text = (Path(__file__).resolve().parents[1] / 'web/index.html').read_text()
    assert not re.search(r'https?://|wss?://', text)
    assert 'system-ui' in text
    assert 'prefers-reduced-motion' in text


def test_home(client=None):
    import os
    from fastapi.testclient import TestClient
    from server.main import app
    from unittest.mock import patch
    with patch.dict(os.environ, BOOKLAT_SKIP_MODEL='1'):
        with TestClient(app) as c:
            response = c.get('/')
            assert response.status_code == 200
            assert '<title>Booklat' in response.text
