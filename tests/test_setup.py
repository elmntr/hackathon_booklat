"""Model cache reporting must use the same file filter as model loading."""
import sys
from types import SimpleNamespace

from scripts.download_model import main


def test_setup_reports_filtered_model_cache(monkeypatch, capsys):
    calls = []

    def whisper(model, **kwargs):
        calls.append(('load', model, kwargs))

    def download(model, **kwargs):
        calls.append(('cache', model, kwargs))
        return '/cached/small'

    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=whisper))
    monkeypatch.setitem(sys.modules, 'faster_whisper.utils', SimpleNamespace(download_model=download))
    monkeypatch.setenv('HF_HUB_OFFLINE', '1')
    main()
    assert calls == [('load', 'small', {'device': 'cpu', 'compute_type': 'int8'}),
                     ('cache', 'small', {'local_files_only': True})]
    assert 'Cached at: /cached/small' in capsys.readouterr().out
