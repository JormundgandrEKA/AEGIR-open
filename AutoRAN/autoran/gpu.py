"""GPU backend (PyTorch). Optional: AutoRAN's standard-library path stays the reference and the fallback.

What runs here, and why it is worth it:
- scorers trained on the FULL train split (not a 45k sample), early-stopped on the dev split, then calibrated on dev;
- a small neural scorer (`gpu_mlp`) next to the two linear ones;
- bootstrap intervals for AUROC and AUPRC as one batched job (1,000 resamples in seconds);
- a Parquet table of every trial, label, category and score, for pandas, matplotlib, plotly or R (arrow).
Fetching, normalising and the regex labeller are I/O or string work and stay on the CPU.
"""
import json
import math
import time
import zlib

from . import stats
from .core import Paths, iso_now, iter_jsonl, utc_stamp
from .scorers import BINARY, featurize, input_view, iter_joined

TEXT_DIM = 1024


def _torch():
    try:
        import numpy as np
        import torch
        return np, torch
    except ImportError as e:
        raise SystemExit("The GPU backend needs PyTorch and numpy. Run from a Python that has them, or give the small AutoRAN.exe a GPU pack: "
                         "a gpu_pack folder next to it (pip install --target gpu_pack torch --index-url https://download.pytorch.org/whl/cu128) "
                         f"or Settings > GPU pack folder. ({e})")


def info():
    np, torch = _torch()
    d = {"torch": torch.__version__, "cuda_available": torch.cuda.is_available(), "cuda": torch.version.cuda}
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        d.update({"device": p.name, "memory_gb": round(p.total_memory / 2 ** 30, 1), "capability": f"{p.major}.{p.minor}"})
    return d


def device(pref="auto"):
    np, torch = _torch()
    if pref == "cpu":
        return torch.device("cpu")
    if pref == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda was asked for, but PyTorch cannot see a CUDA GPU. Run `autoran gpu-info`.")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# -- features: explicit vocabulary for the tabular part, hashed words for the text part ----------

def _split_features(f):
    tab, txt = {}, {}
    for k, v in f.items():
        if k.startswith("w") and k[1:].isdigit():
            txt[int(k[1:]) % TEXT_DIM] = max(txt.get(int(k[1:]) % TEXT_DIM, 0.0), v)
        else:
            tab[k] = v
    return tab, txt


def build_matrix(paths, want_text=True):
    """One pass over the binary-task trials. Returns (X float32 [N, D], y, nct list, split list, tabular names)."""
    np, torch = _torch()
    rows_tab, rows_txt, ys, ncts, splits = [], [], [], [], []
    vocab = {}
    for rec, lab, cat in iter_joined(paths):
        if lab["class"] not in BINARY:
            continue
        tab, txt = _split_features(featurize(input_view(rec), text=True))
        for k in tab:
            if k not in vocab:
                vocab[k] = len(vocab)
        rows_tab.append(tab)
        rows_txt.append(txt)
        ys.append(1 if lab["class"] == "positive_recruitment" else 0)
        ncts.append(rec["nct_id"])
        splits.append(cat["split"])
    T = len(vocab)
    D = T + (TEXT_DIM if want_text else 0)
    X = np.zeros((len(ys), D), dtype=np.float32)
    for i, (tab, txt) in enumerate(zip(rows_tab, rows_txt)):
        for k, v in tab.items():
            X[i, vocab[k]] = v
        if want_text:
            for j, v in txt.items():
                X[i, T + j] = v
    names = sorted(vocab, key=vocab.get)
    return X, np.array(ys, dtype=np.float32), ncts, np.array(splits), names, T


# -- models -------------------------------------------------------------------------------------

