import pytest
from server.aligner import Aligner, HeardWord, matches, normalize
from server.config import load_config


def feed(aligner, text):
    return aligner.feed([HeardWord(w, i, i + .5) for i, w in enumerate(text.split())])


@pytest.mark.parametrize('heard,statuses', [
    ('Mina has a small garden', ['correct'] * 5),
    ('Mina a small garden', ['correct', 'omission', 'correct', 'correct', 'correct']),
    ('Mina small garden', ['correct', 'omission', 'omission', 'correct', 'correct']),
    ('Mina had a small garden', ['correct', 'substitution', 'correct', 'correct', 'correct']),
    ('Mina has', ['correct', 'correct', 'not_reached', 'not_reached', 'not_reached']),
])
def test_alignment(heard, statuses):
    a = Aligner('Mina has a small garden', load_config())
    feed(a, heard)
    assert [m.status for m in a.marks] == statuses


def test_repeat_and_correction():
    a = Aligner('Mina has a garden', load_config())
    feed(a, 'Mina Mina')
    assert a.p == 1 and a.marks[0].repeats == 1
    feed(a, 'had has')
    assert a.p == 2 and a.marks[1].status == 'correct'
    assert a.marks[1].self_corrected and a.marks[1].repeats == 0


def test_normalization_and_short_words():
    assert normalize("Ña's-á!") == 'ñasá'
    assert not matches('ng', 'ang', load_config()['aligner'])
    assert not matches('!', '?', load_config()['aligner'])


def test_filipino_and_extras():
    a = Aligner('mahal na mahal', load_config())
    feed(a, 'mahal na mahal zebra')
    assert a.p == 3
    assert all(m.status == 'correct' and m.repeats == 0 for m in a.marks)


def test_ignored_words_and_clock():
    a = Aligner('Mina has', load_config())
    a.feed([HeardWord('um', 0, 1), HeardWord('Mina', 2, 3),
            HeardWord('has', 4, 5), HeardWord('!', 6, 7), HeardWord('uh', 8, 9)])
    assert a.first_t == 2 and a.last_t == 5
    assert a.p == 2
    snapshot = a.snapshot()
    snapshot[0].status = 'omission'
    assert a.marks[0].status == 'correct'
