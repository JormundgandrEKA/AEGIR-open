"""Building labelling batches (matched positives and negatives) and auditing them."""
import difflib
import json
import random
import re
from collections import Counter
from pathlib import Path

from . import amend, ctgov, derive
from .core import iso_now, utc_stamp
from .textclean import clean_text

BATCH_SCHEMA = "label-batch/0.2"
QUESTION = ("Between version {a} ({da}) and version {b} ({db}): did anything change in a meaningful way in who can enter "
            "(eligibility, age, sex), what is measured (primary outcomes), how many (enrolment), or the arms and "
            "interventions?")


def labels_dir(ctx):
    return ctx.root / "data" / "labels"


def word_ops(a, b):
    """Word-level diff as two op lists: before = eq/del, after = eq/ins."""
    ta, tb = re.findall(r"\s+|\S+", a), re.findall(r"\s+|\S+", b)
    before, after = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if tag == "equal":
            before.append(["eq", "".join(ta[i1:i2])])
            after.append(["eq", "".join(tb[j1:j2])])
        else:
            if i2 > i1:
                before.append(["del", "".join(ta[i1:i2])])
            if j2 > j1:
                after.append(["ins", "".join(tb[j1:j2])])
    return {"before": before, "after": after}


def display_outcomes(f):
    out = []
    for m, tf in amend.parse_outcomes(f):
        out.append(f"• {m}" + (f"  (time frame: {tf})" if tf else ""))
    return "\n".join(out)


def display_design(f):
    parts = []
    for key, head in (("arms", "Arm groups"), ("interventions", "Interventions")):
        lines = [l.replace(" | ", " — ") for l in f[key].splitlines() if l.strip()]
        if lines:
            parts.append(head + ":\n" + "\n".join("• " + l for l in lines))
    return "\n".join(parts)


def _panel(key, label, a, b):
    return {"key": key, "label": label, "changed": a != b, "ops": word_ops(a, b)}


def make_case(rec, nct, fa, fb, va, vb, date_a, date_b, labels_b, design):
    ps = (rec or {}).get("protocolSection", {})
    sm = ctgov.study_summary(rec) if rec else {"nct_id": nct}
    analysis = amend.analyse(fa, fb)
    prov = amend.provisional(analysis)
    panels = [_panel("eligibility", "Eligibility criteria", fa["eligibility_criteria"], fb["eligibility_criteria"]),
              _panel("outcomes", "Primary outcomes", display_outcomes(fa), display_outcomes(fb)),
              _panel("design", "Arms and interventions", display_design(fa), display_design(fb))]
    rows = []
    for key, label in (("min_age", "minimum age"), ("max_age", "maximum age"), ("sex", "sex"),
                       ("healthy_volunteers", "healthy volunteers"), ("enrollment", "enrolment")):
        b4, af = fa[key], fb[key]
        if key == "enrollment":
            b4 = f"{b4} ({fa.get('enrollment_type', '').lower()})" if b4 else b4
            af = f"{af} ({fb.get('enrollment_type', '').lower()})" if af else af
        rows.append({"field": label, "before": b4, "after": af, "changed": fa[key] != fb[key]})
    kinds = {f["kind"] for f in analysis["findings"] if f["substantive"]}
    focus = ("eligibility" if kinds & {"criterion_added", "criterion_removed", "threshold_changed", "qualifier_changed",
                                       "reworded", "moved_section", "age_limit_changed", "sex_changed"}
             else "outcome" if any(k.startswith("outcome") for k in kinds) else "design")
    return {
        "nct_id": nct, "title": clean_text(ps.get("identificationModule", {}).get("briefTitle", "")),
        "phase": "|".join(sm.get("phase") or []), "sponsor_class": sm.get("sponsor_class"),
        "start": sm.get("start"), "primary_completion": sm.get("primary_completion"),
        "why_stopped": ps.get("statusModule", {}).get("whyStopped"), "focus": focus,
        "question": QUESTION.format(a=va, b=vb, da=date_a, db=date_b),
        "a": {"version": va, "date": date_a}, "b": {"version": vb, "date": date_b, "labels": labels_b},
        "panels": panels, "table": rows, "notes": analysis["notes"],
        "links": {"study": f"https://clinicaltrials.gov/study/{nct}", "history": f"https://clinicaltrials.gov/study/{nct}?tab=history"},
        "evidence_quote": " | ".join(f"{f['kind']}: {f.get('before', '')} -> {f.get('after', '')}"
                                     for f in analysis["findings"] if f["substantive"])[:300],
        "provisional": prov,
        "_design": dict(design, kinds=prov["kinds"], n_substantive=prov["n_substantive"],
                        suggested_types=prov["suggested_types"], suggested_severity=prov["suggested_severity"])}


def _load_pair(ctx, nct, va, vb):
    have = ctgov.stored_versions(ctx, nct)
    if va not in have or vb not in have:
        return None
    load = lambda v: derive.version_fields(json.loads(have[v].read_text(encoding="utf-8")))
    return load(va), load(vb)


