"""Derived tables: field-level diffs, label flags (T12 rule) and content flags (real positive definition)."""
import csv
import difflib
import io
import json
import re

from . import amend, ctgov
from .core import delimit, iso_now, utc_stamp
from .textclean import clean_text

ELIGIBILITY = ("eligibility_criteria", "min_age", "max_age", "sex", "healthy_volunteers")
OUTCOME = ("primary_outcomes",)
DESIGN = ("enrollment", "arms", "interventions")
FIELDS = ELIGIBILITY + OUTCOME + DESIGN
LOW_ACCRUAL = re.compile(r"accru|enrol|enroll|recruit|participants", re.I)   # broad; reconciliation only
STOP_RE = re.compile(r"accru|recruit|enrol", re.I)                            # T12 rule
PROTOCOL_JOURNALS = re.compile(r"\bTrials\.|JMIR Res Protoc|BMJ Open")
_PERSONAL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d ()-]{8,}\d")


def protocol_section(obj):
    ps = ctgov._find_key(obj, "protocolSection")
    return ps if isinstance(ps, dict) else (obj if isinstance(obj, dict) else {})


def version_fields(obj):
    """Normalised comparable fields from a version record (or a current record)."""
    ps = protocol_section(obj)
    el = ps.get("eligibilityModule", {})
    dm = ps.get("designModule", {})
    ao = ps.get("armsInterventionsModule", {})
    outs = ps.get("outcomesModule", {}).get("primaryOutcomes", []) or []
    return {
        "eligibility_criteria": clean_text(el.get("eligibilityCriteria")),
        "min_age": el.get("minimumAge") or "",
        "max_age": el.get("maximumAge") or "",
        "sex": el.get("sex") or "",
        "healthy_volunteers": str(el.get("healthyVolunteers", "")),
        "primary_outcomes": "\n".join(f"{clean_text(o.get('measure'))} | {clean_text(o.get('timeFrame'))}" for o in outs),
        "enrollment": str(dm.get("enrollmentInfo", {}).get("count", "")),
        "enrollment_type": str(dm.get("enrollmentInfo", {}).get("type", "")),
        "arms": "\n".join(f"{clean_text(a.get('label'))} | {a.get('type', '')}" for a in ao.get("armGroups", []) or []),
        "interventions": "\n".join(f"{i.get('type', '')} | {clean_text(i.get('name'))}"
                                   for i in ao.get("interventions", []) or []),
    }


def similarity(a, b, words=False):
    if a == b:
        return 1.0
    if words:
        a, b = a.split(), b.split()
    return round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 4)


def diff_fields(fa, fb):
    rows = []
    for k in FIELDS:
        a, b = fa.get(k, ""), fb.get(k, "")
        row = {"field": k, "changed": a != b, "similarity": similarity(a, b)}
        if k == "eligibility_criteria" and a != b:
            la, lb = a.splitlines(), b.splitlines()
            nd = list(difflib.ndiff(la, lb))
            row["lines_added"] = sum(1 for l in nd if l.startswith("+ "))
            row["lines_removed"] = sum(1 for l in nd if l.startswith("- "))
        rows.append(row)
    return rows


def _load_version(ctx, nct, v):
    p = ctgov.stored_versions(ctx, nct).get(v)
    if p is None:
        raise FileNotFoundError(f"{nct} version {v} is not stored (fetch or import it first)")
    return json.loads(p.read_text(encoding="utf-8"))


