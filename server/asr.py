"""In-memory audio framing and offline CPU speech recognition."""
from collections import deque
from dataclasses import dataclass
import os
import threading

import numpy as np

from server.aligner import HeardWord


@dataclass
class Chunk:
    audio: np.ndarray
    t_start: float


class Chunker:
    def __init__(self, cfg: dict):
        self.cfg = cfg['chunker']
        self.sample_rate = self.cfg['sample_rate']
        self.frame_size = self.sample_rate * self.cfg['frame_ms'] // 1000
        self.calibrated = self.cfg['calibration_frames'] == 0
        self.threshold = float(self.cfg['threshold_floor'])
        self.pending = np.empty(0, dtype=np.int16)
        self.noise: list[float] = []
        self.quiet = deque(maxlen=max(1, self.cfg["calibration_frames"]))
        self.calibration_limited = False
        self.pre = deque(maxlen=self.cfg['lead_in_frames'])
        self.frames: list[np.ndarray] = []
        self.speech_frames = self.silent_run = self.frame_index = 0
        self.start = 0.0

    def _threshold(self, estimate: float) -> float:
        return max(self.cfg['threshold_floor'], min(self.cfg['threshold_ceiling'], estimate))

    def _finish(self) -> list[Chunk]:
        chunks = []
        if self.frames and self.speech_frames >= self.cfg['min_speech_frames']:
            chunks.append(Chunk(np.concatenate(self.frames), self.start))
        self.frames = []
        self.speech_frames = self.silent_run = 0
        self.pre.clear()
        return chunks

    def _frame(self, frame: np.ndarray) -> list[Chunk]:
        index = self.frame_index
        self.frame_index += 1
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))
        if not self.calibrated:
            self.noise.append(rms)
            if len(self.noise) >= self.cfg['calibration_frames']:
                estimate = self.cfg['threshold_multiplier'] * float(np.median(self.noise))
                self.calibration_limited = estimate > self.cfg['threshold_ceiling']
                self.threshold = self._threshold(estimate)
                self.calibrated = True
            return []
        # Recover from startup speech or changing microphone gain during idle audio.
        if not self.frames and rms <= self.threshold:
            self.quiet.append(rms)
            if len(self.quiet) == self.quiet.maxlen:
                self.threshold = min(self.threshold, self._threshold(
                    self.cfg['threshold_multiplier'] * float(np.median(self.quiet))))
        else:
            self.quiet.clear()
        speech = rms > self.threshold
        if not self.frames:
            if not speech:
                self.pre.append(frame)
                return []
            self.start = (index - len(self.pre)) * self.frame_size / self.sample_rate
            self.frames = list(self.pre)
            self.pre.clear()
        self.frames.append(frame)
        self.speech_frames += int(speech)
        self.silent_run = 0 if speech else self.silent_run + 1
        if (len(self.frames) >= self.cfg['max_chunk_frames'] or
            (self.silent_run >= self.cfg['pause_frames'] and len(self.frames) >= self.cfg['min_chunk_frames'])):
            return self._finish()
        return []

    def push(self, samples: np.ndarray) -> list[Chunk]:
        """Reframe arbitrary incoming PCM sizes without losing samples."""
        self.pending = np.concatenate((self.pending, np.asarray(samples, dtype=np.int16).reshape(-1)))
        chunks = []
        offset = 0
        while offset + self.frame_size <= self.pending.size:
            chunks.extend(self._frame(self.pending[offset:offset + self.frame_size].copy()))
            offset += self.frame_size
        self.pending = self.pending[offset:].copy()
        return chunks

    def flush(self) -> list[Chunk]:
        chunks = []
        if self.pending.size:
            chunks.extend(self._frame(self.pending))
            self.pending = np.empty(0, dtype=np.int16)
        chunks.extend(self._finish())
        return chunks


class Transcriber:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.loaded = False
        self.error: str | None = None
        self.model = None
        self.lock = threading.Lock()

    def load(self) -> None:
        """Load cached weights only; missing models never trigger a download."""
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.cfg['asr']['model'], device='cpu',
                                      compute_type=self.cfg['asr']['compute_type'],
                                      cpu_threads=os.cpu_count() or 4, local_files_only=True)
            self.transcribe(np.zeros(self.cfg['chunker']['sample_rate'], dtype=np.int16), 'en', 0)
            self.loaded = True
            self.error = None
        except Exception as exc:
            self.error = str(exc)
            self.loaded = False

    def transcribe(self, audio_int16: np.ndarray, language: str, t_start: float, diagnostics: list[dict] | None = None) -> list[HeardWord]:
        if self.model is None:
            raise RuntimeError('Speech model is not loaded.')
        settings = self.cfg['asr']
        with self.lock:
            segments, _ = self.model.transcribe(
                audio_int16.astype(np.float32) / 32768.0, language=language,
                beam_size=settings['beam_size'], temperature=0, condition_on_previous_text=False,
                word_timestamps=True, vad_filter=False)
            words = []
            for segment in segments:
                for word in segment.words or []:
                    accepted = bool(word.probability >= settings['min_word_probability'])
                    heard = HeardWord(word.word.strip(), float(t_start + word.start), float(t_start + word.end))
                    if diagnostics is not None:
                        diagnostics.append(dict(text=heard.text, t0=heard.t0, t1=heard.t1,
                                                probability=float(word.probability), accepted=accepted))
                    if accepted:
                        words.append(heard)
            return words
