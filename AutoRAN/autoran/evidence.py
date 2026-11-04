"""Evidence: every local test result in one place, plus a factor combiner.

`summary` gathers whatever result files exist under data/derived/sim and data/derived/synth (each part is optional; a missing file just hides its section).
`combine` takes a set of factor families, fits them together on the saved out-of-fold scores of a "workbench" file, and reports AUROC with an interval, AUPRC,
precision and recall at a review budget, calibration, and ROC and precision-recall curves, so any combination can be checked at will.

Workbench files are written by the local research scripts (`workbench_registry_*.npz`, `workbench_protocol_*.npz`). They hold one out-of-fold score per trial
(or document) per family, never raw text. numpy only; the vault and the frozen test split are never read.
"""
import json
import math

import numpy as np

from . import risk, sim


def _latest(d, pattern):
    fs = sorted(d.glob(pattern)) if d.is_dir() else []
    return fs[-1] if fs else None


def _load(d, pattern):
    f = _latest(d, pattern)
    if not f:
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def summary(paths):
    d = paths.data / "derived" / "sim"
    syn = paths.data / "derived" / "synth"
    run = _load(d, "sim_2*.json")
    scaled_f = _latest(d, "ledger_scaled_2*.json")
    scaled = json.loads(scaled_f.read_text(encoding="utf-8")) if scaled_f else None
    proto = _load(d, "ledger_protocol_scaled_2*.json")
    parts = {
        "run": run, "scaled_registry": None, "scaled_protocol": proto, "backtest": _load(d, "enrolment_check_*.json"),
        "sponsor_identity": _load(d, "sponsor_identity_test_*.json"), "topic_baseline": _load(d, "topic_baseline_test_*.json"),
        "text_kind": _load(d, "text_kind_test_*.json"), "text_amend": _load(d, "text_amend_test_*.json"), "corpus_probe": _load(d, "corpus_probe_*.json"),
        "synthetic": _load(syn, "analysis_2*_with_key.json"),
    }
    if scaled:
        parts["scaled_registry"] = {"summary": scaled["summary"], "mlp": scaled["mlp_summary"], "kinds": scaled["kinds"], "stamp": scaled["stamp"],
                                    "sets": [{"window": x["window"], "train_n": x["train_n"], "train_failures": x["train_failures"], "test_n": x["test_n"], "test_failures": x["test_failures"],
                                              "test_prospective_n": x["test_prospective_n"], "test_prospective_failures": x["test_prospective_failures"], "mlp": x["mlp"]} for x in scaled["sets"]],
                                    "per_set_unique": {g: {f: [x["rows"][g][f]["unique"] for x in scaled["sets"] if f in x["rows"][g]] for f in scaled["families"]} for g in ("prospective (headline)", "all")},
                                    "per_set_alone": {g: {f: [x["rows"][g][f]["alone"] for x in scaled["sets"] if f in x["rows"][g]] for f in scaled["families"]} for g in ("prospective (headline)", "all")}}
    out = {"parts": {k: v is not None for k, v in parts.items()}, "gates": [{"gate": g, "claim": c, "status": st, "note": n} for g, c, st, n in sim.GATES],
           "workbench": workbench_info(paths), "files": _files(paths)}
    for k, v in parts.items():
        out[k] = v
    out["headline"] = headline(parts)
    return out


def _files(paths):
    out = []
    for base in (paths.data / "derived" / "sim", paths.data / "derived" / "synth"):
        if base.is_dir():
            for f in sorted(base.iterdir()):
                if f.suffix in (".json", ".npz") and not f.name.endswith("_partial.json"):
                    out.append({"name": f.name, "kb": round(f.stat().st_size / 1024), "modified": f.stat().st_mtime})
    return out


