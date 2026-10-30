"""Provisional change analysis between two registry versions (no language model; plain rules).

What it checks, and the standards behind it
- Eligibility (SPIRIT 2025 item 14): the text is split into criteria items under Inclusion / Exclusion; items are
  matched across versions. An added criterion narrows, a removed one broadens; a changed threshold is read in the
  light of the section (a lower inclusion minimum broadens, a lower exclusion cut-off narrows).
- Primary outcomes (SPIRIT 2025 item 16 and CONSORT 2025: variable, analysis metric, aggregation, time point;
  COMPare: outcomes added or removed): each outcome is matched, then compared on its measure, its metric words and
  its time point separately.
- Sample size (SPIRIT item 19), arms and interventions (design).
- Substantial vs non-substantial follows the EU Clinical Trials Regulation 536/2014 Art. 2(2)(13): a change is
  substantial when it is likely to affect participants' safety or rights, or the reliability and robustness of the data.
  Spelling, grammar, acronym, formatting and unit-style edits are non-substantial.
- Avoidability categories used in the labelling form follow the Tufts CSDD four-level scale.

Everything is normalised first (case, markup, punctuation, symbols such as >= and the unit spellings), so text that is
identical after normalisation is reported as identical and never as a change.
"""
import difflib
import re
import unicodedata

from aegir_core.textclean import split_items  # noqa: F401  (moved to the shared package; RAN and AutoRAN both use it)

STOP = {"the", "a", "an", "of", "to", "with", "in", "for", "is", "are", "be", "by", "as", "on", "at", "that", "this"}
LOGIC = {"and", "or", "not", "no", "without", "any", "all", "only", "except", "unless", "if", "than", "ge", "le",
         "gt", "lt", "within", "prior", "before", "after", "previous", "current", "active", "history", "severe",
         "mild", "moderate", "unstable", "stable", "documented", "confirmed", "known", "male", "female"}
METRIC_WORDS = ["change from baseline", "percent change", "proportion", "percentage", "time to", "mean", "median",
                "incidence", "area under", "auc", "responder", "slope", "ratio", "rate of"]   # weak words (total, score) ignored
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}

_SUBS = [
    (r"greater than or equal to|more than or equal to|at least|no less than|not less than|minimum of|>=|=>|≥", " ge "),
    (r"less than or equal to|at most|no more than|not more than|maximum of|<=|=<|≤", " le "),
    (r"greater than|more than|older than|above|over|exceeding|in excess of|>", " gt "),
    (r"less than|younger than|below|under|<", " lt "),
    (r"micrograms?|µg|μg|\bug\b|\bmcg\b", " mcg "),
    (r"milligrams?|\bmg\b", " mg "),
    (r"years? old|years?|\byrs?\b|y/o", " year "),
    (r"percent|%", " pct "),
    (r"\bmonths?\b|\bmos?\b", " month "),
    (r"\bweeks?\b|\bwks?\b", " week "),
    (r"\bdays?\b", " day "),
]


def normalise(text):
    """Lower-case token list with symbols, units and plurals unified; markup already removed by clean_text."""
    t = unicodedata.normalize("NFKD", (text or "").casefold())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))     # accents; casefold already maps the sharp s to ss
    t = " " + re.sub(r"(?<=\d),(?=\d{3}\b)", "", t) + " "           # 1,000 -> 1000
    for pat, rep in _SUBS:
        t = re.sub(pat, rep, t)
    t = re.sub(r"[^a-z0-9.]+", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)
    toks = []
    for w in t.split():
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        toks.append(w)
    return toks


def _nums(toks):
    return [float(t) for t in toks if re.fullmatch(r"\d+(?:\.\d+)?", t)]


def _is_acr(tok):
    """An acronym has at least two capitals (FEV1, AECOPD); a capitalised word like Males does not."""
    return 2 <= len(tok) <= 9 and sum(1 for c in tok if c.isupper()) >= 2 and not (tok.isupper() and len(tok) > 6)


_PAREN = re.compile(r"\s*\(([A-Za-z][A-Za-z0-9]{1,8})\)")


