"""`autoran label`: build the stop-reason labeller from the curated Open Targets set (measured on its frozen test part),
then label every trial with an outcome class and a stop class. One JSON manifest per build; one jsonl of labels per run."""
import json
import math

from . import __version__, labeller as L
from .core import Paths, iso_now, iter_jsonl, utc_stamp, write_jsonl
from .normalise import load_trials
from .opentargets import load, normalise_reason

UNINFORMATIVE = {"No_Context", "Invalid_Reason"}


def _ie(pred_classes):
    return "Insufficient_Enrollment" in pred_classes


def _combo_metrics(rows, rule_fn, nb, mode):
    tp = fp = fn = 0
    for r in rows:
        a = _ie(rule_fn(r["text"]))
        b = _ie(nb.predict(r["text"])[0])
        pred = {"rules": a, "nb": b, "and": a and b, "or": a or b}[mode]
        gold = "Insufficient_Enrollment" in r["labels"]
        tp += pred and gold
        fp += pred and not gold
        fn += (not pred) and gold
    p, rc, f = L.prf(tp, fp, fn)
    return {"precision": round(p, 4), "recall": round(rc, 4), "f1": round(f, 4), "tp": tp, "fp": fp, "fn": fn}


def build(ctx, cfg):
    paths = Paths(ctx.root).ensure()
    rows = load(paths)
    if not rows:
        raise FileNotFoundError("no Open Targets data; run `autoran labeller-data` first")
    train = [r for r in rows if r["split"] == "train"]
    dev = [r for r in rows if r["split"] == "dev"]
    test = [r for r in rows if r["split"] == "test"]
    rule_fn = lambda t: L.classify_rules(t)[0]
    # model developed on train, thresholds tuned on dev, scored once on test
    nb = L.NB().train(train, L.CLASSES)
    nb.tune(dev, L.CLASSES)
    nb_fn = lambda t: nb.predict(t)[0]
    modes = ["rules", "nb", "and", "or"]
    dev_combo = {m: _combo_metrics(dev, rule_fn, nb, m) for m in modes}
    # choose: best F1 among modes whose dev precision clears the floor (config); if none do, the highest precision
    floor = cfg.get("labeller", {}).get("ie_dev_precision_floor", 0.93)
    ok = [m for m in modes if dev_combo[m]["precision"] >= floor]
    choice = max(ok, key=lambda m: dev_combo[m]["f1"]) if ok else max(modes, key=lambda m: dev_combo[m]["precision"])
    test_combo = {m: _combo_metrics(test, rule_fn, nb, m) for m in modes}
    metrics = {
        "rules": {"dev": L.evaluate(dev, rule_fn), "test": L.evaluate(test, rule_fn)},
        "nb": {"dev": L.evaluate(dev, nb_fn), "test": L.evaluate(test, nb_fn)},
        "ie_combos": {"dev": dev_combo, "test": test_combo, "chosen": choice},
        "sizes": {"train": len(train), "dev": len(dev), "test": len(test)}}
    # production model: same recipe on train+dev (thresholds kept from the dev tuning)
    prod = L.NB().train(train + dev, L.CLASSES)
    prod.thresh = dict(nb.thresh)
    manifest = {"version": __version__, "built": iso_now(), "choice_ie": choice, "metrics": metrics,
                "rule_table": L.rule_table(train + dev), "nb": prod.dump(),
                "exact_index_size": len({normalise_reason(r["text"]) for r in rows}),
                "source": {"name": "Open Targets clinical_trial_reason_to_stop", "licence": "apache-2.0", "grade": "B-",
                           "rows": len(rows)}}
    out = paths.derived / f"labeller_{utc_stamp()}.json"
    out.write_text(json.dumps(manifest, ensure_ascii=True), encoding="utf-8")
    ctx.store.append("autoran_stages.jsonl", {"stage": "labeller", "file": ctx.store.rel(out), "ts": iso_now(), "choice_ie": choice})
    ie = metrics["rules"]["test"]["per_class"]["Insufficient_Enrollment"]
    ctx.notes["ie_test_rules"] = {k: ie[k] for k in ("precision", "recall", "f1")}
    ctx.notes["ie_combo_test"] = test_combo
    ctx.notes["choice_ie"] = choice
    return out, manifest


def load_labeller(paths):
    f = paths.latest("labeller_*.json")
    if not f:
        return None
    return json.loads(f.read_text(encoding="utf-8")), f


