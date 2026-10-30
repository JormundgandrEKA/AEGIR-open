"""status, tally, attribution, snapshot."""
import csv
import io
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import ctgov, pmc
from aegir_core.core import read_jsonl, sha256, utc_stamp, iso_now
from aegir_core.http import NCBI_HOSTS

CATALOGUES = ["fetch_log", "studies", "versions", "articles", "licences", "links", "searches"]


def status(ctx, check_key=False):
    c = {}
    for name in CATALOGUES:
        c[name] = len(ctx.store.records(name + ".jsonl"))
    ctx.counts.update({f"lines_{k}": v for k, v in c.items()})
    last, failures = {}, 0
    for r in ctx.store.records("fetch_log.jsonl"):
        host = urlsplit(r.get("url", "")).hostname
        last[host] = r.get("ts")
        if r.get("error") or (r.get("status") or 0) >= 400:
            failures += 1
    ctx.count("failed_requests_logged", failures)
    size = sum(p.stat().st_size for p in ctx.store.data.rglob("*") if p.is_file()) if ctx.store.data.is_dir() else 0
    ctx.notes["last_fetch_by_host"] = last
    ctx.notes["data_bytes"] = size
    ctx.notes["ncbi_key_configured"] = bool(ctx.client.key)
    ctx.notes["ncbi_email_configured"] = bool(ctx.client.email)
    ctx.notes["ncbi_rate_limit_per_s"] = 10 if ctx.client.key else 3
    if check_key:
        if not ctx.client.key:
            ctx.notes["key_valid"] = False
            return
        r = ctx.client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi", {"db": "pubmed", "retmode": "json"})
        if r is None:
            ctx.notes["key_valid"] = None
            return
        ctx.client.log(r)
        bad = (not r.ok) or b"API key invalid" in r.body
        ctx.notes["key_valid"] = not bad
        if bad:
            ctx.error(f"NCBI rejected the request (HTTP {r.status}); check the API key")


def _labels(ctx):
    """Latest label per (labeller, id, track), read from data/labels/<labeller>/labels.jsonl."""
    out = {}
    d = ctx.root / "data" / "labels"
    if d.is_dir():
        for f in sorted(d.glob("*/labels.jsonl")):
            for r in read_jsonl(f):
                if r.get("id") and r.get("label"):
                    out[(r.get("labeller") or f.parent.name, r["id"], r.get("track"))] = r
    return out


def confirmation(labels):
    """Confirmed = two different human labellers agree; model and provisional labels never count."""
    by_case = {}
    for (who, i, track), r in labels.items():
        if r.get("provisional") or str(who).startswith("model:"):
            continue
        by_case.setdefault((i, track), {})[who] = r["label"]
    conf, disagree, single = {}, [], 0
    for key, votes in by_case.items():
        if len(votes) < 2:
            single += 1
        elif len(set(votes.values())) == 1:
            conf[key] = next(iter(votes.values()))
        else:
            disagree.append(key)
    return conf, disagree, single


