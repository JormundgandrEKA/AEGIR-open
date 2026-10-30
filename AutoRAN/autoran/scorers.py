"""Scorers: plug-ins that rate a trial's chance of failing to recruit from INPUT fields only.

The loader hands a scorer a filtered view (`input_view`): never status, whyStopped, completion dates, actual enrolment,
references or anything posted after the start. A unit test pins the allow-list.

Built in: random (sanity, AUROC about 0.5), criteria_count, logistic (tabular), logistic_text (tabular + hashed title and
condition words). External scorers (for example the AEGIR review engine) write `data/derived/scores/<name>/<split>.jsonl`
with lines {"nct_id", "score"}; they are read like any other scorer.
"""
import json
import math
import random
import zlib
from pathlib import Path

from .core import Paths, iso_now, iter_jsonl, stable_hash, utc_stamp, write_jsonl, year_of

ALLOWED = ("nct_id", "title", "phases", "sponsor_class", "start", "n_sites", "countries", "eligibility", "n_primary", "n_arms",
           "allocation", "masking", "purpose", "intervention_types", "conditions", "mesh", "ancestors", "input_state")
FORBIDDEN = ("status", "why_stopped", "completion", "primary_completion", "last_update", "first_posted", "enrollment", "pmids",
             "page", "pos", "class", "stop_classes", "stop_class", "source", "grade")
BINARY = ("positive_recruitment", "negative_completed")


def input_view(rec):
    """The only fields a scorer may see."""
    return {k: rec[k] for k in ALLOWED if k in rec}


def iter_joined(paths):
    """Stream (trial, label, category) triples. The three stage files are written in the same order, which is asserted."""
    files = []
    for pat, stage in (("trials_*.jsonl", "normalise"), ("labels_*.jsonl", "label"), ("cats_*.jsonl", "categorize")):
        f = paths.latest(pat)
        if f is None:
            raise ValueError(f"no {stage} output yet; run `autoran {stage}` first (order: fetch, labeller-data, normalise, label, categorize, score, metrics)")
        files.append(f)
    t, l, c = (iter_jsonl(f) for f in files)
    for a, b, d in zip(t, l, c):
        if not (a["nct_id"] == b["nct_id"] == d["nct_id"]):
            raise ValueError("stage files out of step; rerun label and categorize after normalise")
        yield a, b, d


# -- features --------------------------------------------------------------------------

def _h(token, dim=2048):
    return zlib.crc32(token.encode("utf-8")) % dim


def featurize(v, text=False):
    e = v["eligibility"]
    f = {"n_incl": math.log1p(e["n_incl"]), "n_excl": math.log1p(e["n_excl"]), "n_words": math.log1p(e["n_words"]) / 3,
         "log_sites": math.log1p(v["n_sites"]), "n_countries": math.log1p(len(v["countries"])), "n_primary": math.log1p(v["n_primary"]),
         "n_arms": math.log1p(v["n_arms"])}
    mn, mx = e.get("min_age_y"), e.get("max_age_y")
    f["has_min_age"], f["has_max_age"] = float(mn is not None), float(mx is not None)
    f["min_age"] = (mn or 0) / 50
    f["max_age"] = (mx if mx is not None else 100) / 50
    f["age_span"] = ((mx if mx is not None else 100) - (mn or 0)) / 100
    hv = e.get("healthy_volunteers")
    f["hv_yes"], f["hv_missing"] = float(hv is True), float(hv is None)
    y = year_of(v.get("start"))
    f["year"] = ((y or 2015) - 2015) / 5
    f["year_missing"] = float(y is None)
    f["phase=" + "/".join(v["phases"] or ["NA"])] = 1.0
    f["sponsor=" + (v["sponsor_class"] or "UNKNOWN")] = 1.0
    f["mask=" + (v["masking"] or "UNKNOWN")] = 1.0
    f["alloc=" + (v["allocation"] or "UNKNOWN")] = 1.0
    f["purpose=" + (v["purpose"] or "UNKNOWN")] = 1.0
    f["sex=" + (e.get("sex") or "UNKNOWN")] = 1.0
    for t in v["intervention_types"]:
        f["itype=" + t] = 1.0
    from .categorize import TOP
    for a in v["ancestors"] + v["mesh"]:
        if a in TOP:
            f["area=" + a] = 1.0
    if text:
        for tok in set((v["title"] + " " + " ".join(v["conditions"]) + " " + " ".join(v["mesh"])).lower().split()):
            if len(tok) > 2:
                f["w%d" % _h(tok)] = 0.5
    return f


class Scorer:
    name = "base"
    trained = False

    def fit(self, rows):
        """rows: list of (view, y)."""

    def score(self, view):
        raise NotImplementedError

    def explain(self, view, k=6):
        return []


class RandomScorer(Scorer):
    name = "random"

    def score(self, view):
        return stable_hash(view["nct_id"], "random-scorer")


class CriteriaCount(Scorer):
    name = "criteria_count"

    def score(self, view):
        e = view["eligibility"]
        return float(e["n_incl"] + e["n_excl"])

    def explain(self, view, k=6):
        e = view["eligibility"]
        return [{"feature": "eligibility criteria", "value": e["n_incl"] + e["n_excl"], "contribution": None}]


