"""Replay a user-recorded PCM WAV through the local reading pipeline."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid
import wave

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.config import load_config

BASE = 'http://127.0.0.1:8000'


def request(path: str, body: dict | None = None):
    req = Request(BASE + path, data=json.dumps(body).encode() if body else None,
                  headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=20) as response:
        return json.load(response)


async def replay(args) -> None:
    cfg = load_config()['chunker']
    sample_rate = cfg['sample_rate']
    frame_ms = 100 if args.engine == 'vosk' else cfg['frame_ms']
    frame_size = sample_rate * frame_ms // 1000
    with wave.open(args.wav, 'rb') as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != sample_rate or wav.getcomptype() != 'NONE':
            raise ValueError(f'Use an uncompressed {sample_rate} Hz mono 16-bit WAV file.')
        passages = request('/api/passages')
        passage = next((p for p in passages if p['id'] == args.passage_id), None)
        if not passage:
            raise ValueError('Unknown passage id. Use ' + ', '.join(p['id'] for p in passages))
        uri = 'ws://127.0.0.1:8000/ws/read?' + urlencode({'passage_id': args.passage_id, 'engine': args.engine})
        async with websockets.connect(uri, max_size=2**20) as ws:
            async def send():
                # Synthetic quiet lead-in calibrates the live chunker without dropping recorded speech.
                if args.engine == 'whisper':
                    await ws.send(bytes(frame_size * 2 * cfg['calibration_frames']))
                while data := wav.readframes(frame_size):
                    await ws.send(data)
                    await asyncio.sleep(frame_ms / 1000 if args.realtime else .02)
                await ws.send(json.dumps({'type': 'stop'}))

            sender = asyncio.create_task(send())
            done = None
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=300)
                    event = json.loads(raw)
                    if event['type'] == 'error':
                        raise ValueError(event['message'])
                    if event['type'] == 'update':
                        for mark in event['marks']:
                            print(f"{mark['idx']} {passage['tokens'][mark['idx']]} {mark['status']} repeats={mark['repeats']}")
                    if event['type'] == 'done':
                        done = event
                        break
                if done is None:
                    raise ValueError('The local server closed before returning a result.')
                await sender
            finally:
                sender.cancel()
                try:
                    await sender
                except asyncio.CancelledError:
                    pass
        result = request('/api/score', dict(session_id=str(uuid.uuid4()), learner='Replay',
                         passage_id=args.passage_id, marks=done['marks'], first_t=done['first_t'],
                         last_t=done['last_t'], teacher_edited=False, save=False))
        print(f"Accuracy: {result['accuracy_pct']}% | WPM: {result['wpm']} | Level: {result['level']}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav')
    parser.add_argument('passage_id')
    parser.add_argument('--realtime', action='store_true')
    parser.add_argument('--engine', choices=['whisper', 'vosk'], default='whisper')
    args = parser.parse_args()
    try:
        asyncio.run(replay(args))
    except (OSError, ValueError, wave.Error, URLError, TimeoutError, websockets.exceptions.WebSocketException) as exc:
        raise SystemExit(f'Replay failed: {exc}\nStart ./run.sh and check the WAV format and passage id.')
