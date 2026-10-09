"""Resource selection and runtime failure must leave a usable CPU fallback."""
from copy import deepcopy
import sys
from types import SimpleNamespace

from server.asr import Transcriber
from server.config import load_config


def test_gpu_warmup_failure_falls_back_to_bounded_cpu(monkeypatch):
    calls = []
    class Model:
        def __init__(self, model, **kwargs):
            self.device = kwargs['device']
            calls.append(kwargs)
        def transcribe(self, *args, **kwargs):
            if self.device == 'cuda':
                raise RuntimeError('missing CUDA runtime')
            return [], None
    monkeypatch.setenv('BOOKLAT_DEVICE', 'auto')
    monkeypatch.setitem(sys.modules, 'ctranslate2', SimpleNamespace(get_cuda_device_count=lambda: 1))
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=Model))
    t = Transcriber(load_config())
    t.load()
    assert t.loaded and t.device == 'cpu' and t.gpu_error == 'missing CUDA runtime'
    assert [c['device'] for c in calls] == ['cuda', 'cpu']
    assert 1 <= calls[1]['cpu_threads'] <= 4
    assert all(c['local_files_only'] for c in calls)


def test_cpu_override_respects_precision_setting(monkeypatch):
    calls = []
    def model(name, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(transcribe=lambda *args, **kwargs: ([], None))
    def unexpected():
        raise AssertionError('CPU override must not probe CUDA')
    monkeypatch.setenv('BOOKLAT_DEVICE', 'cpu')
    monkeypatch.setitem(sys.modules, 'ctranslate2', SimpleNamespace(get_cuda_device_count=unexpected))
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=model))
    cfg = deepcopy(load_config())
    cfg['asr']['compute_type'] = 'float32'
    t = Transcriber(cfg)
    t.load()
    assert t.loaded and t.gpu_error is None
    assert calls[0]['compute_type'] == t.compute_type == 'float32'