def _all_caps(text):
    letters = [c for c in (text or "") if c.isalpha()]
    return len(letters) > 20 and sum(c.islower() for c in letters) / len(letters) < 0.1


def _acronyms(text):
    if _all_caps(text):
        return set()
    return {m.group(1) for m in _PAREN.finditer(text or "") if _is_acr(m.group(1))}


def _strip_acr(text):
    """Drop '(ACR)' after a long form and '(long form)' after an acronym: both only introduce an abbreviation."""
    text = text or ""
    if not _all_caps(text):      # in all-capitals text every word looks like an acronym
        text = _PAREN.sub(lambda m: "" if _is_acr(m.group(1)) else m.group(0), text)

    def expansion(m):
        words = re.findall(r"[A-Za-z0-9]+", m.group(2).lower())
        return m.group(1) if _is_acr(m.group(1)) and _initials_match(m.group(1), words) else m.group(0)
    return re.sub(r"(\b[A-Z][A-Za-z0-9]{1,8})\s*\(([^()]{5,90})\)", expansion, text)


def acronym_map(*texts):
    """{long form (lower case): ACRONYM} harvested from 'Long form (ACR)' and 'ACR (long form)' in the given texts."""
    m = {}
    for text in texts:
        if not text or _all_caps(text):
            continue
        for hit in re.finditer(r"\(([A-Za-z][A-Za-z0-9]{1,8})\)", text):
            acr = hit.group(1)
            if not _is_acr(acr):
                continue
            prev = re.findall(r"[A-Za-z0-9\-]+", text[:hit.start()])[-9:]
            for k in range(1, len(prev) + 1):
                words = [w.lower() for w in prev[-k:]]
                ws = [w for w in words if w not in STOP]
                ini = "".join(w[0] for w in ws)
                if len(ws) >= 2 and ini.startswith(acr.lower()):
                    m[" ".join(words)] = acr
                    break
        for hit in re.finditer(r"\b([A-Z][A-Za-z0-9]{1,8})\s*\(([^()]{5,90})\)", text):
            acr, long = hit.group(1), hit.group(2)
            if _is_acr(acr) and _initials_match(acr, re.findall(r"[A-Za-z0-9]+", long.lower())):
                m[" ".join(re.findall(r"[A-Za-z0-9\-]+", long.lower()))] = acr
    return m


def apply_acr(text, mapping):
    for long in sorted(mapping, key=len, reverse=True):
        text = re.sub(r"\b" + r"[\s\-]+".join(re.escape(w) for w in long.split()) + r"\b", mapping[long], text, flags=re.I)
    return re.sub(r"\b(\w+) \(\1\)", r"\1", text)          # 'MACE (MACE)' left behind by the substitution


def _initials_match(acr, words):
    a = acr.lower()
    ws = [w for w in words if w not in STOP]
    ini = "".join(w[0] for w in ws)
    return a in ini or ini == a


def _cut(s, n=150):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


# -- one text pair --------------------------------------------------------------

def _near(x, y):
    """1 = same word spelled (nearly) the same; 0.65-0.8 = close (use / abuse); numbers never count as spellings."""
    if re.fullmatch(r"\d+(?:\.\d+)?", x) or re.fullmatch(r"\d+(?:\.\d+)?", y):
        return 0.0
    return difflib.SequenceMatcher(None, x, y).ratio()


