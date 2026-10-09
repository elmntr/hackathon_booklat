"""Local reading sessions, scoring, and atomic CSV persistence."""
import asyncio
from contextlib import asynccontextmanager, suppress
import csv
from dataclasses import asdict
from datetime import datetime
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from server.aligner import Aligner
from server.asr import Chunker, Transcriber
from server.config import load_config
from server.scorer import score
from server.streaming import VoskModels, read_stream

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ('session_id,timestamp,learner,passage_id,language,grade,words_attempted,words_total,'
           'reading_time_s,wpm,accuracy_pct,level,substitutions,omissions,repetitions,teacher_edited').split(',')
CSV_LOCK = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cfg = load_config()
    passages = json.loads((ROOT / 'data/passages.json').read_text(encoding='utf-8'))
    app.state.passages = {p['id']: dict(p, tokens=p['text'].split(), word_count=len(p['text'].split())) for p in passages}
    app.state.results_path = Path(os.environ.get('BOOKLAT_RESULTS_PATH', ROOT / 'data/results.csv'))
    app.state.transcriber = Transcriber(app.state.cfg)
    app.state.vosk = VoskModels()
    vosk_task = None
    task = None
    if os.environ.get('BOOKLAT_SKIP_MODEL') != '1':
        task = asyncio.create_task(asyncio.to_thread(app.state.transcriber.load))
        vosk_task = asyncio.create_task(asyncio.to_thread(app.state.vosk.load))
    yield
    if task:
        await task
    if vosk_task:
        await vosk_task


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get('/')
def index():
    return FileResponse(ROOT / 'web/index.html')


@app.get('/api/health')
def health():
    t = app.state.transcriber
    return dict(status='ok', model=app.state.cfg['asr']['model'], loaded=t.loaded,
                error=t.error, network_needed=False)


@app.get('/api/engines')
def engines():
    return dict(whisper=health(), vosk=app.state.vosk.status())


@app.get('/api/passages')
def passages():
    return list(app.state.passages.values())


class ScoreMark(BaseModel):
    status: Literal['not_reached', 'correct', 'substitution', 'omission']
    repeats: Annotated[int, Field(strict=True, ge=0, le=20)] = 0


class ScoreRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    session_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    learner: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    passage_id: str
    marks: list[ScoreMark]
    first_t: Annotated[float, Field(ge=0)] | None = None
    last_t: Annotated[float, Field(ge=0)] | None = None
    teacher_edited: bool = False
    save: bool = False

    @model_validator(mode='after')
    def validate_clock(self):
        if (self.first_t is None) != (self.last_t is None):
            raise ValueError('Both reading timestamps must be supplied together.')
        if self.first_t is not None and self.last_t < self.first_t:
            raise ValueError('End time must not precede start time.')
        return self


def read_rows() -> list[dict]:
    path = app.state.results_path
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as source:
        return list(csv.DictReader(source))


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def save_row(row: dict) -> None:
    """Replace an existing session without exposing a partially written file."""
    path = app.state.results_path
    safe = {k: safe_cell(v) for k, v in row.items()}
    with CSV_LOCK:
        rows = [r for r in read_rows() if r['session_id'] != safe['session_id']]
        rows.append(safe)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', newline='', encoding='utf-8',
                                             dir=path.parent, delete=False) as target:
                temporary = target.name
                writer = csv.DictWriter(target, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


@app.post('/api/score')
def score_reading(body: ScoreRequest):
    passage = app.state.passages.get(body.passage_id)
    if passage is None:
        raise HTTPException(422, 'Unknown passage. Choose a listed passage.')
    if len(body.marks) != passage['word_count']:
        raise HTTPException(422, f"Expected {passage['word_count']} word marks.")
    result = score([m.model_dump() for m in body.marks], body.first_t, body.last_t, app.state.cfg)
    if body.save:
        row = dict(session_id=body.session_id, timestamp=datetime.now().astimezone().isoformat(timespec='seconds'),
                   learner=body.learner, passage_id=passage['id'], language=passage['language'],
                   grade=passage['grade'], teacher_edited=body.teacher_edited)
        row.update({k: result[k] for k in COLUMNS if k in result})
        try:
            save_row(row)
        except OSError:
            raise HTTPException(500, 'Could not save the result. Check available disk space and folder permissions.')
    return dict(result, saved=body.save)


@app.get('/api/results')
def results():
    with CSV_LOCK:
        return read_rows()[-20:][::-1]


@app.get('/api/export.csv')
def export_csv():
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=COLUMNS)
    writer.writeheader()
    with CSV_LOCK:
        writer.writerows(read_rows())
    return Response(output.getvalue(), media_type='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="booklat-results.csv"'})


