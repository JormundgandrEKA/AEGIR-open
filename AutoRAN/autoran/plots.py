"""Visualisations as plug-ins. Add a plot by dropping one Python file into the `plugins/` folder next to the app.

    # plugins/my_plot.py
    from autoran.plots import plot

    @plot("Failure rate by sponsor", "Share of completed or failed trials that failed to recruit, by sponsor class")
    def sponsor(ctx):
        import matplotlib.pyplot as plt
        df = ctx.task()                                  # completed + recruitment-failure trials, with a 0/1 column `fail`
        fig, ax = plt.subplots(figsize=(7, 4))
        df.groupby("sponsor_class")["fail"].mean().sort_values().plot.barh(ax=ax)
        return fig                                       # any matplotlib Figure

`ctx` gives you: ctx.frame() (the pandas DataFrame of every trial, label, category and score), ctx.task(), ctx.metrics (the metrics file),
ctx.device (a torch device, or None when PyTorch is absent), ctx.torch and ctx.np. Plugins run in the app's own process, so they can use
the GPU too. A plugin that raises an error shows the error in the app; nothing else breaks.
"""
import base64
import importlib.util
import io
import json
import time
import traceback
from pathlib import Path

import matplotlib
import matplotlib.ticker  # noqa: F401

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import core  # noqa: E402

REGISTRY = {}


def plot(name, description="", needs_frame=True):
    def deco(fn):
        REGISTRY[name] = {"name": name, "description": description, "fn": fn, "source": getattr(fn, "__module__", ""), "needs_frame": needs_frame}
        return fn
    return deco


class PlotContext:
    def __init__(self, root, metrics, pref="auto"):
        self.root, self.metrics, self.pref = Path(root), metrics or {}, pref
        self._frame = None
        try:
            import numpy
            import torch
            self.np, self.torch = numpy, torch
            self.device = torch.device("cuda" if (pref != "cpu" and torch.cuda.is_available()) else "cpu")
        except ImportError:
            self.np, self.torch, self.device = None, None, None

    def frame(self):
        if self._frame is None:
            import pandas as pd
            paths = core.Paths(self.root)
            f = paths.latest("frame_*.parquet")
            if f is None:
                raise FileNotFoundError("no Parquet frame yet: run the 'Parquet frame' step on the Run page")
            self._frame = pd.read_parquet(f)
        return self._frame

    def task(self):
        df = self.frame()
        t = df[df["class"].isin(["positive_recruitment", "negative_completed"])].copy()
        t["fail"] = (t["class"] == "positive_recruitment").astype(int)
        return t

    def scorers(self):
        return sorted(c[len("score_"):] for c in self.frame().columns if c.startswith("score_"))


def load_plugins(root):
    """Import every .py in <root>/plugins. Returns a list of load errors (shown in the app)."""
    errors = []
    from . import core
    dirs = [Path(root) / "plugins"] + ([core.CODE_ROOT / "plugins"] if Path(core.CODE_ROOT).resolve() != Path(root).resolve() else [])
    for name in [n for n, v in REGISTRY.items() if v["source"].startswith("plugin_")]:
        REGISTRY.pop(name, None)
    for d in dirs:
        if d.is_dir():
            for f in sorted(d.glob("*.py")):
                if f.name.startswith("_"):
                    continue
                try:
                    spec = importlib.util.spec_from_file_location("plugin_" + f.stem, f)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                except Exception as e:
                    errors.append(f"{f.name}: {type(e).__name__}: {e}")
    return errors


def listing(root):
    errors = load_plugins(root)
    return {"plots": [{"name": v["name"], "description": v["description"], "builtin": not v["source"].startswith("plugin_"), "source": v["source"]}
                      for v in REGISTRY.values()], "plugin_errors": errors, "plugins_dir": str(Path(root) / "plugins")}


def render(root, metrics, name, pref="auto"):
    if name not in REGISTRY:
        raise ValueError(f"no plot called {name!r}")
    ctx = PlotContext(root, metrics, pref)
    t0 = time.time()
    try:
        fig = REGISTRY[name]["fn"](ctx)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
        png = buf.getvalue()
        plt.close(fig)
    except Exception as e:
        plt.close("all")
        return {"name": name, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1200:]}
    out = core.Paths(root).derived / "plots"
    out.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in name).strip("_")[:60]
    path = out / f"{safe}_{time.strftime('%Y%m%dT%H%M%S')}.png"
    path.write_bytes(png)
    return {"name": name, "png": base64.b64encode(png).decode("ascii"), "seconds": round(time.time() - t0, 2),
            "device": str(ctx.device) if ctx.device else "cpu (no PyTorch)", "saved": str(path)}


# -- built-in plots ----------------------------------------------------------------------------------