def classify_pair(before, after):
    """Classify the difference between two versions of one item or one measure.

    Returns (kind, detail) with kind in: identical, format_only, wording_acronym, wording_spelling,
    wording_variant, threshold, logic_word, reworded.  `reworded` details give the number of content words
    replaced (n_replaced) and merely inserted or deleted (n_indel).
    """
    if before == after:
        return "identical", {}
    ab, aa = _acronyms(before), _acronyms(after)
    tb, ta = normalise(_strip_acr(before)), normalise(_strip_acr(after))
    if tb == ta:
        return ("wording_acronym" if ab != aa else "format_only"), {"acronyms_before": sorted(ab), "acronyms_after": sorted(aa)}
    ops = difflib.SequenceMatcher(None, tb, ta, autojunk=False).get_opcodes()
    dels, ins, repl = [], [], []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "delete":
            dels += tb[i1:i2]
        elif tag == "insert":
            ins += ta[j1:j2]
        elif tag == "replace":
            repl.append((tb[i1:i2], ta[j1:j2]))
    # spelling-level replacements are removed first, so a typo in a meaning-bearing word is still a typo
    only_spelling, near, real_repl, acronym_pairs = True, False, [], 0
    for a, b in repl:
        if len(a) == len(b) and all(_near(x, y) >= 0.8 for x, y in zip(a, b)):
            continue
        if len(a) == len(b) and all(_near(x, y) >= 0.65 for x, y in zip(a, b)):
            near = True          # close spelling (use / abuse): probably wording, but the meaning can differ
            continue
        if len(a) == 1 and a[0].isalpha() and len(a[0]) <= 8 and _initials_match(a[0], b):
            acronym_pairs += 1
            continue
        if len(b) == 1 and b[0].isalpha() and len(b[0]) <= 8 and _initials_match(b[0], a):
            acronym_pairs += 1
            continue
        real_repl.append((a, b))
    changed = set(dels + ins + [w for a, b in real_repl for w in a + b])
    nb, na = _nums(tb), _nums(ta)
    if sorted(nb) != sorted(na) or any(re.fullmatch(r"\d+(?:\.\d+)?", w) for w in changed):
        return "threshold", {"numbers_before": nb, "numbers_after": na, "tokens_before": tb, "tokens_after": ta}
    if changed and changed <= {"ge", "gt", "le", "lt"}:
        return "boundary", {"words": sorted(changed)}
    if changed & LOGIC:
        return "logic_word", {"words": sorted(changed & LOGIC)}
    n_repl = sum(len([w for w in a + b if w not in STOP]) for a, b in real_repl)
    n_indel = len([w for w in dels + ins if w not in STOP])
    if n_repl == 0 and n_indel == 0:
        if near:
            return "wording_variant", {"note": "near-identical words; check the meaning did not change", "needs_check": True}
        if acronym_pairs:
            return "wording_acronym", {}
        return ("wording_spelling" if repl else "wording_variant"), ({} if repl else {"note": "function words only"})
    ratio = difflib.SequenceMatcher(None, tb, ta, autojunk=False).ratio()
    return "reworded", {"content_words_changed": n_repl + n_indel, "n_replaced": n_repl, "n_indel": n_indel,
                        "ratio": round(ratio, 3)}


def _direction(section, nb, na, toks):
    """broadened / narrowed from a changed threshold, or None when it cannot be read."""
    op = next((t for t in toks if t in ("ge", "gt", "le", "lt")), None)
    if not op or len(nb) != len(na) or not nb:
        return None
    moved = [(x, y) for x, y in zip(nb, na) if x != y]
    if len(moved) != 1:
        return None
    x, y = moved[0]
    lower_minimum = op in ("ge", "gt") and y < x
    higher_maximum = op in ("le", "lt") and y > x
    looser = lower_minimum or higher_maximum
    if section == "exclusion":
        looser = not looser          # a lower exclusion cut-off excludes more people
    return "broadened" if looser else "narrowed"


# -- eligibility ----------------------------------------------------------------

def _ratio(tb, ta):
    return max(difflib.SequenceMatcher(None, tb, ta, autojunk=False).ratio(),
               difflib.SequenceMatcher(None, " ".join(tb), " ".join(ta), autojunk=False).ratio())


