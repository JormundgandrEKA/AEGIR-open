"""PMC: per-article licence (from efetch db=pmc), grading, full text behind the grade gate."""
import csv
import io
import json
import re
import xml.etree.ElementTree as ET

from aegir_core.core import iso_now, utc_stamp
from aegir_core.grades import grade_at_least, grade_for, rank  # noqa: F401  (re-exported: RAN and AutoRAN call pmc.grade_at_least)

EU = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TERMS = "https://pmc.ncbi.nlm.nih.gov/about/copyright/"
CC_RE = re.compile(r"creativecommons\.org/(licenses|publicdomain)/([a-z\-]+)", re.I)
TEXT_PATTERNS = [  # most specific first
    (r"attribution[\s-]*non[\s-]*commercial[\s-]*no[\s-]*deriv", "cc-by-nc-nd"),
    (r"attribution[\s-]*non[\s-]*commercial[\s-]*share", "cc-by-nc-sa"),
    (r"attribution[\s-]*non[\s-]*commercial", "cc-by-nc"),
    (r"attribution[\s-]*no[\s-]*deriv", "cc-by-nd"),
    (r"attribution[\s-]*share", "cc-by-sa"),
    (r"creative commons attribution", "cc-by"),
    (r"public domain|cc0", "cc0"),
]


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def classify(url, text, statement=""):
    """Licence key from a licence URL / text. None when nothing licence-like is present."""
    m = CC_RE.search(url or "")
    if m:
        kind, code = m.group(1).lower(), m.group(2).lower()
        if kind == "publicdomain":
            return "cc0" if code.startswith("zero") else "public-domain"
        return {"by": "cc-by", "by-sa": "cc-by-sa", "by-nd": "cc-by-nd", "by-nc": "cc-by-nc",
                "by-nc-sa": "cc-by-nc-sa", "by-nc-nd": "cc-by-nc-nd"}.get(code, "custom")
    blob = (text or "").lower()
    for pat, key in TEXT_PATTERNS:
        if re.search(pat, blob):
            return key
    if blob.strip():
        return "custom"
    if re.search(r"all rights reserved", (statement or "").lower()):
        return "all-rights-reserved"
    return None


def parse_licence(xml_bytes):
    """Licence facts from a PMC efetch record. Reads <license>, ali:license_ref, copyright statement."""
    root = ET.fromstring(xml_bytes)
    urls, texts, statement, pmcid, pmid, present = [], [], "", None, None, False
    journal = journal_title = None
    for el in root.iter():
        t = _local(el.tag)
        if t == "journal-id" and el.get("journal-id-type") == "iso-abbrev":
            journal = journal or (el.text or "").strip()
        elif t == "journal-title" and journal_title is None:
            journal_title = "".join(el.itertext()).strip()
        elif t == "license":
            present = True
            for k, v in el.attrib.items():
                if _local(k) == "href":
                    urls.append(v)
            for a in el.iter():
                if _local(a.tag) == "ext-link":
                    urls.extend(v for k, v in a.attrib.items() if _local(k) == "href")
            texts.append("".join(el.itertext()).strip())
        elif t == "license_ref":
            present = True
            urls.append((el.text or "").strip())
        elif t == "copyright-statement":
            statement = "".join(el.itertext()).strip()
        elif t == "article-id":
            if el.get("pub-id-type") == "pmcid" or el.get("pub-id-type") == "pmc":
                pmcid = pmcid or (el.text or "").strip()
            elif el.get("pub-id-type") == "pmid":
                pmid = el.text
    cc_urls = [u for u in urls if CC_RE.search(u)]
    url = (cc_urls or urls or [None])[0]
    text = " ".join(texts)
    key = classify(url, text, statement)
    if key is None and present:
        key = "custom"
    return {"licence": key, "licence_url": url, "licence_text": text[:500], "copyright_statement": statement[:300],
            "pmcid": pmcid, "pmid": pmid, "journal": journal, "journal_title": journal_title}


# -- grading ------------------------------------------------------------

def do_not_redistribute(ctx, g):
    return not grade_at_least(ctx.grades, g, ctx.cfg.get("min_redistribute_grade", "B-"))


def pmc_number(pmcid):
    return re.sub(r"\D", "", str(pmcid))


def _article_by_pmcid(ctx):
    return {a["pmcid"]: a for a in ctx.store.latest("articles.jsonl", "pmid").values() if a.get("pmcid")}


