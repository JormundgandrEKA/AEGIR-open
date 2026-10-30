"""ClinicalTrials.gov API v2: page through the scope, store gzip pages with sidecars. Resumable; delta by LastUpdatePostDate."""
import json
import gzip

from aegir_ran import ctgov as rctgov

from . import __version__
from .core import Paths, install_gzip, iso_now, utc_stamp

API = "https://clinicaltrials.gov/api/v2/studies"
TERMS = "https://clinicaltrials.gov/about-site/terms-conditions"


def build_params(cfg, since=None, token=None, first=False):
    sc = cfg["scope"]
    adv = f"AREA[StudyType]INTERVENTIONAL AND AREA[StartDate]RANGE[{sc['start_from']},MAX]"
    if sc["phases"] != "all":
        adv += " AND (" + " OR ".join(f"AREA[Phase]{p}" for p in sc["phases"]) + ")"
    if since:
        adv += f" AND AREA[LastUpdatePostDate]RANGE[{since},MAX]"
    p = {"filter.advanced": adv, "filter.overallStatus": "|".join(sc["statuses"]), "pageSize": cfg["page_size"],
         "fields": ",".join(cfg["fields"]), "format": "json"}
    if first:
        p["countTotal"] = "true"
    if token:
        p["pageToken"] = token
    return p


def _open_run(ctx, kind, resume):
    """Continue the newest unfinished run of this kind, or start a new one. Returns (run, next page number, token, since)."""
    runs = ctx.store.latest("autoran_runs.jsonl", "run")
    if resume:
        open_runs = [r for r in runs.values() if r["kind"] == kind and r["status"] == "started"]
        if open_runs:
            r = sorted(open_runs, key=lambda x: x["run"])[-1]
            pages = [p for p in ctx.store.records("autoran_pages.jsonl") if p["run"] == r["run"]]
            last = pages[-1] if pages else None
            return r["run"], (last["page"] + 1 if last else 1), (last.get("next_token") if last else None), r.get("since")
    since = None
    if kind == "delta":
        done = sorted((r for r in runs.values() if r["status"] == "done"), key=lambda x: x["run"])
        if not done:
            raise ValueError("no finished full run to update from; run `autoran fetch --full` first")
        since = done[-1]["started"][:10]
    run = utc_stamp()
    ctx.store.append("autoran_runs.jsonl", {"run": run, "kind": kind, "status": "started", "since": since,
                                            "started": iso_now(), "version": __version__})
    return run, 1, None, since


def fetch(ctx, cfg, kind="full", resume=True, max_pages=None):
    """Page the API. Each page is stored as it arrives, so a stopped run resumes at the next token."""
    install_gzip()
    run, page, token, since = _open_run(ctx, kind, resume) if not ctx.dry_run else ("dry", 1, None, None)
    ts = rctgov.data_timestamp(ctx)
    total, n_studies, n_pages = None, 0, 0
    while True:
        params = build_params(cfg, since=since, token=token, first=(page == 1))
        r = ctx.client.get(API, params)
        if r is None:                      # --dry-run / --offline
            ctx.notes["first_params"] = {k: v for k, v in params.items() if k != "fields"}
            return {"run": run, "pages": 0, "studies": 0}
        if not r.ok:
            ctx.error(f"page {page}: HTTP {r.status} {r.error or ''}")
            break
        data = r.json()
        studies = data.get("studies", [])
        for s in studies:
            rctgov.strip_personal(s)
        total = data.get("totalCount", total)
        body = gzip.compress(json.dumps({"studies": studies, "totalCount": total}, separators=(",", ":")).encode("utf-8"), 6)
        path = ctx.store.save_raw(
            ["ctgov", "autoran", run], f"page_{page:04d}.json.gz", body,
            r.meta(source="ClinicalTrials.gov", terms_url=TERMS, grade="A+", ctgov_data_timestamp=ts, run=run, kind=kind,
                   page=page, n_studies=len(studies), since=since,
                   modifications="limited field set requested; contact fields not requested; stored gzip-compressed"))
        ctx.client.log(r, ctx.store.rel(path))
        token = data.get("nextPageToken")
        ctx.store.append("autoran_pages.jsonl", {"run": run, "kind": kind, "page": page, "next_token": token, "n": len(studies),
                                                 "total": total, "file": ctx.store.rel(path), "ts": iso_now()})
        n_studies += len(studies)
        n_pages += 1
        ctx.count("pages", 1)
        ctx.count("studies", len(studies))
        page += 1
        if not token:
            ctx.store.append("autoran_runs.jsonl", {"run": run, "kind": kind, "status": "done", "since": since, "total": total,
                                                    "pages": page - 1, "finished": iso_now(), "started": _started(ctx, run)})
            break
        if max_pages and n_pages >= max_pages:
            ctx.notes["stopped"] = f"--max-pages {max_pages} reached; run again to resume"
            break
    ctx.notes.update({"run": run, "total_reported": total, "data_timestamp": ts})
    return {"run": run, "pages": n_pages, "studies": n_studies, "total": total}


def _started(ctx, run):
    for r in ctx.store.records("autoran_runs.jsonl"):
        if r["run"] == run and r["status"] == "started":
            return r["started"]
    return iso_now()


def page_files(ctx, paths=None, partial=False):
    """(run, kind, [page file Paths]) for the newest full run and every delta run after it, oldest first."""
    runs = sorted(ctx.store.latest("autoran_runs.jsonl", "run").values(), key=lambda r: r["run"])
    fulls = [r for r in runs if r["kind"] == "full" and (partial or r["status"] == "done")]
    if not fulls:
        raise ValueError("no finished full fetch yet; run `autoran fetch --full`")
    base = fulls[-1]["run"]
    chosen = [r for r in runs if r["run"] >= base and (r["status"] == "done" or (partial and r["run"] == base))]
    pages = ctx.store.records("autoran_pages.jsonl")
    out = []
    for r in chosen:
        files = sorted({p["file"] for p in pages if p["run"] == r["run"]})
        out.append((r["run"], r["kind"], [ctx.root / f for f in files]))
    return out
