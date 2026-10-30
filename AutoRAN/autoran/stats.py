"""Metrics, standard library only: AUROC, AUPRC, seeded bootstrap intervals, Wilson interval, precision at k, calibration."""
import math
import random


def wilson(k, n, z=1.96):
    """95% Wilson interval for a proportion; (0, 1) when n = 0."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def auroc(y, s):
    """Rank-sum AUROC with average ranks for ties. None when one class is missing."""
    n1 = sum(y)
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return None
    order = sorted(range(len(s)), key=lambda i: s[i])
    ranks = [0.0] * len(s)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and s[order[j + 1]] == s[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    rs = sum(ranks[i] for i in range(len(y)) if y[i])
    return (rs - n1 * (n1 + 1) / 2) / (n1 * n0)


def auprc(y, s):
    """Average precision."""
    n1 = sum(y)
    if n1 == 0:
        return None
    order = sorted(range(len(s)), key=lambda i: -s[i])
    tp = 0
    ap = 0.0
    for rank, i in enumerate(order, 1):
        if y[i]:
            tp += 1
            ap += tp / rank
    return ap / n1


def precision_at(y, s, frac):
    k = max(1, int(round(len(y) * frac)))
    order = sorted(range(len(s)), key=lambda i: -s[i])[:k]
    return sum(y[i] for i in order) / k


def calibration(y, p, bins=10):
    """Ten equal-count bins by score: mean score, observed rate, n."""
    order = sorted(range(len(p)), key=lambda i: p[i])
    out = []
    n = len(order)
    for b in range(bins):
        idx = order[b * n // bins:(b + 1) * n // bins]
        if idx:
            out.append({"bin": b + 1, "n": len(idx), "mean_score": round(sum(p[i] for i in idx) / len(idx), 4),
                        "observed": round(sum(y[i] for i in idx) / len(idx), 4)})
    return out


def _hist(vals, edges):
    import bisect
    h = [0] * (len(edges) + 1)
    for v in vals:
        h[bisect.bisect_right(edges, v)] += 1
    return h


def bootstrap_ci(y, s, resamples=1000, seed=28, bins=400):
    """95% percentile intervals for AUROC and AUPRC. Scores are binned (400 quantile bins) so each resample is two C-speed draws."""
    pos = [s[i] for i in range(len(y)) if y[i]]
    neg = [s[i] for i in range(len(y)) if not y[i]]
    if not pos or not neg:
        return {"auroc": None, "auprc": None}
    allv = sorted(s)
    edges = sorted({allv[min(len(allv) - 1, k * len(allv) // bins)] for k in range(1, bins)})
    hp, hn = _hist(pos, edges), _hist(neg, edges)
    nb = len(hp)
    cp = [sum(hp[:i + 1]) for i in range(nb)]
    cn = [sum(hn[:i + 1]) for i in range(nb)]
    rnd = random.Random(seed)
    au, ap = [], []
    for _ in range(resamples):
        bp = [0] * nb
        bn = [0] * nb
        for b in rnd.choices(range(nb), cum_weights=cp, k=len(pos)):
            bp[b] += 1
        for b in rnd.choices(range(nb), cum_weights=cn, k=len(neg)):
            bn[b] += 1
        below = 0
        wins = 0.0
        for b in range(nb):
            wins += bp[b] * (below + bn[b] / 2)
            below += bn[b]
        au.append(wins / (len(pos) * len(neg)))
        tp = fp = 0                               # sweep from the top bin down; ties inside a bin are taken at the bin's middle
        a = 0.0
        for b in range(nb - 1, -1, -1):
            if bp[b]:
                a += bp[b] * (tp + bp[b] / 2) / (tp + fp + (bp[b] + bn[b]) / 2)
            tp += bp[b]
            fp += bn[b]
        ap.append(a / len(pos))
    au.sort()
    ap.sort()
    lo, hi = int(0.025 * resamples), int(0.975 * resamples) - 1
    return {"auroc": [round(au[lo], 4), round(au[hi], 4)], "auprc": [round(ap[lo], 4), round(ap[hi], 4)]}


def summarize(y, s, resamples=1000, seed=28):
    """Everything one scorer needs on one set of trials."""
    n1 = sum(y)
    out = {"n": len(y), "positives": n1, "base_rate": round(n1 / len(y), 4) if y else None}
    if n1 == 0 or n1 == len(y):
        out.update({"auroc": None, "auprc": None, "ci": {}, "note": "needs both classes"})
        return out
    out["auroc"] = round(auroc(y, s), 4)
    out["auprc"] = round(auprc(y, s), 4)
    out["ci"] = bootstrap_ci(y, s, resamples, seed)
    out["precision_top5"] = round(precision_at(y, s, 0.05), 4)
    out["precision_top10"] = round(precision_at(y, s, 0.10), 4)
    out["calibration"] = calibration(y, s)
    # ROC and PR curve points (about 40) for the dashboard
    order = sorted(range(len(s)), key=lambda i: -s[i])
    n0 = len(y) - n1
    tp = fp = 0
    roc, pr = [[0.0, 0.0]], []
    step = max(1, len(order) // 40)
    for rank, i in enumerate(order, 1):
        if y[i]:
            tp += 1
        else:
            fp += 1
        if rank % step == 0 or rank == len(order):
            roc.append([round(fp / n0, 4), round(tp / n1, 4)])
            pr.append([round(tp / n1, 4), round(tp / rank, 4)])
    out["roc"], out["pr"] = roc, pr
    return out