def tally(ctx):
    studies = ctx.store.latest("studies.jsonl", "nct_id")
    arts = ctx.store.latest("articles.jsonl", "pmid")
    lic = ctx.store.latest("licences.jsonl", "pmcid")
    links = ctx.store.records("links.jsonl")
    labels = _labels(ctx)
    rows = []

    def add(section, item, n):
        rows.append({"section": section, "item": item, "count": n})

    add("stored", "studies_fetched", sum(1 for s in studies.values() if s.get("status_code") == 200))
    hist = ctx.store.raw_dir("ctgov", "history")
    add("stored", "trials_with_history_index", sum(1 for d in hist.iterdir() if d.is_dir()) if hist.is_dir() else 0)
    add("stored", "trials_with_version_files",
        sum(1 for d in hist.iterdir() if d.is_dir() and ctgov.stored_versions(ctx, d.name)) if hist.is_dir() else 0)
    add("stored", "articles", len(arts))
    add("stored", "articles_with_pmcid", sum(1 for a in arts.values() if a.get("pmcid")))
    add("stored", "licences_checked", len(lic))
    add("stored", "links", len({(r["nct_id"], r["pmid"]) for r in links}))
    for g, n in sorted(Counter(r["grade"] for r in lic.values()).items()):
        add("licence_grade", g, n)
    add("usable", "articles_redistributable", sum(1 for r in lic.values() if not r["do_not_redistribute"]))
    conf, disagree, single = confirmation(labels)
    human = {k: r for k, r in labels.items() if not (r.get("provisional") or str(k[0]).startswith("model:"))}
    for (track, label), n in sorted(Counter((str(k[2]), r["label"]) for k, r in human.items()).items()):
        add(f"user_labelled_track_{track}", label, n)
    for (track, label), n in sorted(Counter((str(k[1]), v) for k, v in conf.items()).items()):
        add(f"confirmed_track_{track}", label, n)
    add("labels", "cases_with_one_human_label", single)
    add("labels", "cases_with_disagreement", len(disagree))
    add("labels", "model_or_provisional_labels", len(labels) - len(human))
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=["section", "item", "count"], lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    path = ctx.store.write_new(ctx.store.derived_dir() / f"tally_{utc_stamp()}.csv", buf.getvalue().encode())
    ctx.notes["derived_file"] = ctx.store.rel(path)
    ctx.notes["tally"] = {f"{r['section']}:{r['item']}": r["count"] for r in rows}


def attribution(ctx):
    lic = ctx.store.latest("licences.jsonl", "pmcid")
    arts = {a["pmcid"]: a for a in ctx.store.latest("articles.jsonl", "pmid").values() if a.get("pmcid")}
    searches = [r for r in ctx.store.records("searches.jsonl") if r.get("source") == "ctgov"]
    lines = ["# AEGIR data attribution", "", f"Generated {iso_now()} by aegir-ran {ctx.cfg.get('tool_name', '')}.", "",
             "## ClinicalTrials.gov", "",
             "Registry data come from ClinicalTrials.gov (U.S. National Library of Medicine), "
             "https://clinicaltrials.gov, retrieved on the dates in each file's `.meta.json` sidecar "
             "(`ctgov_data_timestamp` gives the registry's own data date). Stored files are dated snapshots, "
             "not current data. Modification: names, emails and phone numbers of contacts and officials were "
             "removed before storage. NLM does not endorse this project.", ""]
    for s in searches:
        lines.append(f"- query `{s['query_id']}`: {s['n_results']} records, retrieved {s.get('ts', '')}")
    lines += ["", "## Articles (PMC licence per article)", ""]
    for pmcid, r in sorted(lic.items()):
        a = arts.get(pmcid, {})
        lines.append(f"- {pmcid} (PMID {r.get('pmid')}): {a.get('title', '')[:120]} — {a.get('journal', '')}; "
                     f"licence {r.get('licence') or 'undetermined'} {r.get('licence_url') or ''}; "
                     f"grade {r['grade']}{'; DO NOT REDISTRIBUTE' if r['do_not_redistribute'] else ''}")
    path = ctx.store.write_new(ctx.root / f"ATTRIBUTION_{utc_stamp()}.md", ("\n".join(lines) + "\n").encode("utf-8"))
    ctx.notes["file"] = ctx.store.rel(path)
    ctx.count("articles_listed", len(lic))