def _csv_bytes(rows, cols):
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def diff(ctx, nct, v_from, v_to):
    nct = nct.upper()
    try:
        fa, fb = version_fields(_load_version(ctx, nct, v_from)), version_fields(_load_version(ctx, nct, v_to))
    except FileNotFoundError as e:
        ctx.error(str(e))
        return
    rows = diff_fields(fa, fb)
    cols = ["field", "changed", "similarity", "lines_added", "lines_removed"]
    path = ctx.store.write_new(ctx.store.derived_dir() / f"diff_{nct}_v{v_from}_v{v_to}_{utc_stamp()}.csv",
                               _csv_bytes(rows, cols))
    changed = [r["field"] for r in rows if r["changed"]]
    ctx.count("fields_changed", len(changed))
    ctx.notes["changed_fields"] = changed
    ctx.notes["derived_file"] = ctx.store.rel(path)
    ctx.notes["similarity"] = {r["field"]: r["similarity"] for r in rows if r["changed"]}
    if ctx.verbose:
        for k in changed:
            print(delimit(f"{nct} {k} v{v_from}", fa[k][:2000]))
            print(delimit(f"{nct} {k} v{v_to}", fb[k][:2000]))


def norm_date(s):
    """ISO date string; YYYY-MM becomes YYYY-MM-01 (T12 rule, for start and completion alike)."""
    s = (s or "")[:10]
    return s + "-01" if len(s) == 7 else s


def _window(index, start, completion):
    s, e = norm_date(start), norm_date(completion)
    return [(v, d, labels) for v, d, labels in index if v > 0 and s and s < d and (not e or d <= e)]


def _pool_studies(ctx, pool):
    ent = ctx.store.latest("searches.jsonl", "query_id").get(pool)
    if not ent:
        ctx.error(f"no stored search for pool {pool}; run `ctgov search --query-id {pool}` first")
        return None, None
    sfile = ctx.root / ent["file"]
    sidecar = json.loads(sfile.with_name(sfile.name + ".meta.json").read_text(encoding="utf-8"))
    return json.loads(sfile.read_text(encoding="utf-8")).get("studies", []), sidecar


def label_flags(ctx, pool):
    """T12 rule, from version indexes only: a cheap pre-screen, not the positive definition."""
    studies, sidecar = _pool_studies(ctx, pool)
    if studies is None:
        return
    cols = ["nct_id", "status", "phase", "start", "primary_completion", "sponsor_class", "enrollment",
            "why_stopped", "low_accrual_stop", "n_references", "protocol_paper_ref", "protocol_ref_any",
            "history_available", "n_index_entries", "n_window_entries", "label_eligibility",
            "label_outcome", "label_design", "candidate", "data_timestamp"]
    rows, extra_low = [], []
    for s in ctx.limit(studies):
        sm = ctgov.study_summary(s)
        ps = s.get("protocolSection", {})
        why = ps.get("statusModule", {}).get("whyStopped", "") or ""
        refs = ps.get("referencesModule", {}).get("references", []) or []
        cites = [r.get("citation", "") for r in refs]
        low = bool(STOP_RE.search(why))
        if LOW_ACCRUAL.search(why) and not low:
            extra_low.append(sm["nct_id"])
        row = {**sm, "phase": "|".join(sm["phase"] or []),
               "enrollment": ps.get("designModule", {}).get("enrollmentInfo", {}).get("count", ""),
               "why_stopped": why.replace("\n", " "), "low_accrual_stop": int(low), "n_references": len(refs),
               "protocol_paper_ref": int(any(re.search("protocol", c, re.I) and PROTOCOL_JOURNALS.search(c)
                                             for c in cites)),
               "protocol_ref_any": int(any(re.search("protocol", c, re.I) for c in cites)),
               "data_timestamp": sidecar.get("ctgov_data_timestamp") or ""}
        index, _ = ctgov.stored_index(ctx, sm["nct_id"])
        row["history_available"] = int(bool(index))
        if not index:
            row["candidate"] = "no_history"
        else:
            win = _window(index, sm["start"], sm["primary_completion"])
            labs = {l for _, _, ls in win for l in ls}
            row.update(n_index_entries=len(index), n_window_entries=len(win),
                       label_eligibility=int("Eligibility" in labs), label_outcome=int("Outcome Measures" in labs),
                       label_design=int("Study Design" in labs))
            pos = "Eligibility" in labs or "Outcome Measures" in labs or low
            neg = sm["status"] == "COMPLETED" and not pos and "Study Design" not in labs
            row["candidate"] = "positive" if pos else ("negative" if neg else "neither")
        rows.append(row)
    path = ctx.store.write_new(ctx.store.derived_dir() / f"label_flags_{pool}_{utc_stamp()}.csv",
                               _csv_bytes(rows, cols))
    for c in ("positive", "negative", "neither", "no_history"):
        ctx.count(f"candidate_{c}", sum(1 for r in rows if r["candidate"] == c))
    ctx.count("trials", len(rows))
    ctx.count("low_accrual_stops", sum(r["low_accrual_stop"] for r in rows))
    ctx.count("protocol_paper_refs", sum(r["protocol_paper_ref"] for r in rows))
    ctx.notes.update({
        "derived_file": ctx.store.rel(path), "data_timestamp": sidecar.get("ctgov_data_timestamp"),
        "rule": "T12 label rule (handoff-from-design.md section 1); candidates only",
        "low_accrual_only_under_broad_regex": extra_low})


