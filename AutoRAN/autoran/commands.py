"""Command dispatch. Heavier stages are imported only when used."""
import time

from .core import Paths


def run(cmd, ctx, cfg, args):
    paths = Paths(ctx.root).ensure()
    t0 = time.time()
    out = _dispatch(cmd, ctx, cfg, args, paths)
    if isinstance(out, dict):
        out.setdefault("seconds", round(time.time() - t0, 1))
    return out


def _dispatch(cmd, ctx, cfg, args, paths):
    if cmd == "fetch":
        from . import fetch
        return fetch.fetch(ctx, cfg, kind="delta" if args.delta else "full", resume=not args.new, max_pages=args.max_pages)
    if cmd == "labeller-data":
        from . import opentargets
        f = opentargets.fetch(ctx, cfg)
        return {"file": str(f) if f else None}
    if cmd == "normalise":
        from . import normalise
        return normalise.normalise(ctx, cfg, partial=getattr(args, "partial", False))
    if cmd == "label":
        from . import labelstage
        return labelstage.label(ctx, cfg)
    if cmd == "categorize":
        from . import categorize
        return categorize.categorize(ctx, cfg)
    if cmd == "score":
        from . import scorers
        res = scorers.score_all(ctx, cfg, names=[n for n in (args.scorer or []) if not n.startswith("gpu_")] or None)
        if _use_gpu(args.device):
            from . import gpu
            res["gpu"] = gpu.score_gpu(ctx, cfg, args.device, names=[n for n in (args.scorer or []) if n.startswith("gpu_")] or None)
        return res
    if cmd == "metrics":
        from . import metrics
        return metrics.compute(ctx, cfg, device=args.device if _use_gpu(args.device) else "cpu")
    if cmd == "gpu-info":
        from . import gpu
        return gpu.info()
    if cmd == "frame":
        from . import gpu
        return gpu.frame(ctx, cfg)
    if cmd == "audit-sample":
        from . import audit
        return audit.draw(ctx, cfg, n=args.n, klass=args.klass, seed=args.seed)
    if cmd == "export":
        from . import export
        return export.export(ctx, cfg, floor=args.grade_floor)
    if cmd == "serve":
        from . import server
        return server.serve(ctx, cfg, port=args.port, labeller=args.labeller, open_browser=not args.no_browser)
    if cmd == "run":
        return run_all(ctx, cfg, args, paths)
    if cmd == "status":
        return status(ctx, cfg, paths)
    raise ValueError(f"unknown command: {cmd}")


def _use_gpu(pref):
    """True when the GPU path should run. `auto` quietly falls back to the standard-library path when PyTorch or CUDA is missing."""
    if pref == "cpu":
        return False
    try:
        import torch
        return bool(torch.cuda.is_available()) or pref == "cuda"
    except ImportError:
        if pref == "cuda":
            raise SystemExit("--device cuda needs PyTorch (see the README: setup.ps1 -Gpu, or Settings > GPU pack folder)")
        return False


def run_all(ctx, cfg, args, paths):
    """Idempotent daily run: delta fetch (or full if none yet), then every later stage."""
    from . import fetch, normalise, labelstage, categorize, scorers, metrics
    done = [r for r in ctx.store.records("autoran_runs.jsonl") if r["status"] == "done"]
    kind = "delta" if done else "full"
    res = {"fetch": fetch.fetch(ctx, cfg, kind=kind)}
    if ctx.dry_run:
        return res
    if not paths.latest("ot_reasons_*.jsonl"):
        from . import opentargets
        f = opentargets.fetch(ctx, cfg)
        res["labeller_data"] = str(f) if f else None
    res["normalise"] = normalise.normalise(ctx, cfg)
    res["label"] = labelstage.label(ctx, cfg)
    res["categorize"] = categorize.categorize(ctx, cfg)
    res["score"] = scorers.score_all(ctx, cfg)
    if _use_gpu(args.device):
        from . import gpu
        res["score"]["gpu"] = gpu.score_gpu(ctx, cfg, args.device)
    res["metrics"] = metrics.compute(ctx, cfg, device=args.device if _use_gpu(args.device) else "cpu")
    return res


def status(ctx, cfg, paths):
    out = {}
    for pat in ("trials_*.jsonl", "labels_*.jsonl", "cats_*.jsonl", "labeller_*.json", "ot_reasons_*.jsonl", "metrics_*.json"):
        f = paths.latest(pat)
        out[pat] = f.name if f else None
    runs = ctx.store.latest("autoran_runs.jsonl", "run")
    out["runs"] = [{"run": r["run"], "kind": r["kind"], "status": r["status"]} for r in sorted(runs.values(), key=lambda x: x["run"])]
    size = sum(p.stat().st_size for p in (ctx.root / "data").rglob("*") if p.is_file()) if (ctx.root / "data").is_dir() else 0
    out["data_mb"] = round(size / 1e6, 1)
    return out