def _match(items_b, items_a):
    """Pair criteria across versions in stages: exact, near-identical, restructured text, then loose."""
    nb = [normalise(_strip_acr(t)) for _, t in items_b]
    na = [normalise(_strip_acr(t)) for _, t in items_a]
    pairs, used_a, done_b = [], set(), set()

    def stage(min_ratio):
        cands = sorted(((_ratio(nb[i], na[j]), i, j) for i in range(len(nb)) if i not in done_b
                        for j in range(len(na)) if j not in used_a), reverse=True)
        for r, i, j in cands:
            if r >= min_ratio and i not in done_b and j not in used_a:
                pairs.append((i, j))
                done_b.add(i)
                used_a.add(j)

    for i, tb in enumerate(nb):                      # exact (normalised) matches first
        for j, ta in enumerate(na):
            if j not in used_a and tb == ta and i not in done_b:
                pairs.append((i, j))
                done_b.add(i)
                used_a.add(j)
    stage(0.8)                                       # near-identical: typo, one word swapped
    pool_a = [w for t in na for w in t]
    pool_b = [w for t in nb for w in t]
    skip_b = {i for i in range(len(nb)) if i not in done_b and _split_of(nb[i], na)}
    skip_a = {j for j in range(len(na)) if j not in used_a and _split_of(na[j], nb)}
    done_b |= skip_b                                  # split / merged / moved text is restructured, not changed
    used_a |= skip_a
    stage(0.55)
    paired_b, paired_a = {p[0] for p in pairs}, {p[1] for p in pairs}
    return (pairs, [i for i in range(len(nb)) if i not in paired_b],
            [j for j in range(len(na)) if j not in paired_a], nb, na)


def _split_of(tokens, others):
    """True when `tokens` is (almost) wholly made of text found in other items: split, merged or moved text."""
    joined = " ".join(tokens)
    if tokens and any(joined in " ".join(o) for o in others if len(o) > len(tokens)):
        return True                                  # a short item that sits inside a longer one on the other side
    if len(tokens) < 3:
        return False
    parts = [o for o in others if len(o) >= 2 and _contained(o, tokens)]
    if not parts:
        return False
    cover = set(w for o in parts for w in o)
    return sum(1 for w in tokens if w in cover) / len(tokens) >= 0.85


def _contained(small, big):
    if not small:
        return True
    bs = set(big)
    return sum(1 for w in small if w in bs) / len(small) >= 0.85


def eligibility_findings(before_text, after_text):
    amap = acronym_map(before_text, after_text)
    ib = [(sec, apply_acr(t, amap)) for sec, t in split_items(before_text)]
    ia = [(sec, apply_acr(t, amap)) for sec, t in split_items(after_text)]
    pairs, gone, new, nb, na = _match(ib, ia)
    out = []
    all_b, all_a = [w for t in nb for w in t], [w for t in na for w in t]
    for i, j in pairs:
        sb, tb = ib[i]
        sa, ta = ia[j]
        kind, d = classify_pair(tb, ta)
        if kind == "identical":
            if sb != sa:
                out.append(dict(kind="moved_section", section=sa, substantive=True, confidence="medium",
                                before=_cut(tb), after=_cut(ta), note=f"moved from {sb} to {sa}"))
            continue
        f = dict(section=sa, before=_cut(tb), after=_cut(ta))
        if kind == "threshold":
            dr = _direction(sa, d["numbers_before"], d["numbers_after"], d["tokens_after"])
            out.append(dict(f, kind="threshold_changed", direction=dr, substantive=True, confidence="high",
                            note=f"{_fmt(d['numbers_before'])} → {_fmt(d['numbers_after'])}"))
        elif kind == "boundary":
            out.append(dict(f, kind="boundary_changed", substantive=True, confidence="medium",
                            note="inclusive / exclusive boundary changed (for example > to \u2265)"))
        elif kind == "logic_word":
            out.append(dict(f, kind="qualifier_changed", substantive=True, confidence="medium",
                            note="meaning-bearing word(s) changed: " + ", ".join(d["words"])))
        elif kind == "reworded":
            n = d["content_words_changed"]
            big = d["n_replaced"] > 0 or d["n_indel"] > 3      # a swapped content word is a real change
            out.append(dict(f, kind="reworded" if big else "wording_variant", direction="clarified" if big else None,
                            substantive=big, confidence="medium" if big else "low", needs_check=True,
                            note=f"{n} content word(s) differ; check whether the meaning changed"))
        elif kind == "wording_variant":
            out.append(dict(f, kind="wording_variant", substantive=False, confidence="medium" if d.get("needs_check") else "high",
                            needs_check=bool(d.get("needs_check")), note=d.get("note", "function words only")))
        else:
            out.append(dict(f, kind=kind, substantive=False, confidence="high"))
    for i in gone:
        s, t = ib[i]
        if _split_of(nb[i], na):
            out.append(dict(kind="restructured", section=s, substantive=False, confidence="medium",
                            before=_cut(t), note="text still present elsewhere (split, merged or moved)"))
        else:
            out.append(dict(kind="criterion_removed", section=s, direction="broadened", substantive=True,
                            confidence="high", before=_cut(t)))
    for j in new:
        s, t = ia[j]
        if _split_of(na[j], nb):
            out.append(dict(kind="restructured", section=s, substantive=False, confidence="medium",
                            after=_cut(t), note="text already present elsewhere (split, merged or moved)"))
        else:
            out.append(dict(kind="criterion_added", section=s, direction="narrowed", substantive=True,
                            confidence="high", after=_cut(t)))
    return out


