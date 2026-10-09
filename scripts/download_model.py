"""Explicit, one-time online model setup. Runtime never downloads weights."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.config import load_config


def main() -> None:
    # Model fetching is the only application network use, and happens only in setup.
    os.environ.pop('HF_HUB_OFFLINE', None)
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model
    cfg = load_config()['asr']
    WhisperModel(cfg['model'], device='cpu', compute_type=cfg['compute_type'])
    cached = download_model(cfg['model'], local_files_only=True)
    print(f"Model: {cfg['model']}\nCached at: {cached}")


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit(f'Model setup failed: {exc}\nCheck your internet connection and rerun ./scripts/setup.sh.')