def _real_case(ctx, nct, trial, va, vb, truth, matched_to=None):
    pair = _load_pair(ctx, nct, va, vb)
    if pair is None:
        return None
    index, _ = ctgov.stored_index(ctx, nct)
    meta = {v: (d, l) for v, d, l in index}
    rec, _ = ctgov.find_study_record(ctx, nct)
    design = {"truth": truth, "matched_to": matched_to, "baseline_post_start": trial.get("baseline_post_start")}
    return make_case(rec, nct, pair[0], pair[1], va, vb, meta.get(va, ("", []))[0], meta.get(vb, ("", []))[0],
                     meta.get(vb, ("", []))[1], design)


def _strata(ctx, nct):
    rec, _ = ctgov.find_study_record(ctx, nct)
    sm = ctgov.study_summary(rec) if rec else {}
    return rec, ("|".join(sm.get("phase") or []), sm.get("sponsor_class"), (sm.get("start") or "")[:4])


def build_batch(ctx, source, positives, negatives, seed, name=None, synthetic=0):
    rng = random.Random(seed)
    cases, notes = [], []
    if synthetic:
        cases = _synthetic(synthetic)
    else:
        src = Path(source)
        src = src if src.is_absolute() else ctx.root / src
        doc = json.loads(src.read_text(encoding="utf-8"))
        if "substantive_v2" not in next(iter(doc["trials"].values())):
            raise ValueError("this content-flags file predates rule v2; rerun `derive content-flags`")
        trials = {n: t for n, t in doc["trials"].items() if t.get("status") == "ok"}
        pos = sorted(n for n, t in trials.items() if t["substantive_v2"] and t["best_version"])
        neg = sorted(n for n, t in trials.items() if t["clean_negative"])
        rng.shuffle(pos)
        rng.shuffle(neg)
        pos = pos[:positives]
        strata = {n: _strata(ctx, n) for n in pos + neg}
        used, pairs, exact = set(), [], 0
        for p in pos:
            key = strata[p][1]
            for lvl, rel in enumerate((lambda s: s == key, lambda s: s[:2] == key[:2], lambda s: s[:1] == key[:1],
                                       lambda s: True)):
                m = next((n for n in neg if n not in used and rel(strata[n][1])), None)
                if m:
                    used.add(m)
                    pairs.append((p, m, lvl))
                    break
        pairs = pairs[:negatives]
        if len(pos) < positives:
            notes.append(f"only {len(pos)} positives available")
        if len(pairs) < min(len(pos), negatives):
            notes.append(f"only {len(pairs)} clean negatives available for matching (wanted {min(len(pos), negatives)})")
        for p, m, lvl in pairs:
            tp, tn = trials[p], trials[m]
            cases.append(_real_case(ctx, p, tp, tp["baseline_version"], tp["best_version"], "positive"))
            c = _real_case(ctx, m, tn, tn["baseline_version"], tn["window_versions"][-1], "negative", matched_to=p)
            if c:
                c["_design"]["match_level"] = lvl
            cases.append(c)
        for p in pos[len(pairs):]:                   # unmatched positives still make it in when negatives run out
            tp = trials[p]
            cases.append(_real_case(ctx, p, tp, tp["baseline_version"], tp["best_version"], "positive"))
    cases = [c for c in cases if c]
    rng.shuffle(cases)
    hide = random.Random(seed + 1)
    for i, c in enumerate(cases, 1):
        c["case_id"] = f"c{i:03d}"
        c["provisional_mode"] = "hidden_by_design" if hide.random() < 0.10 else "collapsed"
    name = name or f"batch_{utc_stamp()}"
    batch = {"schema": BATCH_SCHEMA, "name": name, "seed": seed, "built": iso_now(),
             "source": str(source) if source else "synthetic", "notes": notes,
             "counts": {"cases": len(cases), "positives": sum(c["_design"]["truth"] == "positive" for c in cases),
                        "negatives": sum(c["_design"]["truth"] == "negative" for c in cases),
                        "hidden_provisional": sum(c["provisional_mode"] != "collapsed" for c in cases)},
             "cases": cases}
    path = ctx.store.write_json_new(labels_dir(ctx) / "batches" / f"{name}.json", batch)
    for k, v in batch["counts"].items():
        ctx.count(k, v)
    ctx.notes["batch_file"] = ctx.store.rel(path)
    if notes:
        ctx.notes["warnings"] = notes


