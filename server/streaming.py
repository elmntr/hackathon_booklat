"""Offline Vosk trial: continuous audio and revisable passage previews."""
import asyncio
from contextlib import suppress
from copy import copy
from dataclasses import asdict
import json
from pathlib import Path
import time

from fastapi import WebSocket, WebSocketDisconnect
import numpy as np

from server.aligner import Aligner, HeardWord

ROOT = Path(__file__).resolve().parents[1]
MODEL_NAMES = {'en': 'vosk-model-small-en-us-0.15', 'tl': 'vosk-model-tl-ph-generic-0.6'}


def recognize_frame(recognizer, data: bytes) -> tuple[bool, dict]:
    """Advance Vosk and fetch its matching hypothesis in one worker dispatch."""
    endpoint = recognizer.AcceptWaveform(data)
    raw = recognizer.Result() if endpoint else recognizer.PartialResult()
    return bool(endpoint), json.loads(raw)


class VoskModels:
    def __init__(self):
        self.models: dict = {}
        self.errors: dict = {}
        self.finished = False

    def load(self) -> None:
        """Explicit local paths prevent Vosk's automatic model downloads."""
        try:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)
            for language, name in MODEL_NAMES.items():
                path = ROOT / 'models' / name
                try:
                    if not path.is_dir():
                        raise FileNotFoundError(f'Missing {name}. Run ./scripts/setup_vosk.sh once online.')
                    self.models[language] = Model(model_path=str(path))
                except Exception as exc:
                    self.errors[language] = str(exc)
        except Exception as exc:
            self.errors = {lang: f'Vosk unavailable: {exc}. Run ./scripts/setup_vosk.sh once online.' for lang in MODEL_NAMES}
        finally:
            self.finished = True

    def status(self) -> dict:
        return {lang: dict(model=name, loaded=lang in self.models, error=self.errors.get(lang),
                           loading=not self.finished and lang not in self.models)
                for lang, name in MODEL_NAMES.items()}

    def recognizer(self, language: str, sample_rate: int):
        from vosk import KaldiRecognizer
        recognizer = KaldiRecognizer(self.models[language], sample_rate)
        recognizer.SetWords(True)
        # The text-only best path is available before Vosk's partial word lattice.
        # Real word timestamps still come from SetWords(True) at phrase endpoints.
        recognizer.SetPartialWords(False)
        return recognizer


class StreamingAlignment:
    """Commit only endpoint results; rebuild each partial from that baseline."""
    def __init__(self, passage: str, cfg: dict, debug: bool = False):
        self.committed = Aligner(passage, cfg)
        self.last_signature = None
        self.events = 0
        self.last_marks = self.committed.snapshot()
        self.last_provisional: set[int] = set()
        self.debug = debug

    def update(self, result: dict, final: bool, audio_end: float) -> dict | None:
        text = result.get('text' if final else 'partial', '')
        raw = result.get('result' if final else 'partial_result', [])
        signature = (final, text, json.dumps(raw, sort_keys=True))
        if not final and signature == self.last_signature:
            return None
        self.last_signature = signature
        # Partial word timestamps can trail the partial text. Preview all text now;
        # estimated times are never committed to scores.
        if not final and ' '.join(w['word'] for w in raw) != text:
            tokens = text.split()
            start = self.committed.last_t or 0.0
            step = max(0.0, audio_end-start) / max(1, len(tokens))
            raw = [dict(word=word, start=start+i*step, end=start+(i+1)*step) for i, word in enumerate(tokens)]
        if final and text and not raw:
            raise ValueError('Vosk returned final text without word timestamps.')
        baseline = self.committed.marks
        aligned = self.committed if final else copy(self.committed)
        if not final:
            aligned.marks = self.committed.snapshot()
        decisions = []
        for item in raw:
            word = HeardWord(item['word'], float(item['start']), float(item['end']))
            pointer = aligned.p
            changed = aligned.feed([word])
            if self.debug:
                decisions.append(dict(heard=word.text, pointer_before=pointer, pointer_after=aligned.p,
                                      expected=aligned.tokens[pointer] if pointer < len(aligned.tokens) else None,
                                      marks=[dict(asdict(aligned.marks[i]), expected=aligned.tokens[i]) for i in sorted(changed)]))
        provisional = set() if final else {i for i, (a, b) in enumerate(zip(baseline, aligned.marks)) if a != b}
        changed = {i for i, (a, b) in enumerate(zip(self.last_marks, aligned.marks)) if a != b}
        changed.update(self.last_provisional.symmetric_difference(provisional))
        changed_marks = [asdict(aligned.marks[i]) for i in sorted(changed)]
        self.last_marks = aligned.snapshot()
        self.last_provisional = provisional
        self.events += 1
        return dict(type='update', marks=[asdict(m) for m in aligned.marks], pointer=aligned.p,
                    provisional=sorted(provisional), changed_marks=changed_marks, final=final, transcript=text,
                    words=[dict(text=w['word'], t0=float(w['start']), t1=float(w['end']),
                                probability=float(w['conf']) if 'conf' in w else None, accepted=True) for w in raw] if self.debug else [],
                    decisions=decisions)


