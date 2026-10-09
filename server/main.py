"""Offline reading sessions, document imports, and SQLite history."""
import asyncio
from contextlib import asynccontextmanager, suppress
import csv
from dataclasses import asdict
from datetime import datetime
import io
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid
import wave
import math
from html import escape
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from server.aligner import Aligner
from server.asr import Chunker, Transcriber
from server.config import load_config
from server.philiri import RUBRIC, grade_profile
from server.scorer import score
from server.streaming import VoskModels, read_stream
from server.storage import Store
from server.imports import MAX_UPLOAD, clean_text, extract

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ('session_id,timestamp,learner,passage_id,language,grade,words_attempted,words_total,'
           'reading_time_s,wpm,accuracy_pct,level,substitutions,omissions,repetitions,teacher_edited,philiri_word_score_pct,philiri_word_level,philiri_miscues,reviewed_miscues,comprehension_correct,comprehension_total,comprehension_pct,comprehension_level,grading_status,grading_note,rubric_version,word_independent_criteria,word_instructional_criteria,word_frustration_criteria,comprehension_independent_criteria,comprehension_instructional_criteria,comprehension_frustration_criteria,rubric_source,word_score_formula,comprehension_formula,counted_miscue_types,overall_philiri_level').split(',')


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cfg = load_config()
    passages = json.loads((ROOT / 'data/passages.json').read_text(encoding='utf-8'))
    app.state.passages = {p['id']: dict(p, tokens=p['text'].split(), word_count=len(p['text'].split())) for p in passages}
    app.state.results_path = Path(os.environ.get('BOOKLAT_RESULTS_PATH', ROOT / 'data/results.csv'))
    default_db = app.state.results_path.with_suffix('.sqlite3') if 'BOOKLAT_RESULTS_PATH' in os.environ else ROOT / 'data/booklat.sqlite3'
    app.state.store = Store(Path(os.environ.get('BOOKLAT_DB_PATH', default_db)))
    app.state.store.migrate_csv(app.state.results_path, app.state.passages)
    for passage in app.state.store.passages():
        app.state.passages[passage['id']] = passage
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
    return FileResponse(ROOT / 'web/index.html', headers={'Cache-Control': 'no-cache'})


@app.get('/api/health')
def health():
    t = app.state.transcriber
    return dict(status='ok', model=app.state.cfg['asr']['model'], loaded=t.loaded,
                error=t.error, device=t.device, compute_type=t.compute_type,
                gpu_error=t.gpu_error, cpu_threads=t.cpu_threads, network_needed=False)


@app.get('/api/engines')
def engines():
    return dict(whisper=health(), vosk=app.state.vosk.status())


@app.get('/api/passages')
def passages():
    return list(app.state.passages.values())


class PassageRequest(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30000)]
    language: Literal['en', 'tl']
    grade: Annotated[int, Field(strict=True, ge=1, le=12)] = 3
    source: Annotated[str, StringConstraints(max_length=200)] = 'Pasted text'


@app.post('/api/passages', status_code=201)
def add_passage(body: PassageRequest):
    text = clean_text(body.text)
    tokens = text.split()
    if not 1 <= len(tokens) <= 2000:
        raise HTTPException(422, 'Choose an excerpt of 1–2,000 words. Split longer books into separate passages.')
    passage = dict(id='custom-' + str(uuid.uuid4()), title=body.title, text=text, language=body.language,
                   grade=body.grade, source=body.source, tokens=tokens, word_count=len(tokens), custom=True)
    try:
        app.state.store.add_passage(passage)
    except (OSError, sqlite3.Error):
        raise HTTPException(500, 'Could not save the passage. Check local disk space and permissions.')
    app.state.passages[passage['id']] = passage
    return passage


class BookRequest(PassageRequest):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100000)]
    section_words: Annotated[int, Field(strict=True, ge=50, le=2000)] = 300


@app.post('/api/books', status_code=201)
def add_book(body: BookRequest):
    words = clean_text(body.text).split()
    book_id = 'book-' + str(uuid.uuid4())
    sections = []
    count = (len(words) + body.section_words - 1) // body.section_words
    for number, start in enumerate(range(0, len(words), body.section_words), 1):
        tokens = words[start:start + body.section_words]
        sections.append(dict(id='custom-' + str(uuid.uuid4()),
                             title=f'{body.title[:75]} · {number}/{count}', text=' '.join(tokens),
                             language=body.language, grade=body.grade, source=body.source,
                             tokens=tokens, word_count=len(tokens), custom=True,
                             book_id=book_id, book_title=body.title, section=number, sections=count))
    try:
        app.state.store.add_passages(sections)
    except (OSError, sqlite3.Error):
        raise HTTPException(500, 'Could not save book sections. Check disk space and permissions.')
    app.state.passages.update({p['id']: p for p in sections})
    return dict(book_id=book_id, passages=sections)