def _synthetic(n):
    base = ("Inclusion Criteria:\n\n• Age 40 years or older\n• Diagnosis of COPD\n• Smoking history of at least "
            "10 pack-years\n\nExclusion Criteria:\n\n• Asthma\n• Recent exacerbation within 4 weeks")
    variants = [
        (base.replace("at least 10", "at least 20").replace("• Asthma", "• Asthma or lung cancer"), "positive"),
        (base, "negative"),
        (base.replace("exacerbation", "exacerbaton").replace("Diagnosis", "Diagnoses"), "negative"),   # spelling only
        (base.replace("COPD", "COPD (chronic obstructive pulmonary disease)"), "negative"),            # acronym only
        (base.replace("within 4 weeks", "within 8 weeks"), "positive"),
    ]
    out = []
    for i in range(n):
        text, truth = variants[i % len(variants)]
        fa = {"eligibility_criteria": base, "min_age": "40 Years", "max_age": "", "sex": "ALL", "healthy_volunteers": "False",
              "primary_outcomes": "FEV1 | 12 weeks", "enrollment": "100", "enrollment_type": "ESTIMATED", "arms": "", "interventions": ""}
        fb = dict(fa, eligibility_criteria=text)
        rec = {"protocolSection": {"identificationModule": {"briefTitle": f"Synthetic COPD trial {i + 1}"},
                                   "statusModule": {"startDateStruct": {"date": "2012-03"}},
                                   "designModule": {"phases": ["PHASE3"]},
                                   "sponsorCollaboratorsModule": {"leadSponsor": {"class": "INDUSTRY"}}}}
        out.append(make_case(rec, f"NCT9000000{i}", fa, fb, 0, 2, "2012-01-05", "2012-09-14", ["Eligibility", "Study Status"],
                             {"truth": truth}))
    return out


# -- audit ------------------------------------------------------------------------

MARKUP = re.compile(r"</?[a-z]+[^>]*>|&#?\w+;|\*\*|\\\*|^\s*[*+-] ", re.M)


def audit(ctx, names, label_user=None):
    """Quality checks over batches: balance, matching, overlap, weak positives, markup residue, size."""
    batches = {}
    for n in names:
        p = Path(n)
        p = p if p.is_file() else labels_dir(ctx) / "batches" / (n if n.endswith(".json") else n + ".json")
        batches[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    report = {"generated": iso_now(), "batches": {}, "issues": []}
    sets = {k: {c["nct_id"] for c in b["cases"]} for k, b in batches.items()}
    for k, b in batches.items():
        cs = b["cases"]
        pos = [c for c in cs if c["_design"]["truth"] == "positive"]
        neg = [c for c in cs if c["_design"]["truth"] == "negative"]
        text = lambda c: " ".join(o[1] for p_ in c["panels"] for o in p_["ops"]["before"] + p_["ops"]["after"])
        sizes = [len(text(c)) for c in cs]
        kinds = Counter(x for c in pos for x in c["_design"]["kinds"])
        weak = [c["case_id"] for c in pos if c["provisional"]["confidence"] != "high"]
        hard_neg = [c["case_id"] for c in neg if any(f for f in c["provisional"]["evidence"].splitlines() if "minor" in f and f[:1].isdigit())]
        m = {"n_cases": len(cs), "positives": len(pos), "negatives": len(neg),
             "hidden_provisional": sum(c["provisional_mode"] != "collapsed" for c in cs),
             "match_levels": dict(Counter(c["_design"].get("match_level") for c in neg)),
             "positives_without_substantive_finding": [c["case_id"] for c in pos if c["_design"]["n_substantive"] == 0],
             "negatives_with_substantive_finding": [c["case_id"] for c in neg if c["_design"]["n_substantive"] > 0],
             "weak_positives_not_high_confidence": weak, "hard_negatives_with_minor_findings": hard_neg,
             "markup_residue_cases": [c["case_id"] for c in cs if MARKUP.search(text(c))],
             "very_long_cases_over_6000_chars": [c["case_id"] for c in cs if len(text(c)) > 6000],
             "median_chars": sorted(sizes)[len(sizes) // 2] if sizes else 0, "max_chars": max(sizes) if sizes else 0,
             "baseline_post_start_cases": [c["case_id"] for c in cs if c["_design"].get("baseline_post_start")],
             "positive_kind_counts": dict(kinds.most_common()),
             "positive_types_suggested": dict(Counter(t for c in pos for t in c["_design"]["suggested_types"]).most_common()),
             "overlap_with_other_batches": {o: len(sets[k] & sets[o]) for o in sets if o != k}}
        report["batches"][k] = m
        for key in ("positives_without_substantive_finding", "negatives_with_substantive_finding", "markup_residue_cases"):
            if m[key]:
                report["issues"].append(f"{k}: {key} {m[key][:8]}")
        if m["positives"] != m["negatives"]:
            report["issues"].append(f"{k}: unbalanced {m['positives']} positives vs {m['negatives']} negatives")
        if len(weak) > 0.3 * max(len(pos), 1):
            report["issues"].append(f"{k}: {len(weak)} of {len(pos)} positives are not high confidence")
    out = ctx.store.write_json_new(ctx.store.derived_dir() / f"batch_audit_{utc_stamp()}.json", report)
    ctx.notes["audit_file"] = ctx.store.rel(out)
    ctx.notes["issues"] = report["issues"]
    ctx.notes["per_batch"] = {k: {x: (len(v) if isinstance(v, list) else v) for x, v in m.items()
                                  if x in ("n_cases", "positives", "negatives", "hidden_provisional",
                                           "weak_positives_not_high_confidence", "hard_negatives_with_minor_findings",
                                           "markup_residue_cases", "baseline_post_start_cases",
                                           "very_long_cases_over_6000_chars", "median_chars", "max_chars")}
                              for k, m in report["batches"].items()}
