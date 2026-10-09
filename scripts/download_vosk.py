"""Explicit online setup for the optional streaming trial; runtime stays offline."""
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.request import urlretrieve
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.streaming import MODEL_NAMES, ROOT


def extract_model(archive: Path, destination: Path, name: str) -> Path:
    """Reject paths outside the expected model directory before extracting."""
    with ZipFile(archive) as source:
        for entry in source.infolist():
            parts = Path(entry.filename).parts
            if not parts or parts[0] != name or '..' in parts or Path(entry.filename).is_absolute():
                raise ValueError('Unexpected path in model archive.')
        source.extractall(destination)
    folder = destination / name
    if not (folder / 'am' / 'final.mdl').is_file():
        raise ValueError('Downloaded archive is missing the acoustic model.')
    return folder


def main() -> None:
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    models = ROOT / 'models'
    models.mkdir(exist_ok=True)
    print('Filipino model license: CC-BY-NC-SA 4.0 (noncommercial). English: Apache 2.0.', flush=True)
    for language, name in MODEL_NAMES.items():
        target = models / name
        if target.is_dir():
            Model(model_path=str(target))
            print(f'{language}: existing model verified at {target}', flush=True)
            continue
        with tempfile.TemporaryDirectory(dir=models, prefix='.download-') as temporary:
            temp = Path(temporary)
            last_percent = -1
            def progress(blocks, size, total):
                nonlocal last_percent
                percent = min(100, blocks*size*100//total) if total > 0 else 0
                if percent >= last_percent + 5:
                    print(f'{name}: {percent}%', flush=True)
                    last_percent = percent
            print(f'Downloading {name}…', flush=True)
            urlretrieve(f'https://alphacephei.com/vosk/models/{name}.zip', temp/'model.zip', reporthook=progress)
            folder = extract_model(temp/'model.zip', temp, name)
            Model(model_path=str(folder))
            shutil.move(str(folder), str(target))
        print(f'{language}: ready at {target}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit(f'Vosk setup failed: {exc}\nRetry ./scripts/setup_vosk.sh while online.')
