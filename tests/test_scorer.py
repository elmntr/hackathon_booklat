from copy import deepcopy
import pytest
from server.config import load_config
from server.scorer import score


def marks(correct, wrong=0, unread=0):
    return [{'status': s, 'repeats': 0} for s in
            ['correct'] * correct + ['substitution'] * wrong + ['not_reached'] * unread]


def test_guide_example():
    result = score(marks(50, 15), 0, 60, load_config())
    assert result['accuracy_pct'] == 76.9 and result['level'] == 'frustration'


@pytest.mark.parametrize('correct,wrong,accuracy,level', [
    (97, 3, 97.0, 'independent'), (969, 31, 96.9, 'instructional'),
    (90, 10, 90.0, 'instructional'), (899, 101, 89.9, 'frustration')])
def test_boundaries(correct, wrong, accuracy, level):
    result = score(marks(correct, wrong), 0, 60, load_config())
    assert result['accuracy_pct'] == accuracy and result['level'] == level


def test_partial_and_wpm():
    result = score(marks(9, 1, 10), 2, 32, load_config())
    assert result['words_attempted'] == 10 and result['partial']
    assert result['accuracy_pct'] == 90 and result['wpm'] == 18
    assert score(marks(1), 0, .5, load_config())['wpm'] is None


def test_repetition_configuration_and_floor():
    cfg = deepcopy(load_config())
    reading = [{'status': 'correct', 'repeats': 2}]
    assert score(reading, 0, 2, cfg)['accuracy_pct'] == 0
    cfg['scoring']['counted_miscues'].remove('repetition')
    assert score(reading, 0, 2, cfg)['accuracy_pct'] == 100


def test_empty():
    result = score(marks(0, unread=3), None, None, load_config())
    assert result['accuracy_pct'] is None and result['level'] is None
    assert result['wpm'] is None and result['words_attempted'] == 0