def headline(p):
    """The few numbers a person should see first, each with what produced it."""
    h = {"cards": [], "ladder": [], "sentences": []}
    run, sc, pr = p["run"], p["scaled_registry"], p["scaled_protocol"]
    if run and run.get("replay"):
        g = run["replay"]["groups"]["prospective (headline)"]
        h["cards"] += [{"label": "Registry factors, prospective trials", "value": g["full"]["auroc"], "fmt": "auc", "ci": g["full"]["auroc_ci"], "note": "trained to 2014, scored 2016 to 2018"},
                       {"label": "Precision in the top 5%", "value": g["full"]["top5"]["precision"], "fmt": "pct", "note": f"{g['full']['top5']['lift']}x the base rate of {g['full']['auprc_guessing_level']:.3f}"},
                       {"label": "AUPRC", "value": g["full"]["auprc"], "fmt": "num", "note": f"guessing level {g['full']['auprc_guessing_level']:.3f}"}]
        h["ladder"] += [{"label": "Registry factors, prospective", "auroc": g["full"]["auroc"], "ci": g["full"]["auroc_ci"], "group": "registry"},
                        {"label": "Registry factors, all trials", "auroc": run["replay"]["groups"]["all"]["full"]["auroc"], "ci": run["replay"]["groups"]["all"]["full"]["auroc_ci"], "group": "registry"},
                        {"label": "Who runs it only (prospective)", "auroc": g["who_runs_it_only"]["auroc"], "ci": g["who_runs_it_only"]["auroc_ci"], "group": "baseline"},
                        {"label": "Criteria count only (prospective)", "auroc": g["criteria_count_only"]["auroc"], "group": "baseline"}]
    if sc:
        sm = sc["summary"]["prospective (headline)"]
        stick = [r for r in sm["rows"] if r["status"] == "sticks"]
        best = sorted(stick, key=lambda r: -r["mean_unique"])[:3]
        h["cards"].append({"label": "Registry factors that stick", "value": len(stick), "fmt": "int", "note": f"of {len(sm['rows'])} tested over {len(sc['sets'])} windows; the rest not shown"})
        h["sentences"].append(f"Of {len(sm['rows'])} registry factor families tested over ten windows, {len(stick)} stuck on prospective trials; the strongest are " + ", ".join(r["family"].split(" (")[0] for r in best) + ".")
        h["ladder"].append({"label": "Neural network, same inputs (mean of 10 windows)", "auroc": sc["mlp"]["prospective (headline)"]["network_mean"], "group": "model"})
        h["ladder"].append({"label": "Ridge, same inputs (mean of 10 windows)", "auroc": sc["mlp"]["prospective (headline)"]["ridge_mean"], "group": "model"})
    if pr:
        v = pr["variants"].get("strict") or next(iter(pr["variants"].values()))
        stick = [r for r in v["rows"] if r["status"] == "sticks" and r["kind"] != "control"]
        h["cards"].append({"label": "Protocol-document families that stick", "value": len(stick), "fmt": "int", "note": f"of {len(v['rows'])}, strict cohort of {v['n']:,} documents ({v['failures']} failures)"})
        h["ladder"].append({"label": "Registry + sponsor + registry text, documents dated before start", "auroc": v["baseline_auroc"], "group": "documents"})
        h["ladder"].append({"label": "plus every document family", "auroc": v["full_auroc"], "group": "documents"})
        h["sentences"].append(f"Protocol-document families: {len(stick)} of {len(v['rows'])} stuck on documents dated at or before the trial start.")
    ti = p["topic_baseline"]
    if ti:
        t = ti["document_text_gain_over_registry_plus_sponsor_plus_registry_text"]
        h["sentences"].append(f"Document text still adds {t['gain']:+.3f} AUROC (interval {t['ci'][0]:+.3f} to {t['ci'][1]:+.3f}) after sponsor identity and the registry's own topic words; names, vocabulary band and version wording do not explain it.")
    bt = p["backtest"]
    if bt:
        b = bt["backtest_era_B"]
        h["cards"].append({"label": "Simulator backtest (gate G4)", "value": bt["gate_G4_verdict"], "fmt": "text", "note": f"AUROC {b['auroc']['simulator calibrated on era A']:.2f} against {b['auroc']['registry factors']:.2f} for registry factors"})
        h["ladder"].append({"label": "Simulator calibrated on era A, real 2016 to 2018 trials", "auroc": b["auroc"]["simulator calibrated on era A"], "group": "simulator"})
        h["sentences"].append(f"The recruitment simulator failed its first backtest on real trials ({b['auroc']['simulator calibrated on era A']:.2f} against {b['auroc']['registry factors']:.2f}); it stays a scenario tool.")
    if run and run.get("negative_controls"):
        c = run["negative_controls"]
        h["cards"].append({"label": "Negative controls", "value": "passed" if c["passed"] else "FAILED", "fmt": "text", "note": "shuffled outcomes, random columns, placebo outcome"})
    ld = run.get("ledger") if run else None
    if ld and ld.get("mercury") and ld["mercury"].get("overall"):
        o = ld["mercury"]["overall"]
        h["sentences"].append(f"Mercury in retrograde (the joke measure): rate ratio {o['rr']} ({o['rr_ci'][0]} to {o['rr_ci'][1]}), p = {o['p']}; it does not stick.")
    sy = p["synthetic"]
    if sy and sy.get("pairwise_share_ordered_as_designed"):
        r = sy["pairwise_share_ordered_as_designed"]["registry-factor risk"]
        h["sentences"].append(f"Twelve synthetic protocols: the registry factors ordered strong above weak and average perfectly but weak above average only {r[1]:.2f} of the time (0.5 is chance).")
    return h


