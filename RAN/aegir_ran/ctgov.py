"""ClinicalTrials.gov: search, study, history (section 3.1), history import."""
import json
import re
from pathlib import Path

from .core import NCT_RE, VERSION, iso_now, read_jsonl, sha256, utc_stamp
from .http import HostBlocked

API = "https://clinicaltrials.gov/api/v2"
INT = "https://clinicaltrials.gov/api/int"
TERMS = "https://clinicaltrials.gov/about-site/terms-conditions"
PERSONAL_NOTE = "contacts, officials and investigator names removed (R11)"


def data_timestamp(ctx):
    """Registry data timestamp (one request per process, cached)."""
    if "ctgov_ts" not in ctx.cache:
        ctx.cache["ctgov_ts"] = None
        r = ctx.client.get(f"{API}/version")
        if r is not None and r.ok:
            try:
                ctx.cache["ctgov_ts"] = r.json().get("dataTimestamp")
            except ValueError:
                pass
    return ctx.cache["ctgov_ts"]


def strip_personal(study):
    """Remove names, emails and phones (R11). Returns True if anything was removed."""
    changed = False
    ps = study.get("protocolSection", {})
    cl = ps.get("contactsLocationsModule")
    if isinstance(cl, dict):
        for k in ("centralContacts", "overallOfficials"):
            if k in cl:
                del cl[k]
                changed = True
        for loc in cl.get("locations", []) or []:
            if isinstance(loc, dict) and "contacts" in loc:
                del loc["contacts"]
                changed = True
    rp = ps.get("sponsorCollaboratorsModule", {}).get("responsibleParty")
    if isinstance(rp, dict):
        for k in ("investigatorFullName", "investigatorTitle", "investigatorAffiliation"):
            if k in rp:
                del rp[k]
                changed = True
    return changed


def study_summary(study):
    ps = study.get("protocolSection", {})
    st = ps.get("statusModule", {})
    return {
        "nct_id": ps.get("identificationModule", {}).get("nctId"),
        "status": st.get("overallStatus"),
        "phase": ps.get("designModule", {}).get("phases"),
        "start": st.get("startDateStruct", {}).get("date"),
        "primary_completion": st.get("primaryCompletionDateStruct", {}).get("date"),
        "sponsor_class": ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("class"),
    }


def _meta(ctx, resp, grade_key, **extra):
    return resp.meta(source="ClinicalTrials.gov", terms_url=TERMS, ctgov_data_timestamp=data_timestamp(ctx),
                     grade=ctx.cfg.get("source_grades", {}).get(grade_key), **extra)


def search(ctx, query_id=None, params=None):
    """Run a named query (or an exploratory one, which is forced into data/scratch/)."""
    if query_id:
        q = ctx.query(query_id, "ctgov")
        params = dict(q["params"])
    else:
        if not params:
            raise ValueError("give --query-id, or --param key=value for an exploratory search")
        ctx.store.scratch = True
        ctx.store.base = ctx.store.data / "scratch"
        query_id = "adhoc"
    if not ctx.refresh and query_id != "adhoc" and query_id in ctx.store.latest("searches.jsonl", "query_id"):
        ctx.count("search_cached")
        ctx.notes["hint"] = "search already catalogued; use --refresh for a new dated snapshot"
        return
    base = dict(params, pageSize=1000, countTotal="true", format="json")
    studies, token, first, pages, total = [], None, None, 0, None
    while True:
        p = dict(base)
        if token:
            p["pageToken"] = token
        r = ctx.client.get(f"{API}/studies", p)
        if r is None:
            return
        if not r.ok:
            ctx.error(f"search {query_id}: HTTP {r.status} {r.error or ''}")
            return
        first = first or r
        data = r.json()
        studies.extend(data.get("studies", []))
        total = data.get("totalCount", total)
        pages += 1
        ctx.client.log(r)
        token = data.get("nextPageToken")
        if not token or (ctx.max_items and len(studies) >= ctx.max_items):
            break
    removed = any([strip_personal(s) for s in studies])
    studies = ctx.limit(studies)
    out = {"query_id": query_id, "params": params, "totalCount": total, "pages": pages, "studies": studies}
    body = json.dumps(out, ensure_ascii=False).encode("utf-8")
    path = ctx.store.save_raw(
        ["ctgov", "search", query_id], utc_stamp() + ".json", body,
        _meta(ctx, first, "ctgov_search", query_id=query_id, params=params, pages=pages,
              modifications=PERSONAL_NOTE if removed else None))
    ctx.store.append("searches.jsonl", {"query_id": query_id, "source": "ctgov", "params": params,
                                        "n_results": len(studies), "file": ctx.store.rel(path),
                                        "ts": iso_now(), "scratch": ctx.store.scratch})
    ctx.count("studies_in_search", len(studies))


