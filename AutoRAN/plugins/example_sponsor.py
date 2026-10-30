"""Example plot plug-in. Copy this file, change it, press Refresh on the Plots page. Files starting with _ are ignored.

ctx.frame()   every trial with its label, categories and scores (pandas DataFrame, from the newest Parquet frame)
ctx.task()    completed + recruitment-failure trials only, with a 0/1 column `fail`
ctx.metrics   the metrics file (dict)         ctx.device  a torch device, or None        ctx.torch, ctx.np   PyTorch and numpy
"""
from autoran.plots import plot


@plot("Failure rate by sponsor class", "Share of completed or failed trials that failed to recruit, by sponsor class, with trial counts")
def sponsor(ctx):
    import matplotlib.pyplot as plt
    g = ctx.task().groupby("sponsor_class")["fail"].agg(["mean", "count"]).query("count >= 200").sort_values("mean")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(g.index, g["mean"] * 100, color="#0040ff")
    for y, (rate, n) in enumerate(zip(g["mean"], g["count"])):
        ax.text(rate * 100 + 0.05, y, f"{n:,}", va="center", fontsize=8)
    ax.set_xlabel("% that failed to recruit (labels: trials)")
    return fig