# -- workbenches and the combiner ------------------------------------------------------------------------------------------------------------

def _wb_files(paths, kind):
    d = paths.data / "derived" / "sim"
    return sorted(d.glob(f"workbench_{kind}_*.npz")) if d.is_dir() else []


def workbench_info(paths):
    out = {}
    for kind in ("registry", "protocol"):
        fs = _wb_files(paths, kind)
        if not fs:
            continue
        z = np.load(fs[-1], allow_pickle=False)
        meta = json.loads(str(z["meta"]))
        out[kind] = {"families": [{"name": str(n), "kind": str(k)} for n, k in zip(z["fam"], z["kind"])], "meta": meta, "file": fs[-1].name}
    return out


def _curve(y, s, n=80):
    o = np.argsort(-s, kind="mergesort")
    yy = y[o]
    tp, fp = np.cumsum(yy), np.cumsum(1 - yy)
    P, Nn = max(1, int(yy.sum())), max(1, int(len(yy) - yy.sum()))
    idx = np.unique(np.linspace(0, len(yy) - 1, n).astype(int))
    roc = [[0.0, 0.0]] + [[round(float(fp[i] / Nn), 4), round(float(tp[i] / P), 4)] for i in idx]
    pr = [[round(float(tp[i] / P), 4), round(float(tp[i] / (i + 1)), 4)] for i in idx]
    return roc, pr


def _budget(y, s, fracs=(0.01, 0.05, 0.10, 0.20)):
    o = np.argsort(-s, kind="mergesort")
    out = []
    for f in fracs:
        k = max(1, int(len(y) * f))
        top = y[o[:k]]
        out.append({"budget": f, "precision": round(float(top.mean()), 4), "recall": round(float(top.sum() / max(1, y.sum())), 4), "lift": round(float(top.mean() / max(y.mean(), 1e-9)), 2), "flagged": k})
    return out


def _boot_auc(y, s, n=300, seed=3):
    r = np.random.default_rng(seed)
    v = []
    for _ in range(n):
        i = r.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            v.append(risk.auroc(y[i], s[i]))
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] if v else None


def _metrics(y, s, names, weights, alone, ref):
    cal, ece = risk.calibration(y, risk._sig(s))
    roc, pr = _curve(y, s)
    return {"n": int(len(y)), "failures": int(y.sum()), "base_rate": round(float(y.mean()), 5), "auroc": round(risk.auroc(y, s), 4), "auroc_ci": _boot_auc(y, s),
            "auprc": round(risk.auprc(y, s), 4), "at_budget": _budget(y, s), "roc": roc, "pr": pr, "calibration": cal, "ece": round(ece, 4), "weights": weights, "alone": alone, "reference": ref}