def study(ctx, ncts):
    done = ctx.store.latest("studies.jsonl", "nct_id")
    for nct in ctx.limit(ncts):
        nct = nct.upper()
        if not NCT_RE.fullmatch(nct):
            ctx.error(f"not an NCT number: {nct}")
            continue
        if not ctx.refresh and done.get(nct, {}).get("status_code") == 200:
            ctx.count("study_cached")
            continue
        r = ctx.client.get(f"{API}/studies/{nct}", {"format": "json"})
        if r is None:
            continue
        if not r.ok:
            ctx.error(f"{nct}: HTTP {r.status} {r.error or ''}")
            ctx.store.append("studies.jsonl", {"nct_id": nct, "status_code": r.status, "file": None})
            continue
        s = r.json()
        removed = strip_personal(s)
        body = json.dumps(s, ensure_ascii=False).encode("utf-8")
        path = ctx.store.save_raw(
            ["ctgov", "study", nct], utc_stamp() + ".json", body,
            _meta(ctx, r, "ctgov_study", modifications=PERSONAL_NOTE if removed else None,
                  source_sha256=sha256(r.body)))
        ctx.client.log(r, ctx.store.rel(path))
        ctx.store.append("studies.jsonl", {**study_summary(s), "nct_id": nct, "status_code": 200,
                                           "file": ctx.store.rel(path), "ts": iso_now()})
        ctx.count("studies_fetched")


# -- stored-record access ------------------------------------------------

def find_study_record(ctx, nct):
    """Latest stored current record: an individual study file, else the newest search file holding it."""
    ent = ctx.store.latest("studies.jsonl", "nct_id").get(nct)
    if ent and ent.get("file"):
        p = ctx.root / ent["file"]
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8")), p
    idx = ctx.cache.get("search_index")
    if idx is None:
        idx = {}
        for sid, ent in sorted(ctx.store.latest("searches.jsonl", "query_id").items()):
            if ent.get("source") != "ctgov" or not ent.get("file"):
                continue
            p = ctx.root / ent["file"]
            if p.is_file():
                for s in json.loads(p.read_text(encoding="utf-8")).get("studies", []):
                    n = study_summary(s)["nct_id"]
                    if n:
                        idx[n] = (s, p)
        ctx.cache["search_index"] = idx
    return idx.get(nct, (None, None))


# -- history ------------------------------------------------------------

def parse_index(obj):
    """[(version, date, module_labels)] from a history index; tolerant of key naming."""
    items = obj.get("changes") if isinstance(obj, dict) else obj
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        v = it.get("version", it.get("versionNumber"))
        d = it.get("date") or it.get("versionDate") or ""
        if v is not None:
            out.append((int(v), str(d)[:10], it.get("moduleLabels") or []))
    return sorted(out)


def stored_index(ctx, nct):
    files = sorted(f for f in (ctx.store.raw_dir("ctgov", "history", nct).glob("index_*.json"))
                   if not f.name.endswith(".meta.json"))
    p = files[-1] if files else None
    return (parse_index(json.loads(p.read_text(encoding="utf-8"))), p) if p else ([], None)


def stored_versions(ctx, nct):
    """{version: path} for stored version files."""
    out = {}
    for f in ctx.store.raw_dir("ctgov", "history", nct).glob("v*.json"):
        m = re.fullmatch(r"v(\d+)\.json", f.name)
        if m:
            out[int(m.group(1))] = f
    return out


def _parse_date(s, end=False):
    from datetime import date
    import calendar
    parts = [int(x) for x in (s or "")[:10].split("-") if x.isdigit()]
    if not parts:
        return None
    y = parts[0]
    m = parts[1] if len(parts) > 1 else (12 if end else 1)
    d = parts[2] if len(parts) > 2 else (calendar.monthrange(y, m)[1] if end else 1)
    return date(y, m, d)


def needed_versions(index, start, completion):
    """Versions needed for diffs: last at/before start plus every one dated inside the window."""
    s, e = _parse_date(start), _parse_date(completion, end=True)
    if not index:
        return []
    pre = [v for v, d, _ in index if s and _parse_date(d) and _parse_date(d) <= s]
    need = set(pre[-1:])
    for v, d, _ in index:
        dd = _parse_date(d)
        if dd and s and e and s < dd <= e:
            need.add(v)
    return sorted(need)


