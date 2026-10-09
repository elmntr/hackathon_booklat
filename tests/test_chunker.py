from copy import deepcopy
from types import SimpleNamespace
import numpy as np
import pytest
from server.asr import Chunker, Transcriber
from server.config import load_config


def frames(*levels):
    return np.concatenate([np.full(4000, level, dtype=np.int16) for level in levels])


def test_calibration():
    c = Chunker(load_config())
    assert not c.calibrated
    assert c.push(frames(100, 200, 300, 400)) == []
    assert c.calibrated and c.threshold == 625


def test_pause_and_clock():
    c = Chunker(load_config())
    chunks = c.push(frames(0, 0, 0, 0, 0, 1000, 1000, 0, 0))
    assert len(chunks) == 1
    assert chunks[0].t_start == 1.0 and chunks[0].audio.size == 20000


def test_continuous_cap():
    c = Chunker(load_config())
    chunks = c.push(frames(*([0] * 4 + [1000] * 32)))
    assert len(chunks) == 2
    assert [x.t_start for x in chunks] == [1, 5]
    assert all(x.audio.size == 64000 for x in chunks)


def test_silence_and_flush():
    c = Chunker(load_config())
    assert c.push(frames(*([0] * 20))) == [] and c.flush() == []
    c.push(frames(1000))
    assert len(c.flush()) == 1
    assert c.flush() == []


def test_arbitrary_sizes():
    audio = frames(*([0] * 4 + [1000] * 4 + [0] * 2 + [1000] * 2))
    def run(size):
        c = Chunker(load_config())
        output = []
        for i in range(0, len(audio), size):
            output.extend(c.push(audio[i:i+size]))
        return output + c.flush()
    expected, actual = run(4000), run(719)
    assert len(expected) == len(actual)
    for a, b in zip(expected, actual):
        assert a.t_start == b.t_start
        np.testing.assert_array_equal(a.audio, b.audio)


def test_partial_final_frame():
    c = Chunker(load_config())
    c.push(frames(0, 0, 0, 0))
    c.push(np.full(500, 1000, dtype=np.int16))
    assert c.flush()[0].audio.size == 500


def test_min_speech():
    cfg = deepcopy(load_config())
    cfg['chunker']['min_speech_frames'] = 2
    c = Chunker(cfg)
    assert c.push(frames(0, 0, 0, 0, 1000, 0, 0)) == []


def test_transcriber_arguments_and_filtering():
    class Model:
        def transcribe(self, audio, **kwargs):
            assert audio.dtype == np.float32 and audio.max() <= 1
            assert kwargs == dict(language='tl', beam_size=1, temperature=0,
                                  condition_on_previous_text=False, word_timestamps=True, vad_filter=False)
            return [SimpleNamespace(words=[SimpleNamespace(word=' Ben', start=.1, end=.4, probability=.9),
                                            SimpleNamespace(word=' noise', start=.5, end=.8, probability=.01)])], None
    t = Transcriber(load_config())
    t.model = Model()
    words = t.transcribe(frames(1000), 'tl', 2)
    assert len(words) == 1 and words[0].text == 'Ben'
    assert words[0].t0 == pytest.approx(2.1)


def test_transcriber_diagnostics_include_filtered_words():
    class Model:
        def transcribe(self, *args, **kwargs):
            return [SimpleNamespace(words=[SimpleNamespace(word=' Ben', start=.1, end=.4, probability=.9),
                                            SimpleNamespace(word=' noise', start=.5, end=.8, probability=.01)])], None
    t = Transcriber(load_config())
    t.model = Model()
    diagnostic = []
    words = t.transcribe(frames(1000), 'tl', 2, diagnostics=diagnostic)
    assert [w.text for w in words] == ['Ben']
    assert [w['accepted'] for w in diagnostic] == [True, False]
    assert diagnostic[1]['t0'] == 2.5 and diagnostic[1]['probability'] == .01


def test_loud_calibration_is_bounded_and_recovers_for_quiet_speech():
    c = Chunker(load_config())
    c.push(frames(4606, 4606, 4606, 4606))
    assert c.calibration_limited
    assert c.threshold == 1500
    c.push(frames(50, 50, 50, 50))
    assert c.threshold == 250
    chunks = c.push(frames(400, 400, 0, 0))
    assert len(chunks) == 1
    assert chunks[0].t_start == 1.75
    assert np.count_nonzero(chunks[0].audio == 400) == 8000


def test_threshold_does_not_learn_active_speech_as_noise():
    c = Chunker(load_config())
    c.push(frames(0, 0, 0, 0))
    c.push(frames(*([1000] * 20)))
    assert c.threshold == 250