def _fmt(nums):
    return ", ".join(f"{n:g}" for n in nums) or "-"


# -- structured fields ------------------------------------------------------------

def _age(s):
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else None


def age_text_check(f):
    """Notes only: structured minimum age against an age stated in the criteria text."""
    m = re.search(r"\bage[d]?\b[^.\n]{0,40}?(?:ge|>=|≥|at least|over|older than)?\s*(\d{2})\s*(?:year|yr)", (f.get("eligibility_criteria") or "").lower())
    a = _age(f.get("min_age"))
    if m and a and int(m.group(1)) != a:
        return f"age in the criteria text ({m.group(1)}) does not match the structured minimum age ({a})"
    return None


def structured_findings(fa, fb):
    out = []
    for key, label in (("min_age", "minimum age"), ("max_age", "maximum age")):
        if fa[key] != fb[key]:
            x, y = _age(fa[key]), _age(fb[key])
            dr = None
            if x is not None and y is not None:
                dr = ("broadened" if y < x else "narrowed") if key == "min_age" else ("broadened" if y > x else "narrowed")
            elif (x is None) != (y is None):      # limit added or removed
                dr = "narrowed" if y is not None else "broadened"
            out.append(dict(kind="age_limit_changed", direction=dr, substantive=True, confidence="high",
                            before=fa[key] or "none", after=fb[key] or "none", note=label))
    if fa["sex"] != fb["sex"]:
        dr = "narrowed" if fb["sex"] != "ALL" and fa["sex"] == "ALL" else ("broadened" if fb["sex"] == "ALL" else None)
        out.append(dict(kind="sex_changed", direction=dr, substantive=True, confidence="high",
                        before=fa["sex"], after=fb["sex"]))
    if fa["healthy_volunteers"] != fb["healthy_volunteers"]:
        out.append(dict(kind="healthy_volunteers_changed", substantive=True, confidence="high",
                        before=fa["healthy_volunteers"], after=fb["healthy_volunteers"]))
    return out


def enrolment_finding(fa, fb):
    try:
        x, y = float(fa["enrollment"]), float(fb["enrollment"])
    except (TypeError, ValueError):
        return []
    if x == y:
        return []
    pct = abs(y - x) / x * 100 if x else 100.0
    ta, tb = (fa.get("enrollment_type") or "").upper(), (fb.get("enrollment_type") or "").upper()
    if ta == "ESTIMATED" and tb == "ACTUAL":      # the planned target was replaced by the number actually enrolled
        return [dict(kind="actual_enrolment_recorded", substantive=False, confidence="high", before=f"{x:g} (estimated)",
                     after=f"{y:g} (actual)", note=f"{pct:.0f}% difference from the plan; not an amendment of the target")]
    return [dict(kind="sample_size_changed", direction="increased" if y > x else "decreased", substantive=True,
                 confidence="high", before=f"{x:g}", after=f"{y:g}", note=f"{pct:.0f}% change",
                 magnitude="large" if pct >= 20 else "small")]