def snapshot(ctx, snap_id, query_id):
    """Copy the raw files behind a named query into data/snapshots/<id>/ with a manifest."""
    q = None
    qf = ctx.root / "config" / "queries" / f"{query_id}.json"
    if qf.is_file():
        q = json.loads(qf.read_text(encoding="utf-8"))
    if q is None:
        ctx.error(f"{query_id} is not a named query in config/queries; scratch pulls are never gold-set eligible")
        return
    dest = ctx.root / "data" / "snapshots" / snap_id
    if dest.exists():
        ctx.error(f"snapshot {snap_id} already exists; snapshots are never replaced")
        return
    ent = ctx.store.latest("searches.jsonl", "query_id").get(query_id)
    if not ent or ent.get("scratch"):
        ctx.error(f"no stored (non-scratch) search for {query_id}")
        return
    files = [ent["file"]]
    if q["source"] == "ctgov":
        sf = ctx.root / ent["file"]
        for s in json.loads(sf.read_text(encoding="utf-8")).get("studies", []):
            nct = ctgov.study_summary(s)["nct_id"]
            d = ctx.root / "data" / "raw" / "ctgov" / "history" / nct
            if d.is_dir():
                files += [ctx.store.rel(p) for p in sorted(d.iterdir()) if p.is_file()]
    else:
        pm = json.loads((ctx.root / ent["file"]).read_text(encoding="utf-8")).get("pmids", [])
        lic = ctx.store.latest("licences.jsonl", "pmid")
        for pmid in pm:
            d = ctx.root / "data" / "raw" / "pubmed" / "article" / pmid
            if d.is_dir():
                files += [ctx.store.rel(p) for p in sorted(d.iterdir()) if p.is_file()]
            rec = lic.get(pmid)
            if rec and rec.get("file"):
                files.append(rec["file"])
    manifest = {"snapshot_id": snap_id, "query_id": query_id, "created": iso_now(), "files": []}
    lic_by_file = {r.get("file"): r for r in ctx.store.records("licences.jsonl")}
    for rel in dict.fromkeys(files):
        src = ctx.root / rel
        if not src.is_file():
            continue
        # sidecars travel with their file
        for s in (src, src.with_name(src.name + ".meta.json")):
            if not s.is_file():
                continue
            target = dest / s.relative_to(ctx.root / "data")
            if not ctx.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(s, target)
                ctx.store.files_written += 1
            manifest["files"].append({"path": target.relative_to(dest).as_posix(),
                                      "sha256": sha256(s.read_bytes())})
    ctx.store.write_json_new(dest / "manifest.json", manifest)
    ctx.count("snapshot_files", len(manifest["files"]))


def log_minutes(ctx, track, minutes, note=""):
    """Manual field for the efficiency report: user minutes spent on a track."""
    path = ctx.root / "data" / "labels" / "effort.jsonl"
    if not ctx.dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"track": track, "minutes": minutes, "note": note, "ts": iso_now()}) + "\n")
    ctx.count("minutes_logged", minutes)


def efficiency(ctx):
    """Per track: requests used, user minutes, candidate cases, confirmed cases."""
    req = Counter()
    for r in ctx.store.records("fetch_log.jsonl"):
        host = urlsplit(r.get("url", "")).hostname
        req[1 if host == "clinicaltrials.gov" else 2] += 1
    manual = Counter()
    for r in read_jsonl(ctx.root / "data" / "labels" / "effort.jsonl"):
        manual[int(r["track"])] += float(r["minutes"])
    active = 0.0
    for f in (ctx.root / "data" / "labels").glob("*/sessions/*.jsonl"):
        active += sum(float(e.get("active_seconds") or 0) for e in read_jsonl(f) if e.get("type") in ("save", "skip"))
    cand = Counter()
    for f in reversed(sorted((ctx.root / "data" / "derived").glob("content_flags_*.json"))):
        doc = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and str(doc.get("schema", "")).startswith("content-flags/"):     # skips the interim file
            cand[1] = sum(1 for t in doc["trials"].values() if t.get("substantive_v2", t.get("substantive")))
            break
    for ent in ctx.store.latest("searches.jsonl", "query_id").values():
        if ent.get("source") == "pubmed" and not ent.get("scratch"):
            cand[2] += ent.get("n_results", 0)
    conf, _, _ = confirmation(_labels(ctx))
    confirmed = Counter(k[1] for k in conf)
    rows = [{"track": t, "requests_used": req[t], "user_minutes_manual": manual[t],
             "user_minutes_labelling_active": round(active / 60, 1) if t == 1 else 0,
             "candidate_cases": cand[t], "confirmed_cases": confirmed[t]} for t in (1, 2)]
    buf = io.StringIO(newline="")
    cols = list(rows[0])
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    path = ctx.store.write_new(ctx.store.derived_dir() / f"efficiency_{utc_stamp()}.csv", buf.getvalue().encode())
    ctx.notes["derived_file"] = ctx.store.rel(path)
    ctx.notes["rows"] = rows
    ctx.notes["track_by_host"] = "track 1 = clinicaltrials.gov requests; track 2 = NCBI and Europe PMC requests"