@app.post('/api/import')
async def import_document(request: Request, filename: str = Query(max_length=255)):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD:
            raise HTTPException(413, 'Choose a document up to 10 MB or paste a shorter excerpt.')
        data.extend(chunk)
    try:
        return await asyncio.to_thread(extract, bytes(data), filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(422, 'Could not extract text. Try an unprotected file or paste the text.')


class ScoreMark(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    status: Literal['not_reached', 'correct', 'substitution', 'omission']
    repeats: Annotated[int, Field(strict=True, ge=0, le=20)] = 0
    heard: Annotated[str, StringConstraints(max_length=1200)] | None = None
    t0: Annotated[float, Field(ge=0)] | None = None
    t1: Annotated[float, Field(ge=0)] | None = None
    self_corrected: bool = False


    @model_validator(mode='after')
    def validate_word_clock(self):
        if (self.t0 is None) != (self.t1 is None):
            raise ValueError('Word start and end timestamps must be supplied together.')
        if self.t0 is not None and self.t1 < self.t0:
            raise ValueError('Word end time must not precede start time.')
        return self


class ScoreRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    session_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    learner: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    passage_id: str
    marks: list[ScoreMark]
    first_t: Annotated[float, Field(ge=0)] | None = None
    last_t: Annotated[float, Field(ge=0)] | None = None
    comprehension_correct: Annotated[int, Field(strict=True, ge=0, le=1000)] | None = None
    comprehension_total: Annotated[int, Field(strict=True, ge=1, le=1000)] | None = None
    reviewed_miscues: Annotated[int, Field(strict=True, ge=0, le=100000)] | None = None
    teacher_edited: bool = False
    save: bool = False
    engine: Literal['vosk', 'whisper'] = 'whisper'
    validation_mode: Literal['live', 'auto_finish', 'after_pause', 'after_stop'] = 'live'

    @model_validator(mode='after')
    def validate_clock(self):
        if (self.comprehension_correct is None) != (self.comprehension_total is None):
            raise ValueError('Enter both comprehension scores, or leave both empty.')
        if self.comprehension_total is not None and self.comprehension_correct > self.comprehension_total:
            raise ValueError('Correct answers cannot exceed questions administered.')
        if (self.first_t is None) != (self.last_t is None):
            raise ValueError('Both reading timestamps must be supplied together.')
        if self.first_t is not None and self.last_t < self.first_t:
            raise ValueError('End time must not precede start time.')
        return self


def read_rows() -> list[dict]:
    return app.state.store.history(limit=-1)


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def rubric_export_fields():
    values = dict(rubric_version=RUBRIC['version'], rubric_source=RUBRIC['source_url'], word_score_formula=RUBRIC['word_formula'], comprehension_formula=RUBRIC['comprehension_formula'])
    for row in RUBRIC['criteria']:
        values['word_' + row['level'] + '_criteria'] = row['word_reading']
        values['comprehension_' + row['level'] + '_criteria'] = row['comprehension']
    return values


@app.get('/api/rubric')
def reading_rubric():
    return RUBRIC


@app.get('/api/results/{session_id}/report.html')
def grading_report(session_id: str):
    saved = app.state.store.reading(session_id)
    if saved is None:
        raise HTTPException(404, 'Reading not found.')
    summary = saved['summary']
    detail = saved['reading'] or {}
    grading = detail.get('grading') or summary
    rubric = grading.get('rubric') or RUBRIC
    def cell(value):
        return escape(str(value)) if value is not None and value != '' else 'Not assessed'
    rows = ''.join('<tr><td>' + cell(r['level'].title()) + '</td><td>' + cell(r['word_reading']) + '</td><td>' + cell(r['comprehension']) + '</td></tr>' for r in rubric['criteria'])
    values = [('Word score (%)', grading.get('philiri_word_score_pct')), ('Word component level', grading.get('philiri_word_level')),
              ('Counted miscues', grading.get('philiri_miscues')), ('Automatic miscue types', grading.get('counted_miscue_types')), ('Teacher-reviewed miscues', grading.get('reviewed_miscues')),
              ('Comprehension correct', grading.get('comprehension_correct')), ('Questions administered', grading.get('comprehension_total')),
              ('Comprehension (%)', grading.get('comprehension_pct')), ('Comprehension level', grading.get('comprehension_level')),
              ('Grading status', grading.get('grading_status', 'Legacy record; components not assessed')),
              ('App accuracy (%)', summary.get('accuracy_pct')), ('App word-reading category', summary.get('level')),
              ('Correct words per minute', summary.get('wpm')), ('Reading seconds', summary.get('reading_time_s')),
              ('Words attempted / total', str(summary.get('words_attempted', '')) + ' / ' + str(summary.get('words_total', '')))]
    scores = ''.join('<tr><th>' + cell(k) + '</th><td>' + cell(v) + '</td></tr>' for k, v in values)
    word_rows = ''.join('<tr><td>' + str(i+1) + '</td><td>' + cell(token) + '</td><td>' + cell(mark.get('heard')) + '</td><td>' + cell(mark.get('status')) + '</td><td>' + cell(mark.get('repeats')) + '</td><td>' + cell(mark.get('t0')) + '</td><td>' + cell(mark.get('t1')) + '</td></tr>' for i, (token, mark) in enumerate(zip(detail.get('passage', {}).get('tokens', []), detail.get('marks', []))))
    html = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Booklat reading report</title><style>body{font:16px system-ui;margin:32px;line-height:1.5}table{border-collapse:collapse;width:100%;margin:20px 0}td,th{border:1px solid #ccc;padding:8px;text-align:left}h1,h2{break-after:avoid}tr{break-inside:avoid}</style><h1>Booklat reading report</h1>'
    html += '<p>Learner: ' + cell(summary.get('learner')) + '<br>Passage: ' + cell(summary.get('passage_title')) + '<br>Saved: ' + cell(summary.get('timestamp')) + '</p><h2>Scores</h2><table>' + scores + '</table><h2>Phil-IRI component criteria</h2><table><tr><th>Level</th><th>Word recognition</th><th>Comprehension</th></tr>' + rows + '</table>'
    html += '<p>' + cell(rubric['word_formula']) + '<br>' + cell(rubric['comprehension_formula']) + '</p><p>' + cell(grading.get('grading_note', rubric['notes'])) + '</p><p>' + cell(rubric['notes']) + '</p><p>Source: ' + cell(rubric['source_title']) + ' — ' + cell(rubric['source_url']) + '</p><h2>Word review and recording times</h2><table><tr><th>#</th><th>Expected</th><th>Heard</th><th>Mark</th><th>Repeats</th><th>Start (s)</th><th>End (s)</th></tr>' + word_rows + '</table></html>'
    return Response(html, media_type='text/html', headers={'Content-Disposition': 'attachment; filename="booklat-reading-report.html"', 'Cache-Control': 'no-store'})


@app.post('/api/score')
def score_reading(body: ScoreRequest):
    passage = app.state.passages.get(body.passage_id)
    if passage is None:
        raise HTTPException(422, 'Unknown passage. Choose a listed passage.')
    if len(body.marks) != passage['word_count']:
        raise HTTPException(422, f"Expected {passage['word_count']} word marks.")
    result = score([m.model_dump() for m in body.marks], body.first_t, body.last_t, app.state.cfg)
    result.update(grade_profile(result, body.comprehension_correct, body.comprehension_total, body.reviewed_miscues))
    result['counted_miscue_types'] = ', '.join(app.state.cfg['scoring']['counted_miscues'])
    if body.save:
        row = dict(session_id=body.session_id, timestamp=datetime.now().astimezone().isoformat(timespec='seconds'),
                   learner=body.learner, passage_id=passage['id'], language=passage['language'],
                   grade=passage['grade'], teacher_edited=body.teacher_edited, passage_title=passage['title'],
                   engine=body.engine, validation_mode=body.validation_mode,
                   device='cpu' if body.engine == 'vosk' else app.state.transcriber.device)
        row.update({k: result[k] for k in COLUMNS if k in result})
        row.update(rubric_export_fields())
        try:
            detail = dict(session_id=body.session_id, learner=body.learner, passage=passage,
                          marks=[dict(m.model_dump(), idx=i) for i, m in enumerate(body.marks)],
                          first_t=body.first_t, last_t=body.last_t, teacher_edited=body.teacher_edited,
                          engine=body.engine, validation_mode=body.validation_mode,
                          comprehension_correct=body.comprehension_correct, comprehension_total=body.comprehension_total,
                          reviewed_miscues=body.reviewed_miscues, grading=result)
            app.state.store.save(row, detail)
        except (OSError, sqlite3.Error):
            raise HTTPException(500, 'Could not save the result. Check available disk space and folder permissions.')
    return dict(result, saved=body.save)


@app.get('/api/results')
def results(q: str = Query(default='', max_length=200), limit: int = Query(default=20, ge=1, le=100),
            offset: int = Query(default=0, ge=0)):
    return app.state.store.history(q, limit, offset)


@app.get('/api/results/{session_id}')
def reading_detail(session_id: str):
    reading = app.state.store.reading(session_id)
    if reading is None:
        raise HTTPException(404, 'This reading was not found in local history.')
    return reading


MAX_RECORDING = 50 * 1024 * 1024


@app.put('/api/results/{session_id}/recordings/{segment_id}')
async def save_recording(session_id: str, segment_id: str, request: Request,
                         offset: float = Query(default=0, ge=0)):
    if len(session_id) > 100 or len(segment_id) > 100 or not math.isfinite(offset):
        raise HTTPException(422, 'Invalid recording identifier or offset.')
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_RECORDING:
            raise HTTPException(413, 'Recording exceeds the 50 MB local limit.')
        data.extend(chunk)
    try:
        with wave.open(io.BytesIO(data), 'rb') as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000 or audio.getcomptype() != 'NONE':
                raise ValueError('Expected mono 16 kHz PCM audio.')
            frames = audio.getnframes()
            if not frames or len(audio.readframes(frames)) != frames * 2:
                raise ValueError('Incomplete recording.')
            duration = frames / 16000
    except (wave.Error, EOFError, ValueError) as exc:
        raise HTTPException(422, 'Invalid WAV recording: ' + str(exc))
    try:
        saved = await asyncio.to_thread(app.state.store.save_recording, session_id, segment_id, offset, duration, bytes(data))
    except (OSError, sqlite3.Error):
        raise HTTPException(500, 'Could not save recording. Check local disk space.')
    if not saved:
        raise HTTPException(404, 'Save the reading result before saving its recording.')
    return dict(saved=True, segment_id=segment_id, time_offset=offset, duration=duration)


@app.get('/api/results/{session_id}/recordings/{segment_id}')
def recording_audio(session_id: str, segment_id: str, request: Request):
    data = app.state.store.recording(session_id, segment_id)
    if data is None:
        raise HTTPException(404, 'Recording not found.')
    headers = {'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store',
               'Content-Disposition': 'inline; filename="reading.wav"'}
    requested = request.headers.get('range')
    if requested:
        try:
            unit, bounds = requested.split('=', 1)
            left, right = bounds.split('-', 1)
            if unit != 'bytes' or ',' in bounds:
                raise ValueError()
            start = int(left) if left else max(0, len(data) - int(right))
            end = min(len(data)-1, int(right)) if left and right else len(data)-1
            if start < 0 or start >= len(data) or end < start:
                raise ValueError()
        except ValueError:
            return Response(status_code=416, headers={'Content-Range': f'bytes */{len(data)}'})
        headers['Content-Range'] = f'bytes {start}-{end}/{len(data)}'
        return Response(data[start:end+1], status_code=206, media_type='audio/wav', headers=headers)
    return Response(data, media_type='audio/wav', headers=headers)


@app.delete('/api/results/{session_id}/recordings')
def delete_recording_audio(session_id: str):
    app.state.store.delete_recordings(session_id)
    return dict(deleted=True)


@app.get('/api/backup.sqlite3')
def database_backup():
    return Response(app.state.store.backup(), media_type='application/vnd.sqlite3',
                    headers={'Content-Disposition': 'attachment; filename="booklat-backup.sqlite3"'})


@app.get('/api/export.csv')
def export_csv():
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows({k: safe_cell(dict(rubric_export_fields(), **row).get(k, '')) for k in COLUMNS} for row in read_rows())
    return Response(output.getvalue(), media_type='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="booklat-results.csv"'})


@app.websocket('/ws/read')
async def read(websocket: WebSocket, passage_id: str = '', debug: bool = False, engine: str = 'whisper', start_index: int = 0):
    await websocket.accept()
    passage = app.state.passages.get(passage_id)
    if not passage:
        await websocket.send_json(dict(type='error', message='Unknown passage. Choose a listed passage.'))
        await websocket.close()
        return
    if not 0 <= start_index < len(passage['tokens']):
        await websocket.send_json(dict(type='error', message='Invalid reading position. Start a new reading.'))
        await websocket.close()
        return
    if start_index:
        passage = dict(passage, text=' '.join(passage['tokens'][start_index:]), tokens=passage['tokens'][start_index:])
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
                                 pointer=aligner.p, final=True, latency_ms=round((time.monotonic()-queued)*1000),
                                 processing_ms=round((finished-started)*1000), queue_ms=round((started-queued)*1000))
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