# -- outcomes ---------------------------------------------------------------------

def _time_points(text):
    t = (text or "").lower()
    pts = set()
    for n, u in re.findall(r"(\d+(?:\.\d+)?)\s*(day|week|month|year)", t):
        pts.add(round(float(n) * UNIT_DAYS[u], 1))
    for u, n in re.findall(r"(day|week|month|year)s?\s*(\d+(?:\.\d+)?)", t):
        pts.add(round(float(n) * UNIT_DAYS[u], 1))
    return pts


def _metric_hits(text):
    t = " ".join(normalise(text))
    return {w for w in METRIC_WORDS if w in t}


def outcome_findings(ob, oa):
    """ob, oa: lists of (measure, time_frame)."""
    amap = acronym_map(*[m for m, _ in ob + oa])
    ob = [(apply_acr(m, amap), t) for m, t in ob]
    oa = [(apply_acr(m, amap), t) for m, t in oa]
    nb = [normalise(m) for m, _ in ob]
    na = [normalise(m) for m, _ in oa]
    pairs, used = [], set()
    for i, t in enumerate(nb):
        for j, u in enumerate(na):
            if j not in used and t == u:
                pairs.append((i, j))
                used.add(j)
                break
    taken = {i for i, _ in pairs}
    cands = sorted(((difflib.SequenceMatcher(None, nb[i], na[j], autojunk=False).ratio(), i, j)
                    for i in range(len(nb)) if i not in taken for j in range(len(na)) if j not in used), reverse=True)
    for r, i, j in cands:
        if r >= 0.6 and i not in taken and j not in used:
            pairs.append((i, j))
            taken.add(i)
            used.add(j)
    out = []
    for i, j in pairs:
        (mb, tb), (ma, ta) = ob[i], oa[j]
        kind, d = classify_pair(mb, ma)
        f = dict(before=_cut(mb), after=_cut(ma))
        if kind not in ("identical", "format_only", "wording_acronym", "wording_spelling", "wording_variant"):
            hb, ha = _metric_hits(mb), _metric_hits(ma)
            if hb != ha:
                out.append(dict(f, kind="outcome_metric_changed", substantive=True, confidence="medium",
                                note="metric wording differs: " + ", ".join(sorted(hb ^ ha))))
            elif kind == "threshold":
                out.append(dict(f, kind="outcome_metric_changed", substantive=True, confidence="high",
                                note=f"cut-off or number changed: {_fmt(d['numbers_before'])} → {_fmt(d['numbers_after'])}"))
            else:
                small = d.get("n_replaced", 0) == 0 and d.get("n_indel", 0) <= 3     # detail added, nothing swapped
                out.append(dict(f, kind="outcome_wording" if small else "outcome_variable_changed",
                                substantive=not small, confidence="low" if small else "medium", needs_check=True,
                                note=("detail added or removed; check whether the variable itself changed"
                                      if small else "the measured variable appears to differ")))
        elif kind in ("wording_acronym", "wording_spelling", "wording_variant", "format_only"):
            out.append(dict(f, kind="outcome_wording", substantive=False, confidence="high", note=kind, wtype=kind))
        if tb != ta:
            pb, pa = _time_points(tb), _time_points(ta)
            if pb != pa and (pb or pa):
                out.append(dict(before=_cut(tb), after=_cut(ta), kind="outcome_timepoint_changed", substantive=True,
                                confidence="high", note="time point differs"))
            elif normalise(tb) != normalise(ta):
                out.append(dict(before=_cut(tb), after=_cut(ta), kind="outcome_wording", substantive=False,
                                confidence="medium", note="time frame reworded, same time points"))
    for i in range(len(ob)):
        if i not in taken:
            out.append(dict(kind="outcome_removed", substantive=True, confidence="high", before=_cut(ob[i][0])))
    for j in range(len(oa)):
        if j not in used:
            out.append(dict(kind="outcome_added", substantive=True, confidence="high", after=_cut(oa[j][0])))
    return out


