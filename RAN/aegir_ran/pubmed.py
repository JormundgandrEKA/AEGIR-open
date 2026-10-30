"""PubMed via E-utilities: fixed searches and article fetch."""
import json
import math
import xml.etree.ElementTree as ET

from aegir_core.core import NCT_RE, iso_now, utc_stamp

EU = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TERMS = "https://www.ncbi.nlm.nih.gov/home/about/policies/"
ESEARCH_CAP = 9999   # ESearch cannot page past 10,000 records


def _text(el):
    return "".join(el.itertext()).strip() if el is not None else ""


def parse_article(el):
    """Catalogue fields from a <PubmedArticle> element."""
    mc = el.find("MedlineCitation")
    art = mc.find("Article")
    ids = {a.get("IdType"): (a.text or "").strip() for a in el.findall("PubmedData/ArticleIdList/ArticleId")}
    ncts = set()
    for db in art.findall("DataBankList/DataBank"):
        if "clinicaltrials" in (db.findtext("DataBankName") or "").lower():
            ncts.update(NCT_RE.findall(" ".join(a.text or "" for a in db.findall("AccessionNumberList/AccessionNumber"))))
    abstract = " ".join(_text(a) for a in art.findall("Abstract/AbstractText"))
    return {
        "pmid": (mc.findtext("PMID") or "").strip(),
        "pmcid": ids.get("pmc"),
        "doi": ids.get("doi") or next((_text(e) for e in art.findall("ELocationID") if e.get("EIdType") == "doi"), None),
        "journal": art.findtext("Journal/ISOAbbreviation") or art.findtext("Journal/Title"),
        "journal_title": art.findtext("Journal/Title"),
        "year": art.findtext("Journal/JournalIssue/PubDate/Year"),
        "pub_types": [_text(p) for p in art.findall("PublicationTypeList/PublicationType")],
        "title": _text(art.find("ArticleTitle")),
        "secondary_ids": sorted(ncts),
        "text_ncts": sorted(set(NCT_RE.findall(abstract)) - ncts),
    }


def search(ctx, query_id=None, term=None):
    if query_id:
        q = ctx.query(query_id, "pubmed")
        term = q["term"]
    else:
        if not term:
            raise ValueError("give --query-id, or --term for an exploratory search")
        ctx.store.scratch = True
        ctx.store.base = ctx.store.data / "scratch"
        query_id = "adhoc"
    if not ctx.refresh and query_id != "adhoc" and query_id in ctx.store.latest("searches.jsonl", "query_id"):
        ctx.count("search_cached")
        ctx.notes["hint"] = "search already catalogued; use --refresh for a new dated snapshot"
        return
    pmids, first, start, count = [], None, 0, None
    while count is None or (start < count and start < ESEARCH_CAP):
        r = ctx.client.get(f"{EU}/esearch.fcgi", {"db": "pubmed", "term": term, "retmax": 10000 if not ctx.max_items else min(ctx.max_items, 10000),
                                                 "retstart": start, "retmode": "json"})
        if r is None:
            return
        if not r.ok:
            ctx.error(f"pubmed search {query_id}: HTTP {r.status} {r.error or ''}")
            return
        ctx.client.log(r)
        first = first or r
        res = r.json().get("esearchresult", {})
        if "ERROR" in res:
            ctx.error(f"pubmed search {query_id}: {res['ERROR']}")
            return
        count = int(res.get("count", 0))
        ids = res.get("idlist", [])
        pmids.extend(ids)
        start += len(ids)
        if not ids or ctx.max_items:
            break
    if count and count > ESEARCH_CAP:
        ctx.notes["truncated"] = f"{count} matches; ESearch returns at most {ESEARCH_CAP + 1}"
    out = {"query_id": query_id, "term": term, "count": count, "pmids": pmids}
    body = json.dumps(out).encode("utf-8")
    path = ctx.store.save_raw(["pubmed", "search", query_id], utc_stamp() + ".json", body,
                              first.meta(source="PubMed", terms_url=TERMS, query_id=query_id,
                                         grade=ctx.cfg.get("source_grades", {}).get("pubmed_metadata")))
    ctx.store.append("searches.jsonl", {"query_id": query_id, "source": "pubmed", "params": {"term": term},
                                        "n_results": len(pmids), "total": count, "file": ctx.store.rel(path),
                                        "ts": iso_now(), "scratch": ctx.store.scratch})
    ctx.count("pmids_found", len(pmids))


def fetch(ctx, pmids):
    """EFetch in batches; one stored XML file per article."""
    done = ctx.store.latest("articles.jsonl", "pmid")
    todo = [p for p in ctx.limit(dict.fromkeys(str(p) for p in pmids)) if ctx.refresh or p not in done]
    ctx.count("article_cached", len(list(pmids)) - len(todo) if not ctx.max_items else 0)
    n = ctx.cfg.get("pubmed_batch", 200)
    ctx.client.check_window(math.ceil(len(todo) / n))
    for i in range(0, len(todo), n):
        batch = todo[i:i + n]
        r = ctx.client.get(f"{EU}/efetch.fcgi", {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"})
        if r is None:
            continue
        if not r.ok:
            ctx.error(f"efetch {batch[0]}..: HTTP {r.status} {r.error or ''}")
            continue
        ctx.client.log(r)
        try:
            root = ET.fromstring(r.body)
        except ET.ParseError as e:
            ctx.error(f"efetch parse error: {e}")
            continue
        for el in root.findall("PubmedArticle"):
            rec = parse_article(el)
            body = b'<?xml version="1.0" encoding="UTF-8"?>\n<PubmedArticleSet>' + ET.tostring(el, encoding="utf-8") + b"</PubmedArticleSet>\n"
            path = ctx.store.save_raw(["pubmed", "article", rec["pmid"]], utc_stamp() + ".xml", body,
                                      r.meta(source="PubMed", terms_url=TERMS, batch_request=True,
                                             grade=ctx.cfg.get("source_grades", {}).get("pubmed_metadata"),
                                             note="abstract text may be copyrighted by the publisher"))
            ctx.store.append("articles.jsonl", {**rec, "file": ctx.store.rel(path), "ts": iso_now()})
            ctx.count("articles_fetched")


def stored_article(ctx, pmid):
    """Parsed record of the newest stored article XML, or None."""
    f = ctx.store.latest_file(["pubmed", "article", str(pmid)], ".xml")
    if f is None:
        return None
    el = ET.fromstring(f.read_bytes()).find("PubmedArticle")
    return parse_article(el) if el is not None else None