@app.websocket('/ws/read')
async def read(websocket: WebSocket, passage_id: str = '', debug: bool = False, engine: str = 'whisper'):
    await websocket.accept()
    passage = app.state.passages.get(passage_id)
    if not passage:
        await websocket.send_json(dict(type='error', message='Unknown passage. Choose a listed passage.'))
        await websocket.close()
        return
    if engine == 'vosk':
        await read_stream(websocket, passage, app.state.cfg, app.state.vosk, debug)
        return
    if engine != 'whisper':
        await websocket.send_json(dict(type='error', message='Unknown speech engine.'))
        await websocket.close()
        return
    transcriber = app.state.transcriber
    if not transcriber.loaded:
        await websocket.send_json(dict(type='error', message='Speech model is not ready. Run ./scripts/setup.sh once while online, then restart.'))
        await websocket.close()
        return
    aligner = Aligner(passage['text'], app.state.cfg)
    chunker = Chunker(app.state.cfg)
    # Bound queued audio so a slow CPU cannot accumulate unlimited microphone data.
    queue = asyncio.Queue(maxsize=32)
    failure: list[Exception] = []

    chunk_number = 0

    async def worker():
        nonlocal chunk_number
        while True:
            chunk, queued = await queue.get()
            try:
                if not failure:
                    started = time.monotonic()
                    raw_words: list[dict] = []
                    args = (chunk.audio, passage['language'], chunk.t_start)
                    words = await asyncio.to_thread(transcriber.transcribe, *args, **({'diagnostics': raw_words} if debug else {}))
                    finished = time.monotonic()
                    changed = set()
                    decisions = []
                    for word in words:
                        before = aligner.p
                        touched = aligner.feed([word])
                        changed.update(touched)
                        if debug:
                            decisions.append(dict(heard=word.text, pointer_before=before, pointer_after=aligner.p,
                                                  expected=aligner.tokens[before] if before < len(aligner.tokens) else None,
                                                  marks=[dict(asdict(aligner.marks[i]), expected=aligner.tokens[i]) for i in sorted(touched)]))
                    event = dict(type='update', marks=[asdict(aligner.marks[i]) for i in sorted(changed)],
                                 pointer=aligner.p, latency_ms=round((time.monotonic()-queued)*1000))
                    if debug:
                        chunk_number += 1
                        duration = chunk.audio.size / chunker.sample_rate
                        event['debug'] = dict(chunk=chunk_number, start_s=chunk.t_start, duration_s=duration,
                                              queue_ms=round((started-queued)*1000), processing_ms=round((finished-started)*1000),
                                              realtime_ratio=round((finished-started)/duration, 2), queued_chunks=queue.qsize(),
                                              words=raw_words, decisions=decisions)
                    await websocket.send_json(event)
            except Exception as exc:
                failure.append(exc)
            finally:
                queue.task_done()

    task = asyncio.create_task(worker())
    async def enqueue(chunks):
        for chunk in chunks:
            queue.put_nowait((chunk, time.monotonic()))

    try:
        while True:
            message = await websocket.receive()
            if message['type'] == 'websocket.disconnect':
                break
            if failure:
                raise RuntimeError('Speech processing failed. Restart the reading and try again.')
            if message.get('bytes') is not None:
                data = message['bytes']
                if len(data) % 2 or len(data) > 320000:
                    raise ValueError('Invalid audio frame. Start a new reading.')
                was_ready = chunker.calibrated
                chunks = chunker.push(np.frombuffer(data, dtype='<i2'))
                if chunker.calibrated and not was_ready:
                    await websocket.send_json(dict(type='ready', calibration_limited=chunker.calibration_limited))
                await enqueue(chunks)
                if debug and data:
                    samples = np.frombuffer(data, dtype='<i2').astype(np.float64)
                    await websocket.send_json(dict(type='debug_audio', rms=round(float(np.sqrt(np.mean(samples**2))), 1),
                                                   threshold=round(chunker.threshold, 1), calibrated=chunker.calibrated, calibration_limited=chunker.calibration_limited,
                                                   clipped_pct=round(float(np.mean(np.abs(samples) >= 32760))*100, 1),
                                                   received_s=round((chunker.frame_index*chunker.frame_size+chunker.pending.size)/chunker.sample_rate, 2),
                                                   queued_chunks=queue.qsize()))
            elif message.get('text') is not None:
                try:
                    command = json.loads(message['text'])
                except json.JSONDecodeError:
                    raise ValueError('Invalid reading command. Start a new reading.')
                if not isinstance(command, dict) or command.get('type') != 'stop':
                    raise ValueError('Unknown reading command.')
                await enqueue(chunker.flush())
                await queue.join()
                if failure:
                    raise RuntimeError('Speech processing failed. Restart the reading and try again.')
                await websocket.send_json(dict(type='done', marks=[asdict(m) for m in aligner.snapshot()],
                                               first_t=aligner.first_t, last_t=aligner.last_t))
                break
    except WebSocketDisconnect:
        pass
    except (ValueError, RuntimeError, asyncio.QueueFull) as exc:
        message = ('Speech processing cannot keep up. Stop other apps and try again.'
                   if isinstance(exc, asyncio.QueueFull) else str(exc))
        with suppress(RuntimeError, WebSocketDisconnect):
            event = dict(type='error', message=message)
            if debug and failure:
                event['diagnostic_error'] = dict(kind=type(failure[0]).__name__, message=str(failure[0])[:1000])
            await websocket.send_json(event)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close()