def history(ctx, ncts, versions="window"):
    done_idx = set()
    for nct in ctx.limit(ncts):
        nct = nct.upper()
        r = ctx.client.get(f"{INT}/studies/{nct}/history")
        if r is None:
            continue
        if r.status == 403:
            ctx.error("registry history endpoint declined this scripted client (HTTP 403). Not working around it: "
                      "collect histories in your own browser and use `ctgov import-history` (design 3.1).")
            return
        if not r.ok:
            ctx.error(f"{nct}: history index HTTP {r.status} {r.error or ''}")
            continue
        path = ctx.store.save_raw(["ctgov", "history", nct], f"index_{utc_stamp()}.json", r.body,
                                  _meta(ctx, r, "ctgov_history"))
        ctx.client.log(r, ctx.store.rel(path))
        index = parse_index(r.json())
        if versions == "index":
            continue
        if versions == "all":
            want = [v for v, _, _ in index]
        else:
            rec, _ = find_study_record(ctx, nct)
            sm = study_summary(rec) if rec else {}
            want = needed_versions(index, sm.get("start"), sm.get("primary_completion"))
        have = stored_versions(ctx, nct)
        labels = {v: (d, l) for v, d, l in index}
        for v in want:
            if v in have:
                continue
            rv = ctx.client.get(f"{INT}/studies/{nct}/history/{v}")
            if rv is None or not rv.ok:
                if rv is not None:
                    ctx.error(f"{nct} v{v}: HTTP {rv.status}")
                continue
            p = ctx.store.save_raw(["ctgov", "history", nct], f"v{v}.json", rv.body,
                                   _meta(ctx, rv, "ctgov_history"))
            ctx.client.log(rv, ctx.store.rel(p))
            ctx.store.append("versions.jsonl", {"nct_id": nct, "version": v, "date": labels.get(v, ("", []))[0],
                                                "module_labels": labels.get(v, ("", []))[1],
                                                "file": ctx.store.rel(p)})
            ctx.count("versions_fetched")
        ctx.count("history_indexes")


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def import_history(ctx, files):
    """Ingest history JSON saved from the user's own browser session.

    Accepted shapes per file:
      {"nct_id": "NCT...", "index": {...}, "versions": {"1": {...}, "2": {...}}}   (bundle)
      a history index ({"changes": [...]}) named like NCT01234567_index.json
      a single version record named like NCT01234567_v3.json (or containing nctId and a version number)
    """
    expanded = []
    for fp in files:
        fp = Path(fp)
        expanded += sorted(fp.glob("*.json")) if fp.is_dir() else [fp]
    for fp in ctx.limit(expanded):
        p = Path(fp)
        try:
            raw = p.read_bytes()
            obj = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError) as e:
            ctx.error(f"{p.name}: unreadable ({e})")
            continue
        nct_m = NCT_RE.search(p.name)
        nct = (obj.get("nct_id") or obj.get("nctId")) if isinstance(obj, dict) else None
        nct = nct or (nct_m.group(0) if nct_m else None) or _find_key(obj, "nctId")
        if not nct or not NCT_RE.fullmatch(str(nct)):
            ctx.error(f"{p.name}: cannot determine the NCT number (put it in the file name)")
            continue
        extra = {"collected_via": "user browser", "import_file": p.name, "grade": ctx.cfg["source_grades"]["ctgov_history"],
                 "source": "ClinicalTrials.gov", "terms_url": TERMS, "url": None,
                 "browser_provenance": obj.get("provenance") if isinstance(obj, dict) else None}
        todo = []
        if isinstance(obj, dict) and "versions" in obj:
            if obj.get("index") is not None:
                todo.append(("index", None, obj["index"]))
            vs = obj["versions"]
            for k, v in (vs.items() if isinstance(vs, dict) else enumerate(vs, 1)):
                todo.append(("version", int(k), v))
        elif isinstance(obj, dict) and "changes" in obj or isinstance(obj, list):
            todo.append(("index", None, obj))
        else:
            vm = re.search(r"v(?:ersion)?[_-]?(\d+)", p.stem, re.I)
            v = vm.group(1) if vm else obj.get("version") if isinstance(obj, dict) else None
            if v is None:
                ctx.error(f"{p.name}: version number unknown (name the file NCT..._v<N>.json)")
                continue
            todo.append(("version", int(v), obj))
        labels = {a: (b, c) for a, b, c in stored_index(ctx, nct)[0]}
        for kind, v, o in todo:
            body = json.dumps(o, ensure_ascii=False).encode("utf-8")
            if kind == "index":
                labels = {a: (b, c) for a, b, c in parse_index(o)}
                ctx.store.save_raw(["ctgov", "history", nct], f"index_{utc_stamp()}.json", body, dict(extra))
                ctx.count("imported_indexes")
            else:
                if v in stored_versions(ctx, nct):
                    ctx.count("version_already_stored")
                    continue
                path = ctx.store.save_raw(["ctgov", "history", nct], f"v{v}.json", body, dict(extra))
                ctx.store.append("versions.jsonl", {"nct_id": nct, "version": v,
                                                    "date": labels.get(v, ("", []))[0],
                                                    "module_labels": labels.get(v, ("", []))[1],
                                                    "file": ctx.store.rel(path), "collected_via": "user browser"})
                ctx.count("imported_versions")