# -- content flags -------------------------------------------------------------

def excerpt(a, b, limit=700):
    """Short before/after excerpt: changed lines only; contact-like strings removed."""
    nd = list(difflib.ndiff(a.splitlines(), b.splitlines()))
    rem = [l[2:].strip() for l in nd if l.startswith("- ")]
    add = [l[2:].strip() for l in nd if l.startswith("+ ")]
    if not (rem or add):
        rem, add = [a], [b]
    clean = lambda ls: _PERSONAL.sub("[removed]", " / ".join(ls))[:limit]
    return clean(rem), clean(add)


def _outcome_set(f):
    return sorted(l.split(" | ")[0].strip() for l in f["primary_outcomes"].splitlines() if l.strip())


def _compare(base, cur):
    return {"elig_sim": similarity(base["eligibility_criteria"], cur["eligibility_criteria"], words=True),
            "age_sex": any(base[k] != cur[k] for k in ("min_age", "max_age", "sex", "healthy_volunteers")),
            "outcome_sim": similarity("\n".join(_outcome_set(base)), "\n".join(_outcome_set(cur))),
            "outcome_any": base["primary_outcomes"] != cur["primary_outcomes"]}


def trial_content(ctx, nct, start, completion):
    index, _ = ctgov.stored_index(ctx, nct)
    have = ctgov.stored_versions(ctx, nct)
    if not index or not have:
        return {"status": "no_versions"}
    s, e = norm_date(start), norm_date(completion)
    pre = [v for v, d, _ in index if s and d <= s]
    post_start = not pre
    base_v = pre[-1] if pre else index[0][0]
    if base_v not in have:
        return {"status": "missing_baseline", "baseline_version": base_v}
    dates = {v: d for v, d, _ in index}
    win = [v for v, d, _ in index if v > base_v and s and d > s and (not e or d <= e) and v in have]
    load = lambda v: version_fields(json.loads(have[v].read_text(encoding="utf-8")))
    fields = {v: load(v) for v in [base_v] + win}
    base = fields[base_v]
    elig_sim, outcome_sim, age_sex, minor = 1.0, 1.0, False, False
    for v in win:
        c = _compare(base, fields[v])
        elig_sim, outcome_sim = min(elig_sim, c["elig_sim"]), min(outcome_sim, c["outcome_sim"])
        age_sex, minor = age_sex or c["age_sex"], minor or c["outcome_any"]
    # v2: rule-based findings (amend.py) for every window version against the baseline
    versions_v2, cleanneg = [], True
    for v in win:
        an = amend.analyse(base, fields[v])
        subs = [x for x in an["findings"] if x["substantive"]]
        versions_v2.append({"version": v, "date": dates.get(v), "n_substantive": len(subs),
                            "n_findings": len(an["findings"]), "kinds": sorted({x["kind"] for x in subs}),
                            "n_needs_check": sum(1 for x in an["findings"] if x.get("needs_check"))})
        cleanneg = cleanneg and not subs
    best = max(versions_v2, key=lambda x: (x["n_substantive"], x["version"]), default=None)
    fl = {"elig_text": elig_sim < 0.95, "elig_age_sex": age_sex, "primary_outcome": outcome_sim < 0.9}
    fl["primary_outcome_minor"] = minor and not fl["primary_outcome"]
    changes, seq = [], [base_v] + win
    for a, b in zip(seq, seq[1:]):
        for r in diff_fields(fields[a], fields[b]):
            if r["changed"]:
                f = r["field"]
                before, after = excerpt(fields[a][f], fields[b][f])
                changes.append({"field": f, "group": "eligibility" if f in ELIGIBILITY else
                                "outcome" if f in OUTCOME else "design",
                                "from_version": a, "version": b, "date": dates.get(b),
                                "similarity": r["similarity"], "before": before, "after": after})
    return {"status": "ok", "baseline_version": base_v, "baseline_post_start": post_start,
            "window_versions": win, "min_eligibility_similarity": elig_sim,
            "min_outcome_set_similarity": outcome_sim, **fl,
            "substantive": fl["elig_text"] or fl["elig_age_sex"] or fl["primary_outcome"],
            "substantive_v2": any(x["n_substantive"] for x in versions_v2), "clean_negative": cleanneg and bool(win),
            "best_version": best["version"] if best and best["n_substantive"] else None,
            "versions_v2": versions_v2, "changes": changes}