class Logistic(Scorer):
    trained = True

    def __init__(self, name="logistic", text=False, epochs=12, lr=0.08, l2=1e-5, seed=28):
        self.name, self.text, self.epochs, self.lr, self.l2, self.seed = name, text, epochs, lr, l2, seed
        self.w, self.b = {}, 0.0

    def fit(self, rows):
        rnd = random.Random(self.seed)
        data = [(featurize(v, self.text), y) for v, y in rows]
        npos = sum(y for _, y in data)
        self.b = math.log((npos + 1) / (len(data) - npos + 1))
        w = self.w
        for ep in range(self.epochs):
            rnd.shuffle(data)
            lr = self.lr / math.sqrt(1 + ep)
            for f, y in data:
                z = self.b + sum(w.get(k, 0.0) * x for k, x in f.items())
                p = 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
                g = p - y
                self.b -= lr * g * 0.1
                for k, x in f.items():
                    w[k] = w.get(k, 0.0) - lr * (g * x + self.l2 * w.get(k, 0.0))
        return self

    def raw(self, view):
        f = featurize(view, self.text)
        return self.b + sum(self.w.get(k, 0.0) * x for k, x in f.items())

    def score(self, view):
        return 1 / (1 + math.exp(-max(-30.0, min(30.0, self.raw(view)))))

    def explain(self, view, k=6):
        f = featurize(view, self.text)
        c = [(self.w.get(n, 0.0) * x, n, x) for n, x in f.items() if not (n.startswith("w") and n[1:].isdigit())]
        c.sort(key=lambda t: -abs(t[0]))
        return [{"feature": n, "value": round(x, 3), "contribution": round(v, 3)} for v, n, x in c[:k]]

    def dump(self):
        return {"name": self.name, "text": self.text, "bias": self.b, "weights": {k: round(v, 5) for k, v in self.w.items() if abs(v) > 1e-4}}

    @classmethod
    def load(cls, d):
        m = cls(d["name"], d["text"])
        m.b, m.w = d["bias"], d["weights"]
        return m


REGISTRY = {"random": lambda: RandomScorer(), "criteria_count": lambda: CriteriaCount(),
            "logistic": lambda: Logistic("logistic", text=False), "logistic_text": lambda: Logistic("logistic_text", text=True)}


def score_all(ctx, cfg, names=None):
    """Train what needs training on the train split, then score every binary-task trial (all splits), one pass each."""
    paths = Paths(ctx.root).ensure()
    names = names or list(REGISTRY)
    rnd = random.Random(cfg["bootstrap"]["seed"])
    pos, negs, seen_neg, cap = [], [], 0, 40000
    for rec, lab, cat in iter_joined(paths):          # pass 1: the training sample (all positives, a seeded reservoir of negatives)
        if cat["split"] != "train" or lab["class"] not in BINARY:
            continue
        if lab["class"] == "positive_recruitment":
            pos.append(input_view(rec))
        else:
            seen_neg += 1
            if len(negs) < cap:
                negs.append(input_view(rec))
            else:
                k = rnd.randrange(seen_neg)
                if k < cap:
                    negs[k] = input_view(rec)
    npos = len(pos)
    train = [(v, 1) for v in pos] + [(v, 0) for v in negs]
    stamp = utc_stamp()
    models, outputs = {}, {}
    for n in names:
        sc = REGISTRY[n]()
        if sc.trained:
            sc.fit(train)
            # the training sample under-represents negatives; shift the bias back so scores read as probabilities
            sc.b += math.log(max(1, len([1 for _, y in train if y == 0])) / max(1, seen_neg))
            models[n] = sc
            (paths.derived / f"model_{n}_{stamp}.json").write_text(json.dumps(sc.dump()), encoding="utf-8")
        else:
            models[n] = sc
        outputs[n] = open(paths.derived / f"scores_{n}_{stamp}.jsonl", "xb")
    n_rows = 0
    for rec, lab, cat in iter_joined(paths):          # pass 2: score everything in the binary task
        if lab["class"] not in BINARY:
            continue
        v = input_view(rec)
        n_rows += 1
        for n, sc in models.items():
            outputs[n].write((json.dumps({"nct_id": rec["nct_id"], "score": round(sc.score(v), 6)}, separators=(",", ":")) + "\n").encode("utf-8"))
    for f in outputs.values():
        f.close()
    ctx.store.append("autoran_stages.jsonl", {"stage": "score", "scorers": names, "stamp": stamp, "n": n_rows, "train_rows": len(train), "ts": iso_now()})
    ctx.count("scored", n_rows)
    return {"stamp": stamp, "scorers": names, "rows": n_rows, "train_rows": len(train), "train_positives": npos}


def load_scores(paths):
    """{scorer: {nct: score}} from the newest scores file per scorer plus external scorers in data/derived/scores/<name>/."""
    out = {}
    for f in sorted(paths.derived.glob("scores_*.jsonl")):
        name = f.name[len("scores_"):].rsplit("_", 1)[0]
        out[name] = {r["nct_id"]: r["score"] for r in iter_jsonl(f)}     # later files overwrite earlier: newest wins
    ext = paths.data / "derived" / "scores"
    if ext.is_dir():
        for d in sorted(p for p in ext.iterdir() if p.is_dir()):
            m = {}
            for f in sorted(d.glob("*.jsonl")):
                for r in iter_jsonl(f):
                    m[r["nct_id"]] = r["score"]
            if m:
                out["ext:" + d.name] = m
    return out