@plot("Scorers: AUROC with intervals", "Test AUROC for every scorer, all trials versus the clean subset, with 95% bootstrap intervals", needs_frame=False)
def _auroc(ctx):
    m = ctx.metrics
    rows = []
    for name, e in m["scorers"].items():
        for which in ("all", "clean"):
            b = e["test"][which]
            if b.get("auroc") is not None and b.get("ci", {}).get("auroc"):
                rows.append((name, which, b["auroc"], *b["ci"]["auroc"]))
    import pandas as pd
    r = pd.DataFrame(rows, columns=["scorer", "set", "auroc", "lo", "hi"])
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for i, (which, col) in enumerate((("all", "#0040ff"), ("clean", "#9a6700"))):
        d = r[r["set"] == which].sort_values("scorer")
        pos = [k + (i - 0.5) * 0.35 for k in range(len(d))]
        ax.barh(pos, d["auroc"], height=0.32, color=col, label=which, xerr=[d["auroc"] - d["lo"], d["hi"] - d["auroc"]], ecolor="#111")
        ax.set_yticks(range(len(d)))
        ax.set_yticklabels(d["scorer"])
    ax.axvline(0.5, color="#999", ls="--")
    ax.set_xlim(0.4, 0.85)
    ax.set_xlabel("test AUROC (95% bootstrap interval)")
    ax.legend(title="trials")
    return fig


@plot("Recruitment failure rate by therapeutic area", "Share of completed or failed trials that failed to recruit, areas with at least 500 trials")
def _area(ctx):
    t = ctx.task()
    g = t.groupby("area")["fail"].agg(["mean", "count"]).query("count >= 500").sort_values("mean")
    fig, ax = plt.subplots(figsize=(8, 5.6))
    ax.barh(g.index, g["mean"] * 100, color="#b00020")
    for y, (rate, n) in enumerate(zip(g["mean"], g["count"])):
        ax.text(rate * 100 + 0.05, y, f"{n:,}", va="center", fontsize=7)
    ax.set_xlabel("% that failed to recruit (labels: trials)")
    return fig


@plot("Failure rate by start year and phase", "Recruitment failure rate over time, one line per phase group")
def _year(ctx):
    t = ctx.task()
    t["phase_group"] = t["phase"].where(t["phase"].isin(["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Not applicable"]), "Other")
    g = t[t["year"].between(2005, 2024)].groupby(["year", "phase_group"])["fail"].mean().unstack() * 100
    fig, ax = plt.subplots(figsize=(8, 4.6))
    g.plot(ax=ax, marker="o", ms=3)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.set_ylabel("% failed to recruit")
    ax.set_xlabel("start year (recent years are biased low: trials still recruiting are not in scope)")
    return fig


@plot("Score distribution of the best scorer", "Test-split scores for completed trials versus trials that failed to recruit (log scale)")
def _dist(ctx):
    best = max((k for k in ctx.metrics["scorers"] if k != "random"), key=lambda k: ctx.metrics["scorers"][k]["test"]["all"].get("auroc") or 0)
    col = "score_" + best.replace(":", "_")
    t = ctx.task()
    te = t[(t["split"] == "test") & t[col].notna()]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.hist(te.loc[te.fail == 0, col], bins=60, alpha=.6, density=True, color="#0b6b2e", label="completed")
    ax.hist(te.loc[te.fail == 1, col], bins=60, alpha=.6, density=True, color="#b00020", label="failed to recruit")
    ax.set_yscale("log")
    ax.set_xlabel(f"{best} score")
    ax.legend()
    return fig


@plot("AUROC bootstrap distribution (computed on the GPU)", "5,000 bootstrap resamples of the best scorer's test AUROC as one batched job; uses CUDA when present, the CPU otherwise")
def _boot(ctx):
    from . import gpu
    best = max((k for k in ctx.metrics["scorers"] if k != "random"), key=lambda k: ctx.metrics["scorers"][k]["test"]["all"].get("auroc") or 0)
    col = "score_" + best.replace(":", "_")
    t = ctx.task()
    te = t[(t["split"] == "test") & t[col].notna()]
    t0 = time.time()
    au = gpu.bootstrap_distribution(te["fail"].tolist(), te[col].tolist(), resamples=5000, seed=28, pref=ctx.pref)
    secs = time.time() - t0
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.hist(au, bins=70, color="#0040ff", alpha=.8)
    lo, hi = float(ctx.np.quantile(au, 0.025)), float(ctx.np.quantile(au, 0.975))
    ax.axvline(lo, color="#111", ls="--")
    ax.axvline(hi, color="#111", ls="--")
    ax.set_xlabel(f"AUROC, {best}, 5,000 resamples: 95% interval {lo:.3f} to {hi:.3f}  ({secs:.1f} s on {ctx.device})")
    return fig