# -- design ------------------------------------------------------------------------

def design_findings(fa, fb):
    out = []
    for key, label in (("arms", "arm groups"), ("interventions", "interventions")):
        sa = {" ".join(normalise(l.split(" | ")[0])) for l in fa[key].splitlines() if l.strip()}
        sb = {" ".join(normalise(l.split(" | ")[0])) for l in fb[key].splitlines() if l.strip()}
        if sa != sb:
            kind, d = classify_pair("\n".join(sorted(sa)), "\n".join(sorted(sb)))
            sub = kind in ("reworded", "threshold", "logic_word") or len(sa) != len(sb)
            out.append(dict(kind="design_changed", substantive=sub, confidence="medium" if sub else "low",
                            before=_cut("; ".join(sorted(sa))), after=_cut("; ".join(sorted(sb))), note=label,
                            needs_check=not sub))
    return out


# -- whole pair -------------------------------------------------------------------

def parse_outcomes(f):
    out = []
    for line in f.get("primary_outcomes", "").splitlines():
        if line.strip():
            m, _, tf = line.partition(" | ")
            out.append((m.strip(), tf.strip()))
    return out


KIND_TYPES = {  # finding kind (+ direction) -> labelling-form change type id
    ("criterion_added", None): "elig_narrowed", ("criterion_removed", None): "elig_broadened",
    ("threshold_changed", "broadened"): "elig_broadened", ("threshold_changed", "narrowed"): "elig_narrowed",
    ("threshold_changed", None): "elig_clarified", ("qualifier_changed", None): "elig_clarified", ("boundary_changed", None): "elig_clarified",
    ("reworded", None): "elig_clarified", ("moved_section", None): "elig_clarified",
    ("age_limit_changed", None): "age_sex", ("sex_changed", None): "age_sex", ("healthy_volunteers_changed", None): "age_sex",
    ("outcome_added", None): "outcome_added_removed", ("outcome_removed", None): "outcome_added_removed",
    ("outcome_variable_changed", None): "outcome_variable", ("outcome_metric_changed", None): "outcome_metric",
    ("outcome_timepoint_changed", None): "outcome_timepoint", ("sample_size_changed", None): "sample_size",
    ("design_changed", None): "design_arms", ("wording_spelling", None): "wording_spelling",
    ("wording_acronym", None): "wording_acronym", ("format_only", None): "wording_format",
    ("wording_variant", None): "wording_rephrase", ("outcome_wording", None): "wording_rephrase",
}
LABELS = {
    "criterion_added": "Criterion added", "criterion_removed": "Criterion removed",
    "threshold_changed": "Threshold changed", "qualifier_changed": "Qualifier changed", "boundary_changed": "Boundary changed (> vs \u2265)",
    "reworded": "Criterion reworded (content words differ)", "wording_variant": "Wording variant",
    "wording_spelling": "Spelling / grammar", "wording_acronym": "Acronym introduced or expanded",
    "format_only": "Format / symbols / units only", "restructured": "Restructured (same content)", "restructured_summary": "Restructured",
    "moved_section": "Moved between inclusion and exclusion", "age_limit_changed": "Age limit changed",
    "sex_changed": "Sex setting changed", "healthy_volunteers_changed": "Healthy-volunteer setting changed",
    "sample_size_changed": "Enrolment target changed", "actual_enrolment_recorded": "Actual enrolment recorded", "design_changed": "Arms / interventions changed",
    "outcome_added": "Primary outcome added", "outcome_removed": "Primary outcome removed",
    "outcome_variable_changed": "Outcome variable changed", "outcome_metric_changed": "Outcome metric / cut-off changed",
    "outcome_timepoint_changed": "Outcome time point changed", "outcome_wording": "Outcome wording",
}


def analyse(fa, fb):
    """All findings between two normalised version-field dicts (derive.version_fields output)."""
    f = []
    f += eligibility_findings(fa["eligibility_criteria"], fb["eligibility_criteria"])
    f += structured_findings(fa, fb)
    f += outcome_findings(parse_outcomes(fa), parse_outcomes(fb))
    f += enrolment_finding(fa, fb)
    f += design_findings(fa, fb)
    notes = [n for n in (age_text_check(fb),) if n]
    return {"findings": f, "notes": notes}


