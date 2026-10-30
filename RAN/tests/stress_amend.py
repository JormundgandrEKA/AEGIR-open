"""Metamorphic stress test of amend.py on every stored real eligibility text (not part of the unit-test run).

Non-substantive edits must NOT produce substantive findings; substantive edits must. Prints false-alarm and miss rates
per edit type and writes the failures to a JSON file for review.  Usage: python RAN/tests/stress_amend.py [seed]
"""
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import aegir_ran  # noqa: E402,F401  (puts ../shared on the path)
from aegir_ran import amend, ctgov, derive  # noqa: E402
from aegir_core.context import Ctx  # noqa: E402
from aegir_core.textclean import clean_text  # noqa: E402

NL = chr(10)
ctx = Ctx(HERE.parent.parent)
rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 28)


def texts():
    out = []
    for d in sorted((ctx.root / "data" / "raw" / "ctgov" / "history").iterdir()):
        for v, p in sorted(ctgov.stored_versions(ctx, d.name).items()):
            t = derive.version_fields(json.loads(p.read_text(encoding="utf-8")))["eligibility_criteria"]
            if len(t.split()) >= 40:
                out.append((d.name, v, t))
    return out


def lines_of(t):
    return t.split(NL)


def item_idx(ls, minw=6):
    return [i for i, l in enumerate(ls) if len(l.split()) >= minw and l.strip().startswith("•")] or \
           [i for i, l in enumerate(ls) if len(l.split()) >= minw]


# ---- non-substantive edits ----
def upper(t):
    return t.upper()


def spaces(t):
    return re.sub(r"[ ]+", "  ", t).replace(NL, NL + " ")


def md_bullets(t):
    return clean_text(t.replace("• ", "* "))      # the pipeline always cleans markup before analysis


def html_wrap(t):
    out = []
    for l in lines_of(t):
        if not l.strip():
            continue
        if l.strip().startswith("•"):
            out.append(f"<ul><li>{l.strip().lstrip(chr(8226)).strip()}</li></ul>")
        else:
            out.append(f"<p>{l.strip()}</p>")
    return clean_text("".join(out))


def symbols(t):
    return t.replace("≥", ">=").replace("≤", "<=")


def typo(t):
    ls = lines_of(t)
    idx = item_idx(ls)
    if not idx:
        return None
    i = rng.choice(idx)
    ws = ls[i].split(" ")
    cand = [k for k, w in enumerate(ws) if len(w) >= 7 and w.isalpha()]
    if not cand:
        return None
    k = rng.choice(cand)
    w = ws[k]
    j = rng.randrange(1, len(w) - 2)
    ws[k] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    ls[i] = " ".join(ws)
    return NL.join(ls)


def acronym(t):
    ls = lines_of(t)
    idx = item_idx(ls)
    if not idx:
        return None
    i = rng.choice(idx)
    ws = ls[i].split(" ")
    k = rng.randrange(1, min(4, len(ws)))
    ws[k] = ws[k] + " (ABX)"
    ls[i] = " ".join(ws)
    return NL.join(ls)


def punct(t):
    return re.sub(r"(?<!\d)\.(?=\s|$)", "", t).replace(", ", " , ")


def reorder(t):
    """Swap two criteria inside the same section (moving across sections would be a real change)."""
    ls = lines_of(t)
    idx = item_idx(ls)
    split = next((k for k, l in enumerate(ls) if l.lower().startswith("exclusion")), len(ls))
    idx = [i for i in idx if i < split] if sum(i < split for i in idx) >= 2 else [i for i in idx if i > split]
    if len(idx) < 2:
        return None
    a, b = rng.sample(idx, 2)
    ls[a], ls[b] = ls[b], ls[a]
    return NL.join(ls)


NON = {"uppercase": upper, "whitespace": spaces, "markdown_bullets": md_bullets, "html_roundtrip": html_wrap,
       "symbols": symbols, "typo": typo, "acronym_added": acronym, "punctuation": punct, "reorder_in_place": reorder}


# ---- substantive edits ----
def drop_line(t):
    ls = lines_of(t)
    idx = item_idx(ls, 6)
    if not idx:
        return None
    del ls[rng.choice(idx)]
    return NL.join(ls)


def add_line(t):
    ls = lines_of(t)
    idx = item_idx(ls, 6)
    if not idx:
        return None
    ls.insert(rng.choice(idx), "• Participants with a documented history of myocardial infarction within the past 6 months")
    return NL.join(ls)


def change_number(t):
    ls = lines_of(t)
    idx = [i for i, l in enumerate(ls) if re.search(r"(?<![\w.])\d{2,3}(?![\w.])", l)]
    if not idx:
        return None
    i = rng.choice(idx)
    ls[i] = re.sub(r"(?<![\w.])(\d{2,3})(?![\w.])", lambda m: str(int(m.group(1)) + 20), ls[i], count=1)
    return NL.join(ls)


def swap_word(t):
    ls = lines_of(t)
    idx = item_idx(ls)
    if not idx:
        return None
    i = rng.choice(idx)
    ws = ls[i].split(" ")
    cand = [k for k, w in enumerate(ws) if len(w) >= 7 and w.isalpha()]
    if not cand:
        return None
    ws[rng.choice(cand)] = "pneumonia"
    ls[i] = " ".join(ws)
    return NL.join(ls)


def drop_negation(t):
    if not re.search(r"\b(no|not|without)\b", t, re.I):
        return None
    return re.sub(r"\b(no|not|without)\b ", "", t, count=1, flags=re.I)


SUB = {"drop_line": drop_line, "add_line": add_line, "change_number": change_number, "swap_word": swap_word,
       "drop_negation": drop_negation}


def fields(t):
    return {"eligibility_criteria": t, "min_age": "18 Years", "max_age": "", "sex": "ALL", "healthy_volunteers": "False",
            "primary_outcomes": "", "enrollment": "", "enrollment_type": "", "arms": "", "interventions": ""}


def main():
    t0 = time.time()
    data = texts()
    print(f"{len(data)} real eligibility texts")
    stat = defaultdict(lambda: [0, 0])      # kind -> [tests, flagged substantive]
    fails = defaultdict(list)
    for nct, v, t in data:
        for kind, fn in list(NON.items()) + list(SUB.items()):
            e = fn(t)
            if e is None or e == t:
                continue
            res = amend.analyse(fields(t), fields(e))
            subs = [f for f in res["findings"] if f["substantive"]]
            stat[kind][0] += 1
            stat[kind][1] += bool(subs)
            wrong = bool(subs) if kind in NON else not subs
            if wrong and len(fails[kind]) < 12:
                fails[kind].append({"nct": nct, "version": v, "findings": [(f["kind"], f.get("before", "")[:90], f.get("after", "")[:90]) for f in (subs or res["findings"])][:3]})
    print(f"{time.time() - t0:.0f}s")
    print(f"{'edit':20s} {'tests':>6s} {'flagged substantive':>20s}")
    for kind in list(NON) + list(SUB):
        n, f = stat[kind]
        if n:
            tag = "FALSE ALARM" if kind in NON else "DETECTED"
            rate = f / n if kind in NON else f / n
            print(f"{kind:20s} {n:6d} {f:6d} ({rate:6.1%})  <- {tag} rate")
    out = ctx.root / "data" / "derived" / f"amend_stress_seed{sys.argv[1] if len(sys.argv) > 1 else 28}.json"
    out.write_text(json.dumps({"stat": stat, "failures": fails}, indent=1, ensure_ascii=True), encoding="utf-8")
    print("failures written to", out)


if __name__ == "__main__":
    main()
