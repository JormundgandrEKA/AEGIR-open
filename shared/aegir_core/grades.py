"""Source and licence grades (the scale lives in shared/config/grades.json)."""


def grade_for(grades, key, journal=None, journal_title=None):
    if not key:
        return "ungraded"
    base = grades["licence_grades"].get(key, "F")
    ov = grades.get("journal_overrides", {}).get(key, {})
    for j in (journal, journal_title):
        if j and j.strip().lower() in ov:
            return ov[j.strip().lower()]
    return base


def rank(grades, g):
    scale = grades["scale"]
    return scale.index(g) if g in scale else len(scale)


def grade_at_least(grades, g, minimum):
    """True if g is as good as or better than `minimum`; ungraded never qualifies."""
    return g != "ungraded" and rank(grades, g) <= rank(grades, minimum)
