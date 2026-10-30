"""Europe PMC licence lookup: one PMID per request (OR queries return 503), cache first."""
import json

from .core import iso_now, read_jsonl, utc_stamp
from .pmc import classify, grade_for

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
TERMS = "https://europepmc.org/Copyright"


def normalise(lic):
    """Europe PMC licence strings ('cc by', 'cc by-nc-nd', 'cc0') to our licence keys."""
    t = (lic or "").strip().lower().replace(" ", "-")
    if not t:
        return None
    if t.startswith("cc0"):
        return "cc0"
    if t.startswith("cc-by"):
        key = "cc-by" + t[5:]
        return key if key in ("cc-by", "cc-by-sa", "cc-by-nd", "cc-by-nc", "cc-by-nc-sa", "cc-by-nc-nd") else "custom"
    return classify(None, lic) or "custom"


def pmids_from_query(ctx, query_id):
    ent = ctx.store.latest("searches.jsonl", "query_id").get(query_id)
    if not ent or ent.get("source") != "pubmed":
        raise ValueError(f"no stored pubmed search {query_id}")
    return json.loads((ctx.root / ent["file"]).read_text(encoding="utf-8")).get("pmids", [])


def licence(ctx, pmids, from_query=None):
    pmids = [str(p) for p in (pmids or [])]
    if from_query:
        pmids += pmids_from_query(ctx, from_query)
    done = ctx.store.latest("epmc_licences.jsonl", "pmid")
    todo = [p for p in ctx.limit(dict.fromkeys(pmids)) if ctx.refresh or p not in done]
    ctx.count("epmc_cached", len(set(pmids)) - len(todo) if not ctx.max_items else 0)
    ctx.notes["estimated_requests"] = len(todo)
    for p in todo:
        r = ctx.client.get(API, {"query": f"EXT_ID:{p} AND SRC:MED", "resultType": "core", "format": "json",
                                 "pageSize": 1})
        if r is None:
            continue
        if not r.ok:
            ctx.error(f"PMID {p}: HTTP {r.status} {r.error or ''}")
            continue
        results = r.json().get("resultList", {}).get("result", [])
        rec = results[0] if results else {}
        ji = rec.get("journalInfo", {}).get("journal", {})
        key = normalise(rec.get("license"))
        journal, title = ji.get("medlineAbbreviation") or ji.get("isoabbreviation"), ji.get("title")
        grade = grade_for(ctx.grades, key, journal, title) if rec else "ungraded"
        path = ctx.store.save_raw(["epmc", "licence", p], utc_stamp() + ".json", r.body,
                                  r.meta(source="Europe PMC", terms_url=TERMS,
                                         grade=ctx.cfg.get("source_grades", {}).get("epmc_licence")))
        ctx.client.log(r, ctx.store.rel(path))
        ctx.store.append("epmc_licences.jsonl", {
            "pmid": p, "pmcid": rec.get("pmcid"), "found": bool(rec), "license_epmc": rec.get("license"),
            "licence": key, "journal": journal, "journal_title": title, "year": rec.get("pubYear"),
            "is_open_access": rec.get("isOpenAccess"), "indicative_grade": grade,
            "note": "indicative only; the PMC check decides the grade when the two disagree",
            "file": ctx.store.rel(path), "ts": iso_now()})
        ctx.count("epmc_checked")
        if not rec:
            ctx.count("epmc_not_found")