def _auc_gpu(y, s, torch):
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = torch.empty_like(s)
    r[torch.argsort(s)] = torch.arange(1, len(s) + 1, device=s.device, dtype=s.dtype)
    return float(((r * y).sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


class Net:
    """A scorer: linear (hidden=0) or a small MLP, trained with Adam on the whole train split."""

    def __init__(self, name, hidden, text, dev, seed=28):
        self.name, self.hidden, self.text, self.dev, self.seed = name, hidden, text, dev, seed
        self.mean = self.std = self.model = None
        self.platt = (1.0, 0.0)

    def _build(self, d, torch):
        torch.manual_seed(self.seed)
        if self.hidden:
            self.model = torch.nn.Sequential(torch.nn.Linear(d, self.hidden), torch.nn.ReLU(), torch.nn.Dropout(0.25),
                                             torch.nn.Linear(self.hidden, 128), torch.nn.ReLU(), torch.nn.Dropout(0.25),
                                             torch.nn.Linear(128, 1)).to(self.dev)
        else:
            self.model = torch.nn.Linear(d, 1).to(self.dev)

    def _cols(self, T, D):
        return slice(0, D if self.text else T)

    def fit(self, X, y, split, T, epochs=60, patience=6, batch=4096):
        np, torch = _torch()
        cols = self._cols(T, X.shape[1])
        tr = torch.tensor(np.where(split == "train")[0], device=self.dev)
        dv = torch.tensor(np.where(split == "dev")[0], device=self.dev)
        Xg = torch.tensor(X[:, cols], device=self.dev)
        yg = torch.tensor(y, device=self.dev)
        mu = Xg[tr].mean(0, keepdim=True)
        sd = Xg[tr].std(0, keepdim=True).clamp_min(1e-3)
        self.mean, self.std, self.cols = mu, sd, cols
        Xg = (Xg - mu) / sd
        self._build(Xg.shape[1], torch)
        npos = float(yg[tr].sum())
        pw = torch.tensor(math.sqrt((len(tr) - npos) / max(npos, 1.0)), device=self.dev)
        lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pw)
        opt = torch.optim.AdamW(self.model.parameters(), lr=2e-3, weight_decay=1e-3 if self.hidden else 1e-4)
        best, best_state, bad, hist = -1.0, None, 0, []
        g = torch.Generator(device="cpu").manual_seed(self.seed)
        for ep in range(epochs):
            self.model.train()
            perm = tr[torch.randperm(len(tr), generator=g).to(self.dev)]
            for i in range(0, len(perm), batch):
                b = perm[i:i + batch]
                opt.zero_grad()
                loss = lossf(self.model(Xg[b]).squeeze(1), yg[b])
                loss.backward()
                opt.step()
            self.model.eval()
            with torch.no_grad():
                a = _auc_gpu(yg[dv], self.model(Xg[dv]).squeeze(1), torch)
            hist.append(round(a, 4))
            if a > best + 1e-4:
                best, bad = a, 0
                best_state = {k: v.detach().clone() for k, v in self.model.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break
        self.model.load_state_dict(best_state)
        self.model.eval()
        # Platt scaling on dev so scores read as probabilities on the real (low) base rate
        with torch.no_grad():
            z = self.model(Xg[dv]).squeeze(1)
        ab = torch.tensor([1.0, math.log(max(npos, 1) / max(len(tr) - npos, 1))], device=self.dev, requires_grad=True)
        o = torch.optim.LBFGS([ab], max_iter=60)
        yd = yg[dv]

        def closure():
            o.zero_grad()
            l = torch.nn.functional.binary_cross_entropy_with_logits(ab[0] * z + ab[1], yd)
            l.backward()
            return l
        o.step(closure)
        self.platt = (float(ab[0].detach()), float(ab[1].detach()))
        self.history = {"dev_auroc_by_epoch": hist, "best_dev_auroc": round(best, 4), "epochs_run": len(hist)}
        return self

    def predict(self, X, batch=65536):
        np, torch = _torch()
        out = []
        with torch.no_grad():
            for i in range(0, len(X), batch):
                xb = torch.tensor(X[i:i + batch][:, self.cols], device=self.dev)
                z = self.model(((xb - self.mean) / self.std)).squeeze(1)
                out.append(torch.sigmoid(self.platt[0] * z + self.platt[1]).cpu())
        return torch.cat(out).numpy()


GPU_SCORERS = {"gpu_logistic": dict(hidden=0, text=False), "gpu_logistic_text": dict(hidden=0, text=True),
               "gpu_mlp": dict(hidden=512, text=True)}


def score_gpu(ctx, cfg, pref="auto", names=None):
    np, torch = _torch()
    dev = device(pref)
    paths = Paths(ctx.root).ensure()
    names = [n for n in (names or GPU_SCORERS) if n in GPU_SCORERS]
    t0 = time.time()
    X, y, ncts, split, vocab, T = build_matrix(paths)
    t_feat = time.time() - t0
    stamp = utc_stamp()
    out = {"device": str(dev), "features_seconds": round(t_feat, 1), "rows": len(y), "tabular_features": T, "scorers": {}}
    for n in names:
        t1 = time.time()
        net = Net(n, dev=dev, seed=cfg["bootstrap"]["seed"], **GPU_SCORERS[n]).fit(X, y, split, T)
        p = net.predict(X)
        with open(paths.derived / f"scores_{n}_{stamp}.jsonl", "xb") as f:
            for nct, s in zip(ncts, p):
                f.write((json.dumps({"nct_id": nct, "score": round(float(s), 6)}, separators=(",", ":")) + "\n").encode("utf-8"))
        te = split == "test"
        out["scorers"][n] = {"seconds": round(time.time() - t1, 1), "test_auroc": round(stats.auroc(y[te].astype(int).tolist(), p[te].tolist()), 4), **net.history}
    if dev.type == "cuda":
        out["peak_gpu_memory_gb"] = round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)
    ctx.store.append("autoran_stages.jsonl", {"stage": "score_gpu", "stamp": stamp, "scorers": names, "device": str(dev), "ts": iso_now()})
    return out


# -- batched bootstrap ---------------------------------------------------------------------------

def bootstrap_gpu(y, s, resamples=1000, seed=28, pref="auto", chunk=125):
    """95% percentile intervals for AUROC and AUPRC; every resample is a row of one batched sort. Ties are broken by a tiny seeded jitter
    (an unbiased half-credit in expectation), so results differ from the CPU path in the third decimal at most."""
    np, torch = _torch()
    dev = device(pref)
    yt = torch.tensor(y, dtype=torch.float32, device=dev)
    st = torch.tensor(s, dtype=torch.float32, device=dev)
    n = len(y)
    g = torch.Generator(device=dev).manual_seed(seed)
    au, ap = [], []
    for c in range(0, resamples, chunk):
        b = min(chunk, resamples - c)
        idx = torch.randint(0, n, (b, n), device=dev, generator=g)
        ys, ss = yt[idx], st[idx] + 1e-9 * torch.rand((b, n), device=dev, generator=g)
        n1 = ys.sum(1)
        n0 = n - n1
        order = torch.argsort(ss, dim=1)
        ranks = torch.empty_like(ss)
        ranks.scatter_(1, order, torch.arange(1, n + 1, device=dev, dtype=torch.float32).expand(b, n))
        au.append(((ranks * ys).sum(1) - n1 * (n1 + 1) / 2) / (n1 * n0).clamp_min(1))
        desc = torch.flip(order, dims=[1])
        ysd = torch.gather(ys, 1, desc)
        tp = torch.cumsum(ysd, 1)
        prec = tp / torch.arange(1, n + 1, device=dev, dtype=torch.float32)
        ap.append((prec * ysd).sum(1) / n1.clamp_min(1))
    au = torch.sort(torch.cat(au)).values.cpu().numpy()
    ap = torch.sort(torch.cat(ap)).values.cpu().numpy()
    lo, hi = int(0.025 * resamples), int(0.975 * resamples) - 1
    return {"auroc": [round(float(au[lo]), 4), round(float(au[hi]), 4)], "auprc": [round(float(ap[lo]), 4), round(float(ap[hi]), 4)]}


def bootstrap_distribution(y, s, resamples=5000, seed=28, pref="auto", chunk=125):
    """The bootstrap AUROC values themselves (a numpy array), one batched GPU job. Falls back to the CPU device if there is no GPU."""
    np, torch = _torch()
    dev = device(pref)
    yt = torch.tensor(y, dtype=torch.float32, device=dev)
    st = torch.tensor(s, dtype=torch.float32, device=dev)
    n = len(y)
    g = torch.Generator(device=dev).manual_seed(seed)
    out = []
    for c in range(0, resamples, chunk):
        b = min(chunk, resamples - c)
        idx = torch.randint(0, n, (b, n), device=dev, generator=g)
        ys, ss = yt[idx], st[idx] + 1e-9 * torch.rand((b, n), device=dev, generator=g)
        n1 = ys.sum(1)
        order = torch.argsort(ss, dim=1)
        ranks = torch.empty_like(ss)
        ranks.scatter_(1, order, torch.arange(1, n + 1, device=dev, dtype=torch.float32).expand(b, n))
        out.append(((ranks * ys).sum(1) - n1 * (n1 + 1) / 2) / (n1 * (n - n1)).clamp_min(1))
    return torch.cat(out).cpu().numpy()


def summarize_gpu(y, s, resamples=1000, seed=28, pref="auto"):
    """Same output as stats.summarize, with the bootstrap on the GPU."""
    n1 = sum(y)
    base = {"n": len(y), "positives": n1, "base_rate": round(n1 / len(y), 4) if y else None}
    if n1 == 0 or n1 == len(y):
        base.update({"auroc": None, "auprc": None, "ci": {}, "note": "needs both classes"})
        return base
    full = stats.summarize(y, s, resamples=1, seed=seed)       # exact point estimates, curves and calibration (cheap)
    full["ci"] = bootstrap_gpu(y, s, resamples, seed, pref)
    return full


# -- the Parquet table for plots ----------------------------------------------------------------------

def frame(ctx, cfg):
    """Every trial with its label, categories and scores as one Parquet file (pandas, matplotlib, plotly, R arrow)."""
    np, torch = _torch()
    import pyarrow as pa
    import pyarrow.parquet as pq
    from .scorers import load_scores
    paths = Paths(ctx.root).ensure()
    scores = load_scores(paths)
    out = paths.derived / f"frame_{utc_stamp()}.parquet"
    writer, buf, n = None, [], 0

    def flush():
        nonlocal writer
        if not buf:
            return
        t = pa.Table.from_pylist(buf)
        if writer is None:
            writer = pq.ParquetWriter(out, t.schema, compression="zstd")
        writer.write_table(t.cast(writer.schema))
        buf.clear()
    for rec, lab, cat in iter_joined(paths):
        row = {"nct_id": rec["nct_id"], "title": rec["title"], "status": rec["status"], "start": rec["start"], "year": cat["year"],
               "class": lab["class"], "stop_class": cat["stop_class"], "label_source": lab["label_source"], "confidence": lab["confidence"],
               "labeller_disagree": bool(lab["labeller_disagree"]), "phase": cat["phase"], "area": cat["areas"][0], "areas": "|".join(cat["areas"]),
               "sponsor_class": cat["sponsor_class"], "region": cat["region"], "site_band": cat["site_band"], "n_sites": rec["n_sites"],
               "allocation": cat["allocation"], "masking": cat["masking"], "purpose": cat["purpose"], "input_state": cat["input_state"],
               "registration": cat["registration"], "split": cat["split"], "n_incl": rec["eligibility"]["n_incl"], "n_excl": rec["eligibility"]["n_excl"],
               "n_words": rec["eligibility"]["n_words"], "n_primary": rec["n_primary"], "n_arms": rec["n_arms"],
               "enrollment_actual": (rec["enrollment"] or {}).get("count")}
        for k, m in scores.items():
            row["score_" + k.replace(":", "_")] = m.get(rec["nct_id"])
        buf.append(row)
        n += 1
        if len(buf) >= 40000:
            flush()
    flush()
    if writer:
        writer.close()
    ctx.store.append("autoran_stages.jsonl", {"stage": "frame", "file": ctx.store.rel(out), "n": n, "ts": iso_now()})
    return {"file": str(out), "rows": n, "scorers": sorted(scores)}
