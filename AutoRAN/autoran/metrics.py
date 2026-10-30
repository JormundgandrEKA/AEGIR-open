"""`autoran metrics`: one JSON file with every number the dashboard shows, tied to the hashes of the files it came from."""
import hashlib
import json
from collections import Counter, defaultdict

from . import __version__, stats
from .core import Paths, iso_now, iter_jsonl, utc_stamp
from .scorers import BINARY, iter_joined, load_scores

CLEAN = {"first_version", "never_updated", "current_unchanged"}
DIMS = ["phase", "area", "year_band", "sponsor_class", "region", "site_band", "allocation", "masking", "purpose", "input_state",
        "registration", "stop_class", "label_source"]
KEY = {"positive_recruitment": "pos", "negative_completed": "neg", "other_stop": "other", "unlabelled": "unl"}


def _sha(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def wilson_block(k, n):
    lo, hi = stats.wilson(k, n)
    return {"k": k, "n": n, "p": round(k / n, 4) if n else None, "lo": lo, "hi": hi}


def audit_stats(paths):
    """Human spot-check precision per class from data/labels/*/autoran_audit.jsonl (latest verdict per trial and labeller)."""
    verdicts = {}
    for f in sorted((paths.data / "labels").glob("*/autoran_audit.jsonl")) if (paths.data / "labels").is_dir() else []:
        for r in iter_jsonl(f):
            if r.get("kind") == "trial":
                verdicts[(f.parent.name, r["nct_id"])] = r
    per = defaultdict(lambda: Counter())
    for (_, nct), r in verdicts.items():
        per[r["class"]][r["verdict"]] += 1
    out = {}
    for klass, c in per.items():
        k, n = c["agree"], c["agree"] + c["disagree"]
        out[klass] = {**wilson_block(k, n), "unsure": c["unsure"], "checked": sum(c.values())}
    return out


def rule_review_stats(paths):
    out = {}
    for f in sorted((paths.data / "labels").glob("*/autoran_audit.jsonl")) if (paths.data / "labels").is_dir() else []:
        for r in iter_jsonl(f):
            if r.get("kind") == "rule":
                out[r["rule_id"]] = r
    return out


def compute(ctx, cfg, device="cpu"):
    paths = Paths(ctx.root).ensure()
    boot = cfg["bootstrap"]
    if device != "cpu":
        from . import gpu
        summ = lambda y, s: gpu.summarize_gpu(y, s, boot["resamples"], boot["seed"], device)
    else:
        summ = lambda y, s: stats.summarize(y, s, boot["resamples"], boot["seed"])
    scores = load_scores(paths)
    cover = {d: defaultdict(lambda: Counter()) for d in DIMS + ["status", "class"]}
    rows = {"dev": [], "test": []}               # (nct, y, clean, areas, phase, year_band)
    n_all = 0
    dis = 0
    rule_counts = Counter()
    index_rows = []
    for rec, lab, cat in iter_joined(paths):
        n_all += 1
        k = KEY[lab["class"]]
        cover["status"][rec["status"]]["n"] += 1
        cover["status"][rec["status"]][k] += 1
        cover["class"][lab["class"]]["n"] += 1
        dis += bool(lab["labeller_disagree"])
        for rid in lab["rule_ids"]:
            rule_counts[rid] += 1
        index_rows.append([rec["nct_id"], rec["title"], rec["status"], lab["class"], cat["stop_class"], lab["label_source"],
                           int(lab["confidence"] * 1000), int(bool(lab["labeller_disagree"])), cat["phase"], cat["areas"], cat["year"],
                           cat["sponsor_class"], cat["region"], cat["input_state"], cat["registration"], cat["split"],
                           rec["why_stopped"][:240], lab["evidence_span"], lab["rule_ids"], (rec.get("enrollment") or {}).get("count"),
                           rec["page"], rec["pos"], rec["n_sites"], rec["eligibility"]["n_incl"] + rec["eligibility"]["n_excl"]])
        vals = {"phase": [cat["phase"]], "area": cat["areas"], "year_band": [cat["year_band"]], "sponsor_class": [cat["sponsor_class"]],
                "region": [cat["region"]], "site_band": [cat["site_band"]], "allocation": [cat["allocation"]], "masking": [cat["masking"]],
                "purpose": [cat["purpose"]], "input_state": [cat["input_state"]], "registration": [cat["registration"]],
                "stop_class": [cat["stop_class"]] if cat["stop_class"] else [], "label_source": [lab["label_source"]] if rec["status"] == "TERMINATED" else []}
        for d, vs in vals.items():
            for v in vs:
                cover[d][v]["n"] += 1
                cover[d][v][k] += 1
        if lab["class"] in BINARY and cat["split"] in rows:
            rows[cat["split"]].append((rec["nct_id"], int(lab["class"] == "positive_recruitment"), cat["input_state"] in CLEAN,
                                       cat["areas"], cat["phase"]))
    coverage = {d: {g: dict(c) for g, c in sorted(m.items(), key=lambda kv: -kv[1]["n"])} for d, m in cover.items()}

    sc_out = {}
    for name, sm in sorted(scores.items()):
        entry = {}
        for split in ("test", "dev"):
            part = [(n, y, c, a, p) for n, y, c, a, p in rows[split] if n in sm]
            y_all, s_all = [r[1] for r in part], [sm[r[0]] for r in part]
            block = {"all": summ(y_all, s_all)}
            cl = [r for r in part if r[2]]
            block["clean"] = summ([r[1] for r in cl], [sm[r[0]] for r in cl])
            if block["all"].get("auroc") is not None and block["clean"].get("auroc") is not None:
                block["gap_auroc"] = round(block["all"]["auroc"] - block["clean"]["auroc"], 4)
            if split == "test":
                for dim, idx in (("by_area", 3), ("by_phase", 4)):
                    groups = defaultdict(list)
                    for r in part:
                        for g in (r[idx] if isinstance(r[idx], list) else [r[idx]]):
                            groups[g].append(r)
                    out_g = []
                    for g, rs in groups.items():
                        yy, ss = [r[1] for r in rs], [sm[r[0]] for r in rs]
                        npos = sum(yy)
                        out_g.append({"group": g, "n": len(rs), "positives": npos, "auroc": round(stats.auroc(yy, ss), 4) if 0 < npos < len(yy) else None})
                    block[dim] = sorted(out_g, key=lambda x: -x["n"])
            entry[split] = block
        sc_out[name] = entry

    man = None
    lf = paths.latest("labeller_*.json")
    if lf:
        man = json.loads(lf.read_text(encoding="utf-8"))
    labeller = None
    if man:
        m = man["metrics"]
        labeller = {"file": lf.name, "choice_ie": man["choice_ie"], "rules": m["rules"], "nb": m["nb"], "ie_combos": m["ie_combos"],
                    "sizes": m["sizes"], "rule_table": man["rule_table"], "source": man["source"],
                    "disagree_count": dis, "disagree_share": round(dis / max(1, coverage["status"].get("TERMINATED", {}).get("n", 1)), 4)}
    audits = audit_stats(paths)
    runs = ctx.store.latest("autoran_runs.jsonl", "run")
    pages = ctx.store.records("autoran_pages.jsonl")
    fl = ctx.store.records("fetch_log.jsonl")
    pipeline = {"trials": n_all, "runs": [{"run": r["run"], "kind": r["kind"], "status": r["status"]} for r in sorted(runs.values(), key=lambda x: x["run"])],
                "pages": len(pages), "requests_logged": len(fl), "errors_logged": sum(1 for r in fl if r.get("error") or (r.get("status") or 0) >= 400),
                "data_timestamp": _first_ts(ctx, pages), "autoran_version": __version__, "computed": iso_now(),
                "disk_mb": round(sum(p.stat().st_size for p in (ctx.root / "data").rglob("*") if p.is_file()) / 1e6, 1)}
    warn = []
    if man:
        ie_t = m["rules"]["test"]["per_class"]["Insufficient_Enrollment"]
        chosen = m["ie_combos"]["test"][man["choice_ie"]]
        if chosen["precision"] < 0.90:
            warn.append(f"Insufficient_Enrollment precision on the held-out curated test is {chosen['precision']:.3f}, below the 0.90 target ({man['choice_ie']} mode).")
    if "random" in sc_out and sc_out["random"]["test"]["all"].get("auroc") is not None and abs(sc_out["random"]["test"]["all"]["auroc"] - 0.5) > 0.02:
        warn.append("The random scorer is not near AUROC 0.5: check the splits for leakage.")
    clean_pos = sum(1 for r in rows["test"] if r[2] and r[1])
    if clean_pos < 100:
        warn.append(f"Only {clean_pos} clean positives in the test split: clean-subset intervals are wide.")
    cl_share = coverage["input_state"]
    clean_n = sum(cl_share.get(k, {}).get("n", 0) for k in CLEAN)
    if clean_n < 0.2 * n_all:
        warn.append(f"Clean inputs are {clean_n:,} of {n_all:,} trials ({100 * clean_n / max(1, n_all):.1f}%) and are mostly small trials never updated after posting: treat 'clean' results as a different population, not just a cleaner one.")
    for name, e in sc_out.items():
        g = e["test"].get("gap_auroc")
        ci = (e["test"]["clean"].get("ci") or {}).get("auroc")
        a_all = e["test"]["all"].get("auroc")
        # only a real gap: the clean interval must exclude the all-trials value
        if g is not None and abs(g) > 0.03 and ci and a_all is not None and not (ci[0] <= a_all <= ci[1]):
            warn.append(f"Scorer {name}: AUROC differs by {g:+.3f} between all trials and the clean subset.")
    if not audits:
        warn.append("No human spot-checks recorded yet: silver label precision is estimated only from the curated test set.")
    hashes = {}
    for pat in ("trials_*.jsonl", "labels_*.jsonl", "cats_*.jsonl", "labeller_*.json"):
        f = paths.latest(pat)
        if f:
            hashes[f.name] = _sha(f)
    stamp = utc_stamp()
    from .core import write_jsonl
    write_jsonl(paths.derived / f"index_{stamp}.jsonl", index_rows)
    out = {"schema": "autoran-metrics/0.1", "rule_counts": dict(rule_counts), "pipeline": pipeline, "coverage": coverage, "labeller": labeller, "audits": audits,
           "rule_review": rule_review_stats(paths), "scorers": sc_out, "warnings": warn, "input_hashes": hashes,
           "scope": cfg["scope"], "grade_floor": cfg["grade_floor"], "compute_device": device}
    f = paths.derived / f"metrics_{stamp}.json"
    f.write_text(json.dumps(out, ensure_ascii=True), encoding="utf-8")
    ctx.store.append("autoran_stages.jsonl", {"stage": "metrics", "file": ctx.store.rel(f), "ts": iso_now()})
    ctx.notes["warnings"] = warn
    ctx.notes["scorers"] = {k: {"test_auroc": v["test"]["all"].get("auroc"), "test_clean_auroc": v["test"]["clean"].get("auroc")} for k, v in sc_out.items()}
    return {"file": str(f), "warnings": warn}


def _first_ts(ctx, pages):
    if not pages:
        return None
    side = ctx.root / pages[0]["file"]
    side = side.with_name(side.name + ".meta.json")
    try:
        return json.loads(side.read_text(encoding="utf-8")).get("ctgov_data_timestamp")
    except (OSError, ValueError):
        return None


def load_metrics(paths):
    f = paths.latest("metrics_*.json")
    return json.loads(f.read_text(encoding="utf-8")) if f else None