def licence(ctx, pmcids):
    arts = _article_by_pmcid(ctx)
    done = ctx.store.latest("licences.jsonl", "pmcid")
    ids = [("PMC" + pmc_number(p)) for p in ctx.limit(pmcids)]
    todo = [p for p in ids if ctx.refresh or p not in done]
    ctx.count("licence_cached", len(ids) - len(todo))
    ctx.client.check_window(len(todo))
    for p in todo:
        r = ctx.client.get(f"{EU}/efetch.fcgi", {"db": "pmc", "id": pmc_number(p), "retmode": "xml"})
        if r is None:
            continue
        if not r.ok:
            ctx.error(f"{p}: HTTP {r.status} {r.error or ''}")
            continue
        try:
            lic = parse_licence(r.body)
        except ET.ParseError as e:
            ctx.error(f"{p}: XML parse error {e}")
            continue
        art = arts.get(p, {})
        lic["pmid"] = lic.get("pmid") or art.get("pmid")
        # the PMC record names its own journal; PubMed metadata is only a fallback
        journal = lic.get("journal") or art.get("journal")
        journal_title = lic.get("journal_title") or art.get("journal_title")
        g = grade_for(ctx.grades, lic["licence"], journal, journal_title)
        rec = {"pmcid": p, "pmid": lic["pmid"], "licence": lic["licence"], "licence_url": lic["licence_url"],
               "grade": g, "journal": journal, "journal_title": journal_title,
               "do_not_redistribute": do_not_redistribute(ctx, g), "source": "efetch db=pmc",
               "licence_text": lic["licence_text"], "copyright_statement": lic["copyright_statement"]}
        path = ctx.store.save_raw(["pmc", "licence", p], utc_stamp() + ".json", json.dumps(rec, indent=2).encode(),
                                  r.meta(source="PMC", terms_url=TERMS, grade=g,
                                         note="licence extracted from efetch db=pmc; article body not stored",
                                         full_response_sha256=__import__("hashlib").sha256(r.body).hexdigest()))
        ctx.client.log(r, ctx.store.rel(path))
        ctx.store.append("licences.jsonl", {**rec, "file": ctx.store.rel(path), "ts": iso_now()})
        ctx.count("licences_checked")
        ctx.count(f"grade_{g}")


def fulltext(ctx, pmcids):
    min_g = ctx.cfg.get("min_fulltext_grade", "D-")
    lic = ctx.store.latest("licences.jsonl", "pmcid")
    for p in ctx.limit("PMC" + pmc_number(x) for x in pmcids):
        rec = lic.get(p)
        if rec is None:
            ctx.error(f"{p}: no licence check on file; run `pmc licence {p}` first")
            continue
        if not grade_at_least(ctx.grades, rec["grade"], min_g):
            ctx.count("fulltext_refused_grade")
            continue
        if not ctx.refresh and ctx.store.latest_file(["pmc", "fulltext", p], ".xml"):
            ctx.count("fulltext_cached")
            continue
        r = ctx.client.get(f"{EU}/efetch.fcgi", {"db": "pmc", "id": pmc_number(p), "retmode": "xml"})
        if r is None:
            continue
        if not r.ok:
            ctx.error(f"{p}: HTTP {r.status} {r.error or ''}")
            continue
        path = ctx.store.save_raw(["pmc", "fulltext", p], utc_stamp() + ".xml", r.body,
                                  r.meta(source="PMC", terms_url=TERMS, grade=rec["grade"],
                                         licence=rec["licence"], licence_url=rec["licence_url"],
                                         do_not_redistribute=rec["do_not_redistribute"]))
        ctx.client.log(r, ctx.store.rel(path))
        ctx.count("fulltext_fetched")


def regrade(ctx):
    """Recompute grades from config/grades.json into a new derived file."""
    rows = []
    epmc = ctx.store.latest("epmc_licences.jsonl", "pmid")
    arts = ctx.store.latest("articles.jsonl", "pmid")
    for rec in ctx.store.latest("licences.jsonl", "pmcid").values():
        alt = arts.get(rec.get("pmid")) or epmc.get(rec.get("pmid")) or {}
        journal = rec.get("journal") or alt.get("journal")
        title = rec.get("journal_title") or alt.get("journal_title")
        g = grade_for(ctx.grades, rec.get("licence"), journal, title)
        rows.append({"pmcid": rec["pmcid"], "pmid": rec.get("pmid"), "licence": rec.get("licence"),
                     "journal": journal, "old_grade": rec.get("grade"), "grade": g,
                     "do_not_redistribute": int(do_not_redistribute(ctx, g))})
    buf = io.StringIO(newline="")
    cols = ["pmcid", "pmid", "licence", "journal", "old_grade", "grade", "do_not_redistribute"]
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    path = ctx.store.write_new(ctx.store.derived_dir() / f"grades_{utc_stamp()}.csv", buf.getvalue().encode())
    ctx.count("licences_graded", len(rows))
    ctx.count("grade_changed", sum(1 for r in rows if r["old_grade"] != r["grade"]))
    ctx.notes["derived_file"] = ctx.store.rel(path)