def suggest(findings):
    types = []
    for x in findings:
        t = KIND_TYPES.get((x["kind"], x.get("direction"))) or KIND_TYPES.get((x["kind"], None))
        if x["kind"] == "outcome_wording" and x.get("wtype"):
            t = KIND_TYPES.get((x["wtype"], None), t)
        if t and (x["substantive"] or t.startswith("wording")) and t not in types:
            types.append(t)
    subs = [x for x in findings if x["substantive"]]
    major_kinds = {"criterion_added", "criterion_removed", "threshold_changed", "outcome_added", "outcome_removed",
                   "outcome_variable_changed", "outcome_metric_changed", "outcome_timepoint_changed", "age_limit_changed",
                   "sex_changed", "design_changed", "moved_section", "qualifier_changed"}
    major = any(x["kind"] in major_kinds or (x["kind"] == "sample_size_changed" and x.get("magnitude") == "large")
                for x in subs)
    sev = "major" if major else ("minor" if subs else "none")
    return types, sev


def provisional(analysis, checked=None):
    """The provisional label: label, confidence, one-line summary, and every finding as readable text."""
    findings, notes = analysis["findings"], analysis["notes"]
    subs = [x for x in findings if x["substantive"]]
    checks = [x for x in findings if x.get("needs_check") and not x["substantive"]]
    if subs:
        label = "positive"
        conf = "high" if any(x["confidence"] == "high" for x in subs) else "medium"
    else:
        label = "negative"
        conf = "medium" if checks else "high"
    types, sev = suggest(findings)
    lines = ["Checked: " + (checked or "eligibility text, age/sex, primary outcomes, enrolment, arms and interventions") + "."]
    if not findings:
        lines.append("Identical after normalising case, spacing, punctuation, markup, symbols and units. No change.")
    else:
        lines.append(f"{len(subs)} substantive and {len(findings) - len(subs)} non-substantive finding(s):")
        restructured = [x for x in findings if x["kind"] == "restructured"]
        listed = [x for x in findings if x["kind"] != "restructured"]
        if restructured:
            listed.append(dict(kind="restructured_summary", substantive=False,
                               note=f"{len(restructured)} item(s) split, merged or moved without changing content"))
        for n, x in enumerate(sorted(listed, key=lambda y: not y["substantive"])[:12], 1):
            tag = "SUBSTANTIVE" if x["substantive"] else "minor"
            head = LABELS.get(x["kind"], x["kind"]) + (f" [{x['section']}]" if x.get("section") else "")
            if x.get("direction"):
                head += f", {x['direction']}"
            body = ""
            if x.get("before") and x.get("after"):
                body = f': "{x["before"]}" → "{x["after"]}"'
            elif x.get("before"):
                body = f': "{x["before"]}"'
            elif x.get("after"):
                body = f': "{x["after"]}"'
            lines.append(f"{n}. {tag} · {head}{body}" + (f" ({x['note']})" if x.get("note") else ""))
        if len(listed) > 12:
            lines.append(f"+{len(listed) - 12} more not listed")
    if checks:
        lines.append("Check yourself: " + "; ".join(sorted({x["note"] for x in checks if x.get("note")})) + ".")
    lines += [f"Note: {n}." for n in notes]
    if findings:
        lines.append("Suggested types: " + (", ".join(types) or "none") + f" · severity: {sev}.")
    lines.append("Not examined: why the change was made, protocol text outside these registry fields.")
    summary = ("no meaningful change" if label == "negative" else f"{len(subs)} substantive change(s)")
    return {"label": label, "confidence": conf, "source": "rule-based change analysis", "summary": summary,
            "evidence": "\n".join(lines), "suggested_types": types, "suggested_severity": sev,
            "kinds": sorted({x["kind"] for x in findings}), "n_substantive": len(subs)}