async def read_stream(websocket: WebSocket, passage: dict, cfg: dict, models: VoskModels, debug: bool) -> None:
    """Process consecutive PCM frames; never gate speech by microphone loudness."""
    if passage['language'] not in models.models:
        await websocket.send_json(dict(type='error', message=models.errors.get(passage['language']) or 'Vosk model is still loading. Try again shortly.'))
        await websocket.close()
        return
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    alignment = StreamingAlignment(passage['text'], cfg, debug)
    sample_rate = cfg['chunker']['sample_rate']
    received_samples = 0
    processed_samples = 0
    audio_report_at = 0.0

    async def worker():
        nonlocal processed_samples
        recognizer = await asyncio.to_thread(models.recognizer, passage['language'], sample_rate)
        await websocket.send_json(dict(type='ready', streaming=True))
        while True:
            data, queued = await queue.get()
            started = time.monotonic()
            final = data is None
            if final:
                result = json.loads(await asyncio.to_thread(recognizer.FinalResult))
            else:
                endpoint, result = await asyncio.to_thread(recognize_frame, recognizer, data)
                processed_samples += len(data)//2
                final = endpoint
            finished = time.monotonic()
            event = alignment.update(result, final, processed_samples/sample_rate)
            if event is not None:
                words, decisions = event.pop('words'), event.pop('decisions')
                event['latency_ms'] = round((finished-queued)*1000)
                event['queue_ms'] = round((started-queued)*1000)
                event['processing_ms'] = round((finished-started)*1000)
                if not final:
                    # The browser already has the previous frame's marks.
                    event['marks'] = event['changed_marks']
                if debug:
                    duration = len(data)/2/sample_rate if data else 0
                    event['debug'] = dict(engine='vosk', chunk=alignment.events,
                                          start_s=processed_samples/sample_rate-duration, duration_s=duration,
                                          queue_ms=round((started-queued)*1000), processing_ms=round((finished-started)*1000),
                                          realtime_ratio=round((finished-started)/duration, 2) if duration else 0,
                                          queued_chunks=queue.qsize(), words=words, decisions=decisions,
                                          final=final, transcript=event['transcript'])
                await websocket.send_json(event)
            if data is None:
                committed = alignment.committed
                await websocket.send_json(dict(type='done', marks=[asdict(m) for m in committed.marks],
                                               first_t=committed.first_t, last_t=committed.last_t))
                return

    async def receive():
        nonlocal received_samples, audio_report_at
        while True:
            message = await websocket.receive()
            if message['type'] == 'websocket.disconnect':
                raise WebSocketDisconnect()
            data = message.get('bytes')
            if data is not None:
                if len(data)%2 or len(data)>320000:
                    raise ValueError('Invalid PCM frame. Start a new reading.')
                if not data:
                    continue
                received_samples += len(data)//2
                queue.put_nowait((data, time.monotonic()))
                # Meters are diagnostic only; low-volume frames still reach Vosk.
                if debug and time.monotonic()-audio_report_at >= .25:
                    audio_report_at = time.monotonic()
                    samples = np.frombuffer(data, dtype='<i2').astype(np.float64)
                    await websocket.send_json(dict(type='debug_audio', streaming=True,
                                                   rms=round(float(np.sqrt(np.mean(samples**2))), 1),
                                                   threshold=None, calibrated=True,
                                                   clipped_pct=round(float(np.mean(np.abs(samples)>=32760))*100, 1),
                                                   received_s=round(received_samples/sample_rate, 2), queued_chunks=queue.qsize()))
            else:
                command = json.loads(message.get('text') or '{}')
                if not isinstance(command, dict) or command.get('type') != 'stop':
                    raise ValueError('Unknown reading command.')
                queue.put_nowait((None, time.monotonic()))
                return

    work = asyncio.create_task(worker())
    receiver = asyncio.create_task(receive())
    try:
        done, _ = await asyncio.wait([work, receiver], return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        if receiver in done:
            await work
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        message = ('Speech processing cannot keep up. Close other apps and try again.' if isinstance(exc, asyncio.QueueFull)
                   else 'Streaming recognition failed. Check the debug report and restart the reading.')
        event = dict(type='error', message=message)
        if debug:
            event['diagnostic_error'] = dict(kind=type(exc).__name__, message=str(exc)[:1000])
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.send_json(event)
    finally:
        for task in (work, receiver):
            task.cancel()
        await asyncio.gather(work, receiver, return_exceptions=True)
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.close()
