"""Open Targets curated stop reasons (Hugging Face dataset, Apache 2.0, graded B-): download, store, split."""
import json
import re
import html

from . import __version__
from .core import Paths, install_gzip, iso_now, iter_jsonl, stable_hash, utc_stamp, write_jsonl

HOST = "https://datasets-server.huggingface.co"
LABEL_META = ("text", "label_descriptions")


def fetch(ctx, cfg, resume=True):
    """Download every row (100 per request) as raw page files with sidecars, then write one normalised jsonl."""
    install_gzip()
    oc = cfg["opentargets"]
    ds, size = oc["dataset"], oc["page"]
    src = cfg["sources"]["sources"]["opentargets_reasons"]
    done = ctx.store.latest("autoran_ot.jsonl", "run")
    if done and not ctx.refresh and any(r.get("status") == "done" for r in done.values()):
        ctx.count("cached", 1)
        ctx.notes["hint"] = "Open Targets data already fetched; use --refresh for a new dated copy"
        return None
    run, offset, total, n = utc_stamp(), 0, None, 0
    rows, features = [], None
    # resume: pick up the newest unfinished download (raw row pages already on disk)
    started = sorted(d for d in (ctx.root / "data" / "raw" / "opentargets").glob("*") if d.is_dir()) if (ctx.root / "data" / "raw" / "opentargets").is_dir() else []
    finished = {r["run"] for r in ctx.store.records("autoran_ot.jsonl") if r.get("status") == "done"}
    pending = [d for d in started if d.name not in finished]
    if pending and not ctx.refresh:
        run = pending[-1].name
        for f in sorted(x for x in pending[-1].glob("rows_*.json") if not x.name.endswith(".meta.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            features = features or [x["name"] for x in d.get("features", [])]
            total = d.get("num_rows_total", total)
            got = [x["row"] for x in d.get("rows", [])]
            rows.extend(got)
            offset += len(got)
        ctx.notes["resumed_from_offset"] = offset
    while total is None or offset < total:
        r = ctx.client.get(f"{HOST}/rows", {"dataset": ds, "config": "default", "split": "train", "offset": offset, "length": size})
        if r is None:
            return None
        if not r.ok:
            ctx.error(f"Open Targets rows at offset {offset}: HTTP {r.status} {r.error or ''}")
            return None
        d = r.json()
        total = d.get("num_rows_total", total)
        features = features or [f["name"] for f in d.get("features", [])]
        got = [x["row"] for x in d.get("rows", [])]
        if not got:
            break
        path = ctx.store.save_raw(["opentargets", run], f"rows_{offset:05d}.json", r.body,
                                  r.meta(source="Open Targets (Hugging Face dataset)", terms_url=src["terms"], grade=src["grade"],
                                         licence=src["licence"], dataset=ds, offset=offset, run=run,
                                         attribution="Open Targets, clinical_trial_reason_to_stop, Apache License 2.0"))
        ctx.client.log(r, ctx.store.rel(path))
        rows.extend(got)
        offset += len(got)
        n += 1
        ctx.count("requests_ok", 1)
    paths = Paths(ctx.root).ensure()
    classes = [f for f in (features or []) if f not in LABEL_META]
    sp = oc["split"]
    out = []
    for i, row in enumerate(rows):
        labs = [c for c in classes if row.get(c)]
        text = row.get("text") or ""
        h = stable_hash(normalise_reason(text), sp["seed"])
        part = "test" if h < sp["test"] else ("dev" if h < sp["test"] + sp["dev"] else "train")
        out.append({"i": i, "text": text, "labels": labs, "split": part})
    f = paths.derived / f"ot_reasons_{run}.jsonl"
    write_jsonl(f, out)
    ctx.store.append("autoran_ot.jsonl", {"run": run, "status": "done", "rows": len(out), "classes": classes, "file": ctx.store.rel(f),
                                         "licence": src["licence"], "grade": src["grade"], "ts": iso_now(), "version": __version__})
    ctx.count("rows", len(out))
    ctx.notes["classes"] = len(classes)
    ctx.notes["split"] = {k: sum(1 for o in out if o["split"] == k) for k in ("train", "dev", "test")}
    return f


def normalise_reason(text):
    """Lower case, entities decoded, non-breaking spaces and runs of space removed."""
    t = html.unescape(text or "")
    t = t.replace("\xca", " ").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t.strip(" .;:-")


def load(paths):
    """Rows of the newest Open Targets file, or []. Each: {i, text, labels, split}."""
    f = paths.latest("ot_reasons_*.jsonl")
    return list(iter_jsonl(f)) if f else []