def content_flags(ctx, pool):
    studies, sidecar = _pool_studies(ctx, pool)
    if studies is None:
        return
    out = {}
    for s in ctx.limit(studies):
        sm = ctgov.study_summary(s)
        if ctgov.stored_versions(ctx, sm["nct_id"]):
            out[sm["nct_id"]] = trial_content(ctx, sm["nct_id"], sm["start"], sm["primary_completion"])
    doc = {"schema": "content-flags/0.2", "pool": pool, "generated": iso_now(),
           "data_timestamp": sidecar.get("ctgov_data_timestamp"),
           "rule": {"baseline": "last version dated on or before start, else earliest (baseline_post_start)",
                    "window": "start < version date <= primary completion",
                    "elig_text": "criteria similarity < 0.95 vs baseline in any window version",
                    "elig_age_sex": "min/max age, sex or healthy volunteers differ",
                    "primary_outcome": "primary-outcome measure-set similarity < 0.9",
                    "primary_outcome_minor": "any other primary-outcome text change",
                    "substantive": "elig_text or elig_age_sex or primary_outcome (v1, similarity thresholds)",
                    "substantive_v2": "any substantive finding from amend.py in any window version (criterion added/removed, "
                                      "threshold, outcome, age/sex, enrolment, arms); wording-only edits are not substantive",
                    "clean_negative": "no substantive finding in any window version"},
           "trials": out}
    path = ctx.store.write_json_new(ctx.store.derived_dir() / f"content_flags_{pool}_{utc_stamp()}.json", doc)
    ok = [t for t in out.values() if t["status"] == "ok"]
    ctx.count("trials_with_versions", len(out))
    ctx.count("substantive", sum(t["substantive"] for t in ok))
    ctx.count("not_substantive", sum(not t["substantive"] for t in ok))
    ctx.count("substantive_v2", sum(t["substantive_v2"] for t in ok))
    ctx.count("clean_negative_v2", sum(t["clean_negative"] for t in ok))
    ctx.count("baseline_post_start", sum(t["baseline_post_start"] for t in ok))
    ctx.count("missing_baseline", sum(t["status"] == "missing_baseline" for t in out.values()))
    ctx.notes["derived_file"] = ctx.store.rel(path)
    interim = ctx.root / "data" / "derived" / "content_flags_copd_20261028.json"
    if interim.is_file():
        try:
            old = json.loads(interim.read_text(encoding="utf-8"))
            keys = ("elig_text", "elig_age_sex", "primary_outcome", "primary_outcome_minor")
            same = sum(1 for n, t in out.items()
                       if n in old and t["status"] == "ok" and {k for k in keys if t[k]} == set(old[n]))
            ctx.notes["agreement_with_interim"] = f"{same} of {len(old)} trials have identical flag sets"
        except (ValueError, TypeError):
            pass
