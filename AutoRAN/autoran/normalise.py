"""Pages to one compact record per trial, with `input_state` (hindsight contamination) and the personal-data rules."""
import re
from pathlib import Path

from aegir_ran import amend, textclean

from .core import Paths, iso_now, iter_jsonl, norm_date, read_gz_json, utc_stamp, write_jsonl
from .fetch import page_files

AGE = re.compile(r"(\d+(?:\.\d+)?)\s*(year|month|week|day|hour|minute)", re.I)
TO_YEARS = {"year": 1.0, "month": 1 / 12, "week": 1 / 52, "day": 1 / 365, "hour": 1 / 8760, "minute": 1 / 525600}


def age_years(s):
    m = AGE.search(s or "")
    return round(float(m.group(1)) * TO_YEARS[m.group(2).lower()], 3) if m else None


def history_index(cfg, root):
    """{NCT: earliest version date} from RAN's browser-collected histories, if any are reachable. Names only; nothing is fetched."""
    out = {}
    from . import settings
    for rel in ([settings.get("history_dir")] if settings.get("history_dir") else []) + list(cfg.get("history_roots", [])):
        d = (Path(root) / rel).resolve()
        if not d.is_dir():
            continue
        from aegir_ran import ctgov
        for sub in d.iterdir():
            if not sub.is_dir() or not sub.name.startswith("NCT"):
                continue
            idx = sorted(f for f in sub.glob("index_*.json") if not f.name.endswith(".meta.json"))
            if not idx:
                continue
            try:
                import json
                entries = ctgov.parse_index(json.loads(idx[-1].read_text(encoding="utf-8")))
            except (ValueError, OSError):
                continue
            if entries:
                out[sub.name] = min(e[1] for e in entries if e[1]) if any(e[1] for e in entries) else ""
    return out


def count_criteria(text):
    items = amend.split_items(textclean.clean_text(text))
    return sum(1 for s, _ in items if s == "inclusion"), sum(1 for s, _ in items if s == "exclusion")


def normalise_study(s, page, pos, hist):
    ps = s.get("protocolSection", {})
    idm, st = ps.get("identificationModule", {}), ps.get("statusModule", {})
    sp = ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
    dm = ps.get("designModule", {})
    di = dm.get("designInfo", {})
    ei = dm.get("enrollmentInfo", {})
    el = ps.get("eligibilityModule", {})
    ao = ps.get("armsInterventionsModule", {})
    locs = ps.get("contactsLocationsModule", {}).get("locations", []) or []
    ders = s.get("derivedSection", {}).get("conditionBrowseModule", {})
    nct = idm.get("nctId")
    start = norm_date(st.get("startDateStruct", {}).get("date"))
    last = norm_date(st.get("lastUpdatePostDateStruct", {}).get("date"))
    n_inc, n_exc = count_criteria(el.get("eligibilityCriteria"))
    text = textclean.clean_text(el.get("eligibilityCriteria"))
    countries = sorted({l.get("country") for l in locs if l.get("country")})
    # input_state: was this the protocol as first written?
    state, baseline_post = "current", False
    if nct in hist:
        first = norm_date(hist[nct])
        if first and start and first <= start:
            state = "first_version"
        else:
            baseline_post = True
    first_posted = norm_date(st.get("studyFirstPostDateStruct", {}).get("date"))
    if state == "current" and first_posted and last and last <= first_posted:
        state = "never_updated"          # no update was ever posted: this record IS the first submission
    elif state == "current" and start and last and last <= start:
        state = "current_unchanged"
    refs = [r.get("pmid") for r in (ps.get("referencesModule", {}).get("references", []) or []) if r.get("pmid")]
    return {
        "nct_id": nct, "title": (idm.get("briefTitle") or "")[:220], "status": st.get("overallStatus"),
        "why_stopped": st.get("whyStopped") or "", "start": start,
        "primary_completion": norm_date(st.get("primaryCompletionDateStruct", {}).get("date")),
        "completion": norm_date(st.get("completionDateStruct", {}).get("date")),
        "first_posted": norm_date(st.get("studyFirstPostDateStruct", {}).get("date")), "last_update": last,
        "phases": dm.get("phases") or [], "sponsor_class": sp.get("class") or "", "sponsor": sp.get("name") or "",
        "n_sites": len(locs), "countries": countries,
        "enrollment": {"type": ei.get("type") or "", "count": ei.get("count")},
        "eligibility": {"n_incl": n_inc, "n_excl": n_exc, "n_words": len(text.split()), "min_age_y": age_years(el.get("minimumAge")),
                        "max_age_y": age_years(el.get("maximumAge")), "sex": el.get("sex") or "",
                        "healthy_volunteers": el.get("healthyVolunteers"), "std_ages": el.get("stdAges") or []},
        "n_primary": len(ps.get("outcomesModule", {}).get("primaryOutcomes", []) or []),
        "n_arms": len(ao.get("armGroups", []) or []), "allocation": di.get("allocation") or "",
        "masking": di.get("maskingInfo", {}).get("masking") or "", "purpose": di.get("primaryPurpose") or "",
        "intervention_types": sorted({i.get("type") for i in ao.get("interventions", []) or [] if i.get("type")}),
        "conditions": (ps.get("conditionsModule", {}).get("conditions") or [])[:6],
        "mesh": [m.get("term") for m in ders.get("meshes", []) or []][:8],
        "ancestors": [m.get("term") for m in ders.get("ancestors", []) or []],
        "pmids": refs[:6], "input_state": state, "baseline_post_start": baseline_post,
        "registration": ("prospective" if first_posted and start and first_posted <= start else "retrospective") if first_posted and start else "unknown",
        "source": "ctgov_current", "grade": "A+", "page": page, "pos": pos}


def normalise(ctx, cfg, partial=False):
    paths = Paths(ctx.root).ensure()
    hist = history_index(cfg, ctx.root)
    runs = page_files(ctx, partial=partial)
    stamp = utc_stamp()
    out = paths.derived / f"trials_{stamp}.jsonl"
    seen = 0

    def rows():
        nonlocal seen
        for run, kind, files in runs:
            for f in files:
                rel = ctx.store.rel(f)
                data = read_gz_json(f)
                for i, s in enumerate(data["studies"]):
                    seen += 1
                    yield normalise_study(s, rel, i, hist)
    n = write_jsonl(out, rows())
    states = {}
    for r in iter_jsonl(out):
        states[r["input_state"]] = states.get(r["input_state"], 0) + 1
    ctx.store.append("autoran_stages.jsonl", {"stage": "normalise", "file": ctx.store.rel(out), "n": n, "ts": iso_now(), "input_state": states})
    ctx.count("trials", n)
    ctx.notes["input_state"] = states
    ctx.notes["history_trials_found"] = len(hist)
    return {"file": str(out), "trials": n, "input_state": states}


def load_trials(paths, latest_wins=True):
    """Newest trials file as {nct: record}. Delta runs write later lines for the same trial; the last line wins."""
    f = paths.latest("trials_*.jsonl")
    if not f:
        raise FileNotFoundError("no trials file yet; run `autoran normalise`")
    out = {}
    for r in iter_jsonl(f):
        out[r["nct_id"]] = r
    return out