def combine(paths, setting, families, subset="prospective", include_baseline=True):
    """Fit the chosen families together and report how the combination does on held-out data."""
    fs = _wb_files(paths, setting)
    if not fs:
        raise ValueError("no workbench for " + setting + " yet: the local research scripts write it")
    z = np.load(fs[-1], allow_pickle=False)
    fam = [str(x) for x in z["fam"]]
    bad = [f for f in families if f not in fam]
    if bad:
        raise ValueError("unknown family: " + bad[0])
    if not families and not (setting == "protocol" and include_baseline):
        raise ValueError("choose at least one family")
    cols = [fam.index(f) for f in families]
    if setting == "registry":
        ytr, yte, Ztr, Zte = z["ytr"].astype(float), z["yte"].astype(int), z["Ztr"].astype(np.float64), z["Zte"].astype(np.float64)
        mask = z["pros_te"].astype(bool) if subset == "prospective" else np.ones(len(yte), bool)
        beta = risk.fit_logit(Ztr[:, cols], ytr, l2=1.0)
        s_all = Zte[:, cols] @ beta[:-1] + beta[-1]
        weights = {f: round(float(w), 3) for f, w in zip(families, beta[:-1])}
        full_beta = risk.fit_logit(Ztr, ytr, l2=1.0)
        s_full = Zte @ full_beta[:-1] + full_beta[-1]
        alone = {f: round(risk.auroc(yte[mask], Zte[mask][:, fam.index(f)]), 4) for f in families}
        singles = {f: risk.auroc(yte[mask], Zte[mask][:, i]) for i, f in enumerate(fam)}
        best = max(singles, key=singles.get)
        ref = {"all_families_auroc": round(risk.auroc(yte[mask], s_full[mask]), 4), "best_single_family": best, "best_single_auroc": round(singles[best], 4),
               "setting": "trained on starts up to 2014, scored 2016 to 2018; each family's score is out of fold on the training years"}
        return _metrics(yte[mask], s_all[mask], families, weights, alone, ref)
    y, Z, base = z["y"].astype(int), z["Z"].astype(np.float64), z["base"].astype(np.float64)
    mask = z["pros"].astype(bool) if subset == "prospective" else np.ones(len(y), bool)
    cols_used = ([base[:, None]] if include_baseline else []) + [Z[:, cols]]
    X = np.hstack(cols_used)
    names = (["registry baseline"] if include_baseline else []) + families
    fold = np.random.default_rng(9).integers(0, 5, len(y))
    s = np.zeros(len(y))
    for f in range(5):
        beta = risk.fit_logit(X[fold != f], y[fold != f].astype(float), l2=1.0)
        s[fold == f] = X[fold == f] @ beta[:-1] + beta[-1]
    beta = risk.fit_logit(X, y.astype(float), l2=1.0)
    weights = {n: round(float(w), 3) for n, w in zip(names, beta[:-1])}
    Xf = np.hstack([base[:, None], Z])
    sf = np.zeros(len(y))
    for f in range(5):
        b2 = risk.fit_logit(Xf[fold != f], y[fold != f].astype(float), l2=1.0)
        sf[fold == f] = Xf[fold == f] @ b2[:-1] + b2[-1]
    alone = {f: round(risk.auroc(y[mask], Z[mask][:, fam.index(f)]), 4) for f in families}
    singles = {f: risk.auroc(y[mask], Z[mask][:, i]) for i, f in enumerate(fam)}
    best = max(singles, key=singles.get)
    ref = {"all_families_auroc": round(risk.auroc(y[mask], sf[mask]), 4), "best_single_family": best, "best_single_auroc": round(singles[best], 4), "baseline_only_auroc": round(risk.auroc(y[mask], base[mask]), 4),
           "setting": "documents dated at or before the trial start; five-fold out-of-fold scores averaged over repeats, combined by a second five-fold stack"}
    return _metrics(y[mask], s[mask], names, weights, alone, ref)


def correlation(paths, setting):
    """Correlation between families' held-out scores: which sources say the same thing."""
    fs = _wb_files(paths, setting)
    if not fs:
        return None
    z = np.load(fs[-1], allow_pickle=False)
    fam = [str(x) for x in z["fam"]]
    M = z["Zte"].astype(np.float64) if setting == "registry" else z["Z"].astype(np.float64)
    C = np.corrcoef(M.T)
    return {"families": fam, "kinds": [str(k) for k in z["kind"]], "matrix": [[None if v != v else round(float(v), 3) for v in r] for r in C]}      # constant families have no correlation
