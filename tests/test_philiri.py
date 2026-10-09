import pytest

from server.philiri import grade_profile


@pytest.mark.parametrize('miscues,answers,expected', [
    (0, 80, 'independent'), (0, 59, 'instructional'), (0, 58, 'frustration'),
    (10, 80, 'independent'), (10, 59, 'instructional'), (10, 58, 'frustration'),
    (11, 80, 'frustration'), (11, 59, 'frustration'), (11, 58, 'frustration'),
])
def test_supplied_rubric_combinations(miscues, answers, expected):
    result = grade_profile(dict(words_total=100, words_attempted=100, miscues=miscues, partial=False), answers, 100)
    assert result['overall_philiri_level'] == expected


@pytest.mark.parametrize('attempted,partial,answers,total', [(50, True, 80, 100), (0, True, 80, 100), (100, False, None, None)])
def test_combined_level_requires_both_components(attempted, partial, answers, total):
    result = grade_profile(dict(words_total=100, words_attempted=attempted, miscues=0, partial=partial), answers, total)
    assert result['overall_philiri_level'] is None
