"""Word-reading accuracy and configurable Phil-IRI categories."""


def score(marks: list[dict], first_t: float | None, last_t: float | None, cfg: dict) -> dict:
    settings = cfg['scoring']
    attempted = next((i + 1 for i in range(len(marks) - 1, -1, -1)
                      if marks[i]['status'] != 'not_reached'), 0)
    reached = marks[:attempted]
    correct = sum(m['status'] == 'correct' for m in reached)
    substitutions = sum(m['status'] == 'substitution' for m in reached)
    omissions = sum(m['status'] == 'omission' for m in reached)
    repetitions = sum(m['repeats'] for m in reached)
    counts = dict(substitution=substitutions, omission=omissions, repetition=repetitions)
    miscues = sum(counts[k] for k in settings['counted_miscues'])
    accuracy = max(0.0, round((attempted - miscues) / attempted * 100, 1)) if attempted else None
    duration = round(last_t - first_t, 1) if first_t is not None and last_t is not None and last_t > first_t else None
    wpm = round(correct / (duration / 60)) if duration and duration >= settings['min_time_s'] else None
    level = None
    if accuracy is not None:
        level = ('independent' if accuracy >= settings['levels']['independent'] else
                 'instructional' if accuracy >= settings['levels']['instructional'] else 'frustration')
    return dict(words_total=len(marks), words_attempted=attempted, correct=correct,
                substitutions=substitutions, omissions=omissions, repetitions=repetitions,
                miscues=miscues, accuracy_pct=accuracy, reading_time_s=duration,
                wpm=wpm, level=level, partial=attempted < len(marks))
