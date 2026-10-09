"""Phil-IRI component rubric; teacher review is required for ASR suggestions."""
RUBRIC = {
    'version': 'Phil-IRI 2018 component criteria / Booklat supplied rubric v2',
    'source_title': 'DepEd PPST Resource Package Module 11, Phil-IRI criteria',
    'source_url': 'https://depedph-my.sharepoint.com/:b:/g/personal/lrms_manila_deped_gov_ph/EcCrs5zU1fZKqzNFxzbKgoUBBvvgAwjtsX9j4XKZpYtT5g?e=Lk2UtR',
    'criteria': [
        {'level': 'independent', 'word_reading': '97–100%', 'comprehension': '80–100%', 'description': 'Reads and understands material independently.'},
        {'level': 'instructional', 'word_reading': '90–96%', 'comprehension': '59–79%', 'description': 'Benefits from teacher guidance.'},
        {'level': 'frustration', 'word_reading': '89% and below', 'comprehension': '58% and below', 'description': 'Needs substantial support with this material.'},
    ],
    'word_formula': '(Passage words − counted miscues) ÷ passage words × 100',
    'comprehension_formula': 'Correct answers ÷ questions administered × 100',
    'notes': 'Decimal scores use thresholds 97/90 for word reading and 80/59 for comprehension. WPM does not determine these levels. Combined reading level follows the supplied adapted Phil-IRI table: either frustration component gives frustration; otherwise comprehension determines the reading level. Teacher administration, suitable passages and review of all miscue types are required.',
}


def component_level(percent, independent, instructional):
    if percent is None:
        return None
    return 'independent' if percent >= independent else 'instructional' if percent >= instructional else 'frustration'


def reading_level(word, comprehension):
    if word is None or comprehension is None:
        return None
    return 'frustration' if 'frustration' in (word, comprehension) else comprehension


def grade_profile(result, comprehension_correct=None, comprehension_total=None, reviewed_miscues=None):
    total = result['words_total']
    miscues = result['miscues'] if reviewed_miscues is None else reviewed_miscues
    raw_word = max(0.0, (total - miscues) / total * 100) if total and result['words_attempted'] else None
    raw_comprehension = comprehension_correct / comprehension_total * 100 if comprehension_total else None
    word_level = component_level(raw_word, 97, 90) if not result['partial'] else None
    comprehension_level = component_level(raw_comprehension, 80, 59)
    return dict(
        rubric=RUBRIC, philiri_word_score_pct=round(raw_word, 2) if raw_word is not None else None,
        philiri_word_level=word_level,
        comprehension_correct=comprehension_correct, comprehension_total=comprehension_total,
        comprehension_pct=round(raw_comprehension, 2) if raw_comprehension is not None else None,
        comprehension_level=comprehension_level,
        reviewed_miscues=reviewed_miscues, philiri_miscues=miscues,
        grading_status='incomplete_reading' if result['partial'] else 'teacher_reviewed_miscue_total' if reviewed_miscues is not None else 'automated_word_estimate',
        overall_philiri_level=reading_level(word_level, comprehension_level),
        grading_note='Reading level uses the supplied adapted Phil-IRI combination table. Both components and a complete reading are required. Automatic miscues cover available word marks; a teacher must review other miscue types. Comprehension is entered by a teacher, not inferred from speech.',
    )
