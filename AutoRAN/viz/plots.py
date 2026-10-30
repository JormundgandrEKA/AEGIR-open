"""Starter plots from AutoRAN's Parquet frame and metrics file. Run it from the AutoRAN folder:

    python viz/plots.py              # newest frame and metrics
    python viz/plots.py --show       # also open interactive windows

Everything is plain pandas + matplotlib, so adapting a plot is a few lines. The same frame reads in R with arrow (see the AutoRAN README).
"""
import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.ticker
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DER = ROOT / "data" / "derived" / "autoran"


def newest(pattern):
    files = sorted(DER.glob(pattern))
    if not files:
        raise SystemExit(f"nothing matching {pattern}; run `autoran frame` and `autoran metrics` first")
    return files[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if not a.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = DER / "plots"
    out.mkdir(exist_ok=True)
    df = pd.read_parquet(newest("frame_*.parquet"))
    m = json.loads(newest("metrics_*.json").read_text(encoding="utf-8"))
    task = df[df["class"].isin(["positive_recruitment", "negative_completed"])].copy()
    task["fail"] = (task["class"] == "positive_recruitment").astype(int)
    plt.rcParams.update({"font.family": "DejaVu Sans Mono", "axes.edgecolor": "#111", "axes.linewidth": 1})

    # 1. how well each scorer separates failures, with bootstrap intervals (test split)
    rows = []
    for name, e in m["scorers"].items():
        for which in ("all", "clean"):
            b = e["test"][which]
            if b.get("auroc") is not None and b.get("ci", {}).get("auroc"):
                rows.append((name, which, b["auroc"], *b["ci"]["auroc"]))
    r = pd.DataFrame(rows, columns=["scorer", "set", "auroc", "lo", "hi"])
    fig, ax = plt.subplots(figsize=(8, 4.5))
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
    fig.tight_layout()
    fig.savefig(out / "auroc_by_scorer.png", dpi=150)

    # 2. recruitment-failure rate by therapeutic area
    g = task.groupby("area")["fail"].agg(["mean", "sum", "count"]).query("count >= 500").sort_values("mean")
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.barh(g.index, g["mean"] * 100, color="#b00020")
    for y, (rate, n) in enumerate(zip(g["mean"], g["count"])):
        ax.text(rate * 100 + 0.05, y, f"{n:,}", va="center", fontsize=7)
    ax.set_xlabel("% of completed + failed trials that failed to recruit (labels in bars: trials)")
    fig.tight_layout()
    fig.savefig(out / "failure_rate_by_area.png", dpi=150)

    # 3. failure rate by start year, split by phase group
    task["phase_group"] = task["phase"].where(task["phase"].isin(["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Not applicable"]), "Other")
    t = task[task["year"].between(2005, 2024)].groupby(["year", "phase_group"])["fail"].mean().unstack() * 100
    fig, ax = plt.subplots(figsize=(8, 4.5))
    t.plot(ax=ax, marker="o", ms=3)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.set_ylabel("% failed to recruit")
    ax.set_xlabel("start year")
    fig.tight_layout()
    fig.savefig(out / "failure_rate_by_year_phase.png", dpi=150)

    # 4. score distributions of the best scorer (test split)
    best = max((k for k in m["scorers"] if k != "random"), key=lambda k: m["scorers"][k]["test"]["all"].get("auroc") or 0)
    col = "score_" + best.replace(":", "_")
    te = task[(task["split"] == "test") & task[col].notna()]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(te.loc[te.fail == 0, col], bins=60, alpha=.6, density=True, color="#0b6b2e", label="completed")
    ax.hist(te.loc[te.fail == 1, col], bins=60, alpha=.6, density=True, color="#b00020", label="failed to recruit")
    ax.set_yscale("log")
    ax.set_xlabel(f"{best} score (predicted probability)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "score_distribution.png", dpi=150)
    print("wrote", ", ".join(sorted(p.name for p in out.glob("*.png"))), "to", out)
    if a.show:
        plt.show()


if __name__ == "__main__":
    main()