class Labeller:
    """Applies the three tiers to one whyStopped text."""

    def __init__(self, manifest, ot_rows):
        self.m = manifest
        self.nb = L.NB.load(manifest["nb"])
        self.exact = {}
        for r in ot_rows:
            self.exact.setdefault(normalise_reason(r["text"]), r["labels"])
        self.rule_prec = {rid: (v["precision"] if v["precision"] is not None else 0.5) for rid, v in manifest["rule_table"].items()}
        self.choice = manifest["choice_ie"]

    def label(self, raw):
        text = normalise_reason(raw)
        if not text:
            return {"stop_classes": [], "label_source": "none", "confidence": 0.0, "rule_ids": [], "span": None, "disagree": False}
        if text in self.exact:
            cl = list(self.exact[text])
            return {"stop_classes": cl, "label_source": "exact", "confidence": 1.0, "rule_ids": [], "span": None, "disagree": False}
        r_cl, r_ids, span = L.classify_rules(raw)
        n_cl, sc = self.nb.predict(raw)
        r_ie, n_ie = "Insufficient_Enrollment" in r_cl, "Insufficient_Enrollment" in n_cl
        ie = {"rules": r_ie, "nb": n_ie, "and": r_ie and n_ie, "or": r_ie or n_ie}[self.choice]
        classes = sorted(set(r_cl) - {"Insufficient_Enrollment"})
        src = "rules"
        if not r_cl and n_cl:
            classes, src = sorted(set(n_cl) - {"Insufficient_Enrollment"}), "nb"
        if ie:
            classes = sorted(set(classes) | {"Insufficient_Enrollment"})
        conf = max([self.rule_prec.get(i, 0.5) for i in r_ids] or [0.0]) if src == "rules" else \
            round(0.5 + 0.5 * math.tanh((sc.get("Insufficient_Enrollment", 0) - self.nb.thresh.get("Insufficient_Enrollment", 0)) / 4), 3)
        if self.choice == "or" and r_ie != n_ie:
            conf = min(conf, 0.75)
        return {"stop_classes": classes, "label_source": src, "confidence": round(conf, 3), "rule_ids": r_ids, "span": span,
                "disagree": r_ie != n_ie}


def outcome_class(rec, lab):
    st = rec["status"]
    if st == "COMPLETED":
        n = (rec.get("enrollment") or {}).get("count")
        return ("negative_completed", []) if (n or 0) >= 1 else ("unlabelled", ["completed_without_enrollment_count"])
    if st == "TERMINATED":
        cl = set(lab["stop_classes"])
        if not rec["why_stopped"].strip():
            return "unlabelled", ["no_why_stopped"]
        if not cl or cl <= UNINFORMATIVE:
            return "unlabelled", ["uninformative_why_stopped"]
        if "Insufficient_Enrollment" in cl:
            if "Covid19" in cl:
                return "other_stop", ["covid_confounded_recruitment_stop"]
            return "positive_recruitment", []
        return "other_stop", []
    return "unlabelled", ["status_out_of_scope"]


CAVEATS = {"negative_completed": ["planned_enrollment_lost_after_completion"]}


def label(ctx, cfg):
    paths = Paths(ctx.root).ensure()
    got = load_labeller(paths)
    if got is None:
        build(ctx, cfg)
        got = load_labeller(paths)
    manifest, mfile = got
    lab = Labeller(manifest, load(paths))
    trials = load_trials(paths)
    stamp = utc_stamp()
    out = paths.derived / f"labels_{stamp}.jsonl"
    counts = {}

    def rows():
        for rec in trials.values():
            tl = lab.label(rec["why_stopped"]) if rec["status"] == "TERMINATED" else {
                "stop_classes": [], "label_source": "none", "confidence": 0.0, "rule_ids": [], "span": None, "disagree": False}
            klass, cav = outcome_class(rec, tl)
            counts[klass] = counts.get(klass, 0) + 1
            yield {"nct_id": rec["nct_id"], "class": klass, "stop_classes": tl["stop_classes"], "label_source": tl["label_source"],
                   "confidence": tl["confidence"], "rule_ids": tl["rule_ids"], "evidence_span": tl["span"],
                   "labeller_disagree": tl["disagree"], "caveats": cav + CAVEATS.get(klass, []),
                   "labeller_file": mfile.name, "autoran_version": __version__, "labelled_at": iso_now()}
    n = write_jsonl(out, rows())
    ctx.store.append("autoran_stages.jsonl", {"stage": "label", "file": ctx.store.rel(out), "n": n, "counts": counts, "ts": iso_now()})
    ctx.count("labelled", n)
    ctx.notes["classes"] = counts
    return {"file": str(out), "counts": counts}


def load_labels(paths):
    f = paths.latest("labels_*.jsonl")
    if not f:
        raise FileNotFoundError("no labels yet; run `autoran label`")
    return {r["nct_id"]: r for r in iter_jsonl(f)}
