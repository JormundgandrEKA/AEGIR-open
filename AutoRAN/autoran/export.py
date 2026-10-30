"""`autoran export`: the silver set as a file, with a licence manifest and the ClinicalTrials.gov attribution.

Refuses any record whose source grade is below the floor (config: grade_floor, default B-). Exports labels and categories only:
no free text from the registry beyond the stop reason that justifies a label, and nothing that is a contact detail.
"""
import json

from aegir_ran import pmc

from .core import Paths, iso_now, iter_jsonl, utc_stamp, write_jsonl
from .scorers import iter_joined


def export(ctx, cfg, floor=None):
    paths = Paths(ctx.root).ensure()
    floor = floor or cfg["grade_floor"]
    grades = ctx.grades
    srcs = cfg["sources"]["sources"]
    refused = []

    def ok(source):
        g = srcs[source]["grade"]
        good = pmc.grade_at_least(grades, g, floor)
        if not good and source not in refused:
            refused.append(source)
        return good

    stamp = utc_stamp()
    out = paths.derived / f"silver_{stamp}.jsonl"
    counts = {}

    def rows():
        for rec, lab, cat in iter_joined(paths):
            if not ok(rec["source"]):
                continue
            counts[lab["class"]] = counts.get(lab["class"], 0) + 1
            yield {"nct_id": rec["nct_id"], "class": lab["class"], "stop_classes": lab["stop_classes"], "label_source": lab["label_source"],
                   "confidence": lab["confidence"], "why_stopped": rec["why_stopped"] if rec["status"] == "TERMINATED" else "",
                   "status": rec["status"], "phase": cat["phase"], "areas": cat["areas"], "sponsor_class": cat["sponsor_class"], "year": cat["year"],
                   "region": cat["region"], "input_state": cat["input_state"], "registration": cat["registration"], "split": cat["split"],
                   "source": rec["source"], "grade": rec["grade"], "licence": srcs[rec["source"]]["licence"]}
    n = write_jsonl(out, rows())
    mfile = paths.derived / f"silver_{stamp}.manifest.json"
    meta = None
    pages = ctx.store.records("autoran_pages.jsonl")
    if pages:
        side = ctx.root / pages[0]["file"]
        try:
            meta = json.loads(side.with_name(side.name + ".meta.json").read_text(encoding="utf-8")).get("ctgov_data_timestamp")
        except (OSError, ValueError):
            meta = None
    lf = paths.latest("labeller_*.json")
    manifest = {"schema": "autoran-silver/0.1", "created": iso_now(), "records": n, "classes": counts, "grade_floor": floor, "refused_sources": refused,
                "sources": {k: v for k, v in srcs.items()},
                "attribution": ("Registry data: ClinicalTrials.gov (U.S. National Library of Medicine), https://clinicaltrials.gov. Data processed by "
                                f"ClinicalTrials.gov {meta or 'on the date in the page sidecars'}; this is a dated snapshot, not current data. Modifications: limited "
                                "field set, contact fields never requested, text normalised, labels and categories added by AutoRAN. Some registry text may be "
                                "subject to third-party copyright. Stop-reason training and test examples: Open Targets, clinical_trial_reason_to_stop, "
                                "Apache License 2.0 (the curated examples themselves are not in this file)."),
                "labeller": lf.name if lf else None, "file": out.name,
                "caveats": ["Labels are machine-made (the silver set) and weakly labelled; use the audit precision and the held-out curated test to qualify claims.",
                            "The planned enrolment of completed trials is lost once the actual figure is posted."]}
    mfile.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ctx.store.append("autoran_stages.jsonl", {"stage": "export", "file": ctx.store.rel(out), "n": n, "ts": iso_now()})
    ctx.count("exported", n)
    return {"file": str(out), "manifest": str(mfile), "records": n, "refused_sources": refused}
