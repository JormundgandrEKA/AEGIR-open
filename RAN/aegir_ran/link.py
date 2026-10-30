"""Links between registry records and publications."""
from . import ctgov, pubmed
from .core import NCT_RE, iso_now


def _have(ctx):
    return {(r["nct_id"], r["pmid"], r["link_type"]) for r in ctx.store.records("links.jsonl")}


def from_registry(ctx, ncts):
    have = _have(ctx)
    for nct in ctx.limit(n.upper() for n in ncts):
        rec, _ = ctgov.find_study_record(ctx, nct)
        if rec is None:
            ctgov.study(ctx, [nct])
            ctx.cache.pop("search_index", None)
            rec, _ = ctgov.find_study_record(ctx, nct)
        if rec is None:
            ctx.count("link_no_record")
            continue
        refs = rec.get("protocolSection", {}).get("referencesModule", {}).get("references", []) or []
        for ref in refs:
            pmid = ref.get("pmid")
            if not pmid or (nct, str(pmid), "registry_ref") in have:
                continue
            ctx.store.append("links.jsonl", {"nct_id": nct, "pmid": str(pmid), "link_type": "registry_ref",
                                             "evidence": {"reference_type": ref.get("type"),
                                                          "citation": (ref.get("citation") or "")[:300]},
                                             "ts": iso_now()})
            have.add((nct, str(pmid), "registry_ref"))
            ctx.count("links_added")


def from_pubmed(ctx, pmids):
    pmids = [str(p) for p in ctx.limit(pmids)]
    pubmed.fetch(ctx, pmids)           # no-op for articles already catalogued
    have = _have(ctx)
    for pmid in pmids:
        art = pubmed.stored_article(ctx, pmid)
        if art is None:
            ctx.count("link_no_article")
            continue
        for kind, ncts in (("pubmed_si", art["secondary_ids"]), ("text_mention", art["text_ncts"])):
            for nct in ncts:
                if (nct, pmid, kind) in have:
                    continue
                ctx.store.append("links.jsonl", {"nct_id": nct, "pmid": pmid, "link_type": kind,
                                                 "evidence": {"title": art["title"][:200]}, "ts": iso_now()})
                have.add((nct, pmid, kind))
                ctx.count("links_added")
