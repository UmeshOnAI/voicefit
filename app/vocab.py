"""Exercise vocabulary: ids, names, aliases, and transcription bias terms.

Task 1 owns this file. The same list seeds the `exercises` table in db.py.
"""

EXERCISES: list[dict] = [
    {"id": "romanian_deadlift", "name": "Romanian deadlift",
     "aliases": ["rdl", "rdls", "romanian deadlift", "romanian deadlifts"]},
    {"id": "bench_press", "name": "Bench press",
     "aliases": ["bench", "bench press"]},
    {"id": "back_squat", "name": "Back squat",
     "aliases": ["squat", "squats", "back squat"]},
    {"id": "overhead_press", "name": "Overhead press",
     "aliases": ["ohp", "overhead press", "shoulder press"]},
    {"id": "deadlift", "name": "Deadlift",
     "aliases": ["deadlift", "deadlifts"]},
    {"id": "barbell_row", "name": "Barbell row",
     "aliases": ["row", "rows", "barbell row", "bent over row"]},
    {"id": "pull_up", "name": "Pull-up",
     "aliases": ["pull up", "pull ups", "pullups", "chin ups"]},
    {"id": "lunge", "name": "Lunge",
     "aliases": ["lunge", "lunges"]},
]

MOODS = ("low", "active", "pumped")

# Extra terms fed to the transcriber's context_bias alongside the vocabulary.
BIAS_EXTRA = ["reps", "sets", "kilos", "kg", "pounds"]


def context_bias_terms() -> list[str]:
    """Every exercise name and alias, plus the unit/rep words, for context_bias."""
    terms = set(BIAS_EXTRA)
    for ex in EXERCISES:
        terms.add(ex["name"])
        terms.update(ex["aliases"])
    return sorted(terms)
