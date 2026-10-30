"""Human spot-checks at scale: sampling plans and the audit log (append-only jsonl per labeller).

Three ways to supervise, from fine to coarse:
- trial verdicts      (kind "trial"):  agree / disagree / unsure on one trial's label;
- screens             : a sheet of cards, all assumed right unless flagged (exception-based review), logged as trial verdicts;
- rule review         (kind "rule"):   a verdict on a whole rule from a sample of the trials it fired on.
Canary cards (curated texts with a deliberately wrong label, about 1 in 12) measure how closely a screen was read; they never enter a precision.
"""
import hashlib
import json
import random

from .core import Paths, iso_now, iter_jsonl, utc_stamp
from . import opentargets


def audit_file(paths, labeller):
    d = paths.data / "labels" / labeller
    d.mkdir(parents=True, exist_ok=True)
    return d / "autoran_audit.jsonl"


def append(paths, labeller, rec):
    rec = dict(rec)
    rec.setdefault("ts", iso_now())
    with open(audit_file(paths, labeller), "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=True) + "\n")


def checked(paths, labeller):
    """{nct: latest trial verdict} for one labeller."""
    f = audit_file(paths, labeller)
    out = {}
    if f.is_file():
        for r in iter_jsonl(f):
            if r.get("kind") == "trial":
                out[r["nct_id"]] = r
    return out


def draw(ctx, cfg, n=200, klass="positive_recruitment", seed=28):
    """Seeded sample of NCT ids of one class, written as a plan file the dashboard can open."""
    paths = Paths(ctx.root).ensure()
    f = paths.latest("index_*.jsonl")
    if not f:
        raise FileNotFoundError("no index yet; run `autoran metrics`")
    pool = [r[0] for r in iter_jsonl(f) if r[3] == klass]
    rnd = random.Random(seed)
    rnd.shuffle(pool)
    pick = sorted(pool[:n])
    out = paths.derived / f"audit_plan_{klass}_{utc_stamp()}.json"
    out.write_text(json.dumps({"class": klass, "seed": seed, "n": len(pick), "population": len(pool), "nct_ids": pick}), encoding="utf-8")
    ctx.notes["population"] = len(pool)
    return {"file": str(out), "n": len(pick)}


# -- canaries -------------------------------------------------------------------------------

def canaries(paths, n, seed):
    """n pseudo-cards: real curated stop-reason texts shown with a label of a DIFFERENT class (the reviewer should flag them)."""
    rows = [r for r in opentargets.load(paths) if r["split"] == "dev" and len(r["labels"]) == 1]
    rnd = random.Random(seed)
    rnd.shuffle(rows)
    out = []
    classes = sorted({c for r in rows for c in r["labels"]})
    for r in rows[:n]:
        wrong = rnd.choice([c for c in classes if c not in r["labels"]])
        fake = "NCT0" + hashlib.sha256(f"{seed}|{r['i']}".encode()).hexdigest()[:7].translate(str.maketrans("abcdef", "123456"))
        out.append({"nct": fake, "canary": True, "title": "(curated example)", "status": "TERMINATED", "class": "other_stop",
                    "stop_class": wrong, "why_stopped": r["text"][:240], "true_labels": r["labels"], "label_source": "rules", "conf": 0.9})
    return out
