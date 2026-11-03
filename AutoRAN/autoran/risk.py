"""Risk model: the chance that a trial fails in a named way, from what is known at registration, with every factor's effect shown.

One design (`design`) turns a table of plain protocol facts into named yes/no factors. Real registry trials and simulated trials go
through the same function, so a model trained on one can be run on the other. The model is a ridge logistic regression plus a few
pairwise terms found by a score test and kept only if they improve held-out log-loss. Bootstrap refits say which effects are stable.

What it is: an association model. A factor that predicts failure may be a stand-in for something unmeasured (a "prime mover"), so
`clusters` reports which factors travel together. Nothing here reads a stop reason: outcomes come from the labels, inputs from the
registry's planning fields (`scorers.ALLOWED`). numpy only.
"""
import datetime
import hashlib
import json
import secrets

import numpy as np

from . import astro, taxonomy
from .categorize import TOP
from .core import Paths, iso_now, iter_jsonl, utc_stamp

PHASES = ["EARLY_PHASE1", "PHASE1", "PHASE1/PHASE2", "PHASE2", "PHASE2/PHASE3", "PHASE3", "PHASE4", "NA"]
SPONSORS = ["INDUSTRY", "NIH", "FED", "OTHER_GOV", "NETWORK", "INDIV", "OTHER"]
MASKS = ["NONE", "SINGLE", "DOUBLE", "TRIPLE", "QUADRUPLE"]
ALLOCS = ["RANDOMIZED", "NON_RANDOMIZED", "NA"]
PURPOSES = ["TREATMENT", "PREVENTION", "SUPPORTIVE_CARE", "DIAGNOSTIC", "SCREENING", "BASIC_SCIENCE", "HEALTH_SERVICES_RESEARCH", "OTHER"]
ITYPES = ["DRUG", "BIOLOGICAL", "DEVICE", "PROCEDURE", "BEHAVIORAL", "RADIATION", "DIETARY_SUPPLEMENT", "OTHER"]
AREAS = sorted(TOP)

# heads: one risk per named way to fail. "recruitment" and "any_stop" use the class; the rest use the super-labels of the tree.
HEADS = ["recruitment", "any_stop"] + [s for s in taxonomy.SUPER if s not in ("Participants", "Uninformative")]

# factors a protocol writer can change to ease recruitment (shown as advice only; never claimed causal)
MODIFIABLE = ["sites=1", "sites=2-5", "sites=6-20", "sites>20", "criteria<=10", "criteria 11-20", "criteria 21-30", "criteria>30", "excl_heavy",
              "elig_words>300", "age_span<=20y", "multi_country"]      # recruitment levers only; arms, outcomes and masking are scientific choices


def design(b):
    """b: dict of numpy arrays (see `base_from_trials`). Returns (uint8 matrix, names)."""
    c = {}
    n = len(b["sites"])
    s, cr = b["sites"], b["crit"]
    c["sites=1"] = s <= 1
    c["sites=2-5"] = (s >= 2) & (s <= 5)
    c["sites=6-20"] = (s >= 6) & (s <= 20)
    c["sites>20"] = s > 20
    c["multi_country"] = b["n_countries"] > 1
    c["us_only"] = b["us_only"]
    c["no_us"] = b["no_us"]
    c["criteria<=10"] = cr <= 10
    c["criteria 11-20"] = (cr > 10) & (cr <= 20)
    c["criteria 21-30"] = (cr > 20) & (cr <= 30)
    c["criteria>30"] = cr > 30
    c["excl_heavy"] = b["n_excl"] > 15
    c["elig_words>300"] = b["words"] > 300
    mn, mx = b["min_age"], b["max_age"]
    span = np.where(np.isnan(mx), 100.0, mx) - np.where(np.isnan(mn), 0.0, mn)
    c["age_span<=20y"] = span <= 20
    c["adult_only"] = ~np.isnan(mn) & (mn >= 18)
    c["paediatric"] = ~np.isnan(mx) & (mx < 18)
    c["older_only"] = ~np.isnan(mn) & (mn >= 60)
    c["healthy_volunteers"] = b["hv"]
    c["one_sex"] = b["one_sex"]
    for p in PHASES:
        c["phase=" + p] = b["phase"] == p
    for p in SPONSORS:
        c["sponsor=" + p] = b["sponsor"] == p
    for p in MASKS:
        c["masking=" + p] = b["mask"] == p
    for p in ALLOCS:
        c["alloc=" + p] = b["alloc"] == p
    for p in PURPOSES:
        c["purpose=" + p] = b["purpose"] == p
    c["single_arm"] = b["arms"] <= 1
    c["arms>=3"] = b["arms"] >= 3
    c["primary>=3"] = b["primary"] >= 3
    y = b["year"]
    c["start<2010"] = y < 2010
    c["start 2010-2014"] = (y >= 2010) & (y < 2015)
    c["start 2015-2019"] = (y >= 2015) & (y < 2020)
    c["start 2020-2022"] = (y >= 2020) & (y < 2023)
    c["start>=2023"] = y >= 2023
    for t in ITYPES:
        c["itype=" + t] = b["itype"][t]
    for a in AREAS:
        c["area=" + a] = b["area"][a]
    names = list(c)
    X = np.zeros((n, len(names)), np.uint8)
    for j, k in enumerate(names):
        X[:, j] = np.asarray(c[k], bool)
    return X, names


def base_from_trials(recs):
    """Arrays for `design` from normalised trial records (input fields only)."""
    n = len(recs)
    nan = float("nan")
    b = {k: np.zeros(n) for k in ("sites", "crit", "n_excl", "words", "n_countries", "arms", "primary", "year")}
    b["min_age"], b["max_age"] = np.full(n, nan), np.full(n, nan)
    for k in ("us_only", "no_us", "hv", "one_sex"):
        b[k] = np.zeros(n, bool)
    for k in ("phase", "sponsor", "mask", "alloc", "purpose"):
        b[k] = np.empty(n, object)
    b["itype"] = {t: np.zeros(n, bool) for t in ITYPES}
    b["area"] = {a: np.zeros(n, bool) for a in AREAS}
    for i, r in enumerate(recs):
        e = r["eligibility"]
        b["sites"][i], b["n_countries"][i] = r["n_sites"], len(r["countries"])
        b["crit"][i], b["n_excl"][i], b["words"][i] = e["n_incl"] + e["n_excl"], e["n_excl"], e["n_words"]
        if e.get("min_age_y") is not None:
            b["min_age"][i] = e["min_age_y"]
        if e.get("max_age_y") is not None:
            b["max_age"][i] = e["max_age_y"]
        b["hv"][i] = e.get("healthy_volunteers") is True
        b["one_sex"][i] = e.get("sex") in ("FEMALE", "MALE")
        b["arms"][i], b["primary"][i] = r["n_arms"], r["n_primary"]
        b["year"][i] = int((r.get("start") or "2015")[:4])
        cs = r["countries"]
        b["us_only"][i] = bool(cs) and all(c == "United States" for c in cs)
        b["no_us"][i] = bool(cs) and "United States" not in cs
        b["phase"][i] = "/".join(r["phases"] or ["NA"])
        b["sponsor"][i] = r["sponsor_class"] or "OTHER"
        b["mask"][i] = r["masking"] or "NONE"
        b["alloc"][i] = r["allocation"] or "NA"
        b["purpose"][i] = r["purpose"] or "OTHER"
        for t in r["intervention_types"]:
            if t in b["itype"]:
                b["itype"][t][i] = True
        for a in r["ancestors"] + r["mesh"]:
            if a in b["area"]:
                b["area"][a][i] = True
    return b


# -- the sealed vault (design principles 5.1): never trained on, tuned on or explored; every look is logged -----------------------

VAULT_YEARS = (2019, 2020)


def _salt(paths):
    f = paths.root / "state" / "vault_salt.txt"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_hex(16), encoding="utf-8")
    return f.read_text(encoding="utf-8").strip()


def vault_mask(paths, nct, year):
    """True for the sealed trials: a random 10% (hash of NCT number with a secret salt) plus every trial that started in 2019-2020."""
    salt = _salt(paths)
    h = np.array([int(hashlib.sha256((salt + n).encode()).hexdigest()[:8], 16) % 10 == 0 for n in nct])
    return h | ((year >= VAULT_YEARS[0]) & (year <= VAULT_YEARS[1]))


def log_vault_look(paths, who, model_hash, why, result):
    f = paths.root / "state" / "vault_looks.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": iso_now(), "who": who, "model": model_hash, "why": why, "result": result}) + "\n")


# -- the real registry as a matrix ---------------------------------------------------------------------------------------------

def head_outcomes(lab):
    """{head: 0/1/None}: None = this trial says nothing about this head (it stopped for some other reason)."""
    cls = lab["class"]
    out = {}
    done = cls == "negative_completed"
    stopped = cls in ("positive_recruitment", "other_stop", "unlabelled")
    out["recruitment"] = 1 if cls == "positive_recruitment" else (0 if done else None)
    out["any_stop"] = 1 if stopped else (0 if done else None)
    sc = set(lab.get("stop_classes") or [])
    for h in HEADS[2:]:
        out[h] = 0 if done else (1 if stopped and sc & set(taxonomy.SUPER[h]) else None)
    return out


EXTRAS = ["nct_num", "nct_last_digit", "start_month", "start_weekday", "start_day_odd", "title_len", "n_conditions", "prospective", "mercury_retro"]


def extras_of(recs, nct, prospective):
    """Per-trial odds and ends. Most are not protocol choices. They are kept so every source of apparent information can be measured."""
    out = np.zeros((len(recs), len(EXTRAS)), np.float64)
    for i, r in enumerate(recs):
        n = str(nct[i])
        d = (r.get("start") or "")
        out[i, 0] = float(n[3:]) if n[3:].isdigit() else 0.0
        out[i, 1] = int(n[-1]) if n[-1].isdigit() else -1
        out[i, 2] = int(d[5:7]) if len(d) >= 7 and d[5:7].isdigit() else 0
        if len(d) == 10:
            try:
                dt = datetime.date(int(d[:4]), int(d[5:7]), int(d[8:10]))
                out[i, 3], out[i, 4] = dt.weekday(), int(d[8:10]) % 2
            except ValueError:
                out[i, 3], out[i, 4] = -1, -1
        else:
            out[i, 3], out[i, 4] = -1, -1                    # a start date with no day (often a planned date)
        out[i, 5] = len(r.get("title") or "")
        out[i, 6] = len(r.get("conditions") or [])
        out[i, 7] = float(prospective[i])
        out[i, 8] = -1                                       # -1 = no day-level start date
        if len(d) == 10:
            try:
                out[i, 8] = float(astro.retrograde_on(datetime.date(int(d[:4]), int(d[5:7]), int(d[8:10]))))
            except ValueError:
                pass
    return out


def build_matrix(paths, limit=None):
    from .scorers import input_view, iter_joined
    recs, ys, split, nct, reg = [], {h: [] for h in HEADS}, [], [], []
    for i, (rec, lab, cat) in enumerate(iter_joined(paths)):
        if limit and i >= limit:
            break
        if lab["class"] not in ("negative_completed", "positive_recruitment", "other_stop", "unlabelled"):
            continue
        v = input_view(rec)
        v["n_sites"] = rec["n_sites"]
        recs.append(v)
        o = head_outcomes(lab)
        for h in HEADS:
            ys[h].append(-1 if o[h] is None else o[h])
        split.append(cat["split"])
        nct.append(rec["nct_id"])
        reg.append(cat.get("registration") == "prospective")
    X, names = design(base_from_trials(recs))
    year = np.array([int((r.get("start") or "2015")[:4]) for r in recs])
    split = np.array(split, dtype="<U5")
    split[vault_mask(paths, nct, year)] = "vault"        # the vault overrides the hash split; nothing downstream may read these rows
    return {"X": X, "names": names, "y": {h: np.array(v, np.int8) for h, v in ys.items()}, "split": split, "nct": np.array(nct),
            "year": year, "prospective": np.array(reg), "extras": extras_of(recs, nct, reg)}


def load_or_build(paths, limit=None):
    """Cached by the newest labels file, so reruns are quick and a new `label` run invalidates the cache."""
    lab = paths.latest("labels_*.jsonl")
    f = paths.derived / f"risk_matrix_v3_{lab.stem.split('_', 1)[1]}.npz"
    if f.exists() and not limit:
        z = np.load(f, allow_pickle=False)
        return {"X": z["X"], "names": list(z["names"]), "y": {h: z["y_" + h] for h in HEADS}, "split": z["split"], "nct": z["nct"], "year": z["year"],
                "prospective": z["prospective"], "extras": z["extras"]}
    m = build_matrix(paths, limit)
    if not limit:
        np.savez_compressed(f, X=m["X"], names=np.array(m["names"]), split=m["split"], nct=m["nct"], year=m["year"], prospective=m["prospective"], extras=m["extras"], **{"y_" + h: m["y"][h] for h in HEADS})
    return m


# -- the model -----------------------------------------------------------------------------------------------------------------

def _sig(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def fit_logit(X, y, l2=2.0, iters=30, tol=1e-6, init=None):
    """Ridge logistic by Newton steps. X float, y 0/1. Returns beta with the intercept last (not penalised)."""
    n, f = X.shape
    A = np.hstack([X, np.ones((n, 1), X.dtype)]).astype(np.float64)
    beta = np.zeros(f + 1) if init is None else init.copy()
    if init is None:
        p0 = (y.sum() + 1) / (n + 2)
        beta[-1] = np.log(p0 / (1 - p0))
    pen = np.full(f + 1, l2)
    pen[-1] = 0.0
    prev = np.inf
    for _ in range(iters):
        p = _sig(A @ beta)
        w = np.maximum(p * (1 - p), 1e-9)
        g = A.T @ (p - y) + pen * beta
        H = (A * w[:, None]).T @ A + np.diag(pen + 1e-9)
        step = np.linalg.solve(H, g)
        beta -= step
        loss = -np.sum(y * np.log(np.maximum(p, 1e-12)) + (1 - y) * np.log(np.maximum(1 - p, 1e-12))) + 0.5 * np.sum(pen * beta ** 2)
        if abs(prev - loss) < tol * max(1.0, abs(loss)):
            break
        prev = loss
    return beta


def predict(beta, X, pairs=()):
    A = _aug(X, pairs)
    return _sig(A @ beta[:-1] + beta[-1])


def _aug(X, pairs):
    X = X.astype(np.float32)
    if not len(pairs):
        return X
    return np.hstack([X, np.stack([X[:, i] * X[:, j] for i, j in pairs], 1)])


def auroc(y, s):
    y = np.asarray(y)
    npos, nneg = int(y.sum()), int(len(y) - y.sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s))
    ss = np.asarray(s)[order]
    # average ranks for ties
    uniq, first, counts = np.unique(ss, return_index=True, return_counts=True)
    avg = first + (counts + 1) / 2.0
    ranks[order] = np.repeat(avg, counts)
    return float((ranks[y == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def auprc(y, s):
    y = np.asarray(y)
    o = np.argsort(-np.asarray(s), kind="mergesort")
    yy = y[o]
    tp = np.cumsum(yy)
    prec = tp / np.arange(1, len(yy) + 1)
    return float((prec * yy).sum() / max(1, yy.sum()))


def logloss(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def calibration(y, p, bins=10):
    """Equal-count bins: (mean predicted, observed rate, n). ECE is their weighted mean absolute gap."""
    o = np.argsort(p)
    out, ece = [], 0.0
    for idx in np.array_split(o, bins):
        if not len(idx):
            continue
        mp, ob = float(p[idx].mean()), float(y[idx].mean())
        out.append({"pred": round(mp, 4), "obs": round(ob, 4), "n": int(len(idx))})
        ece += len(idx) / len(p) * abs(mp - ob)
    return out, float(ece)


def metrics(y, p):
    cal, ece = calibration(y, p)
    return {"n": int(len(y)), "positives": int(y.sum()), "base_rate": round(float(y.mean()), 5), "auroc": round(auroc(y, p), 4), "auprc": round(auprc(y, p), 4),
            "logloss": round(logloss(y, p), 5), "brier": round(float(np.mean((p - y) ** 2)), 6), "ece": round(ece, 5), "calibration": cal}


def screen_pairs(X, y, p, names, k=12, min_joint=300, zmin=5.0, support=0.01):
    """Score test for a product term on top of the main effects: z = sum(y-p) x_i x_j / sqrt(sum p(1-p) x_i x_j)."""
    Xf = X.astype(np.float32)
    keep = np.where(Xf.mean(0) >= support)[0]
    Xk = Xf[:, keep]
    r, w = (y - p).astype(np.float32), (p * (1 - p)).astype(np.float32)
    G = Xk.T @ (Xk * r[:, None])
    H = Xk.T @ (Xk * w[:, None])
    J = Xk.T @ Xk
    cand = []
    for a in range(len(keep)):
        for b in range(a + 1, len(keep)):
            i, j = keep[a], keep[b]
            if J[a, b] < min_joint or names[i].split("=")[0] == names[j].split("=")[0] and "=" in names[i] and "=" in names[j]:
                continue          # no product term between two values of the same variable (they never co-occur, or they are one thing)
            z = G[a, b] / np.sqrt(max(H[a, b], 1e-9))
            if abs(z) >= zmin:
                cand.append((abs(float(z)), int(i), int(j)))
    cand.sort(reverse=True)
    return [(i, j) for _, i, j in cand[:k]]


class RiskModel:
    def __init__(self, head, names, l2=2.0):
        self.head, self.names, self.l2 = head, list(names), l2
        self.beta, self.pairs, self.boot, self.raw = None, [], None, {}

    def fit(self, X, y, Xdev=None, ydev=None, boot=0, seed=28, interactions=True, log=print):
        m = y >= 0
        X, y = X[m], y[m].astype(np.float64)
        self.n, self.base = int(len(y)), float(y.mean())
        Xf = X.astype(np.float32)
        beta = fit_logit(Xf, y, self.l2)
        pairs = []
        if interactions and Xdev is not None and y.sum() >= 200:
            p = _sig(np.hstack([Xf, np.ones((len(y), 1), np.float32)]) @ beta)
            cand = screen_pairs(X, y, p, self.names)
            if cand:
                A = _aug(X, cand)
                b2 = fit_logit(A, y, self.l2)
                md = ydev >= 0
                ld0 = logloss(ydev[md], predict(beta, Xdev[md]))
                ld1 = logloss(ydev[md], predict(b2, Xdev[md], cand))
                log(f"[{self.head}] interactions screened {len(cand)}; dev logloss {ld0:.5f} -> {ld1:.5f}")
                if ld1 < ld0 - 1e-5:                # kept only if the held-out fit improves
                    beta, pairs = b2, cand
        self.beta, self.pairs = beta, pairs
        pos, neg = X[y == 1], X[y == 0]
        self.raw = {n: {"support": int(X[:, j].sum()), "rate_with": round(float(y[X[:, j] == 1].mean()), 5) if X[:, j].any() else None,
                        "rate_without": round(float(y[X[:, j] == 0].mean()), 5) if (X[:, j] == 0).any() else None} for j, n in enumerate(self.names)}
        if boot:
            rnd = np.random.default_rng(seed)
            A = _aug(X, pairs)
            Bs = []
            for b in range(boot):
                idx = rnd.integers(0, len(y), len(y))
                Bs.append(fit_logit(A[idx], y[idx], self.l2, init=self.beta))
            self.boot = np.array(Bs)
            log(f"[{self.head}] {boot} bootstrap refits done")
        return self

    def term_names(self):
        return self.names + [f"{self.names[i]} AND {self.names[j]}" for i, j in self.pairs]

    def effects(self):
        """Per term: log-odds, odds ratio, bootstrap 95% interval, stability (interval excludes 0), raw rates beside the adjusted effect."""
        out = []
        for k, t in enumerate(self.term_names()):
            w = float(self.beta[k])
            row = {"term": t, "logodds": round(w, 4), "odds_ratio": round(float(np.exp(w)), 3)}
            if self.boot is not None:
                lo, hi = np.percentile(self.boot[:, k], [2.5, 97.5])
                row.update(lo=round(float(np.exp(lo)), 3), hi=round(float(np.exp(hi)), 3), stable=bool(lo > 0 or hi < 0))
            row.update(self.raw.get(t, {}))
            out.append(row)
        return out

    def score(self, X):
        return predict(self.beta, X, self.pairs)

    def explain(self, x, k=8):
        """For one trial's factor row: what raises risk, what lowers it, and which protective factors are missing, each as the change
        in predicted risk if that factor alone were flipped (at this trial's own operating point)."""
        x = np.asarray(x, np.float32)[None, :]
        base = float(self.score(x)[0])
        rows = []
        for j, n in enumerate(self.names):
            if abs(self.beta[j]) < 1e-3 and not any(j in pr for pr in self.pairs):
                continue
            f = x.copy()
            f[0, j] = 1 - f[0, j]
            d = float(self.score(f)[0]) - base
            rows.append({"factor": n, "present": bool(x[0, j]), "change_if_flipped": round(d, 5), "modifiable": n in MODIFIABLE})
        raises = sorted([r for r in rows if r["present"] and r["change_if_flipped"] < 0], key=lambda r: r["change_if_flipped"])[:k]
        lowers = sorted([r for r in rows if r["present"] and r["change_if_flipped"] > 0], key=lambda r: -r["change_if_flipped"])[:k]
        missing = sorted([r for r in rows if not r["present"] and r["change_if_flipped"] < 0 and r["modifiable"]], key=lambda r: r["change_if_flipped"])[:k]   # only choices a writer can make
        return {"risk": round(base, 5), "raising": raises, "lowering": lowers, "missing_protective": missing}

    def dump(self):
        return {"head": self.head, "names": self.names, "l2": self.l2, "beta": self.beta.tolist(), "pairs": self.pairs, "n": self.n, "base": self.base,
                "boot": None if self.boot is None else self.boot.tolist(), "raw": self.raw}

    @classmethod
    def load(cls, d):
        m = cls(d["head"], d["names"], d["l2"])
        m.beta, m.pairs, m.n, m.base, m.raw = np.array(d["beta"]), [tuple(p) for p in d["pairs"]], d["n"], d["base"], d["raw"]
        m.boot = None if d["boot"] is None else np.array(d["boot"])
        return m


def clusters(X, names, support=0.01, thresh=0.3):
    """Factors that travel together (|phi| >= thresh), as connected groups. A shared prime mover shows up here, not in the model."""
    Xf = X.astype(np.float32)
    keep = [j for j in range(Xf.shape[1]) if Xf[:, j].mean() >= support and Xf[:, j].mean() <= 1 - support]
    C = np.corrcoef(Xf[:, keep].T)
    parent = list(range(len(keep)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    pairs = []
    for a in range(len(keep)):
        for b in range(a + 1, len(keep)):
            if abs(C[a, b]) >= thresh:
                parent[find(a)] = find(b)
                pairs.append({"a": names[keep[a]], "b": names[keep[b]], "phi": round(float(C[a, b]), 3)})
    groups = {}
    for a in range(len(keep)):
        groups.setdefault(find(a), []).append(names[keep[a]])
    return {"groups": [g for g in groups.values() if len(g) > 1], "pairs": sorted(pairs, key=lambda r: -abs(r["phi"]))[:40]}


def factor_groups(names):
    """For the protocol explorer: pick-one groups (a trial has one value) and tick-boxes (it can have several)."""
    one = [("Sites", [n for n in names if n.startswith("sites")]), ("Eligibility criteria", [n for n in names if n.startswith("criteria")]),
           ("Sponsor", [n for n in names if n.startswith("sponsor=")]), ("Phase", [n for n in names if n.startswith("phase=")]),
           ("Masking", [n for n in names if n.startswith("masking=")]), ("Allocation", [n for n in names if n.startswith("alloc=")]),
           ("Purpose", [n for n in names if n.startswith("purpose=")]), ("Start era", [n for n in names if n.startswith("start")])]
    used = {n for _, g in one for n in g}
    many = [("Intervention types", [n for n in names if n.startswith("itype=")]), ("Therapeutic areas", [n for n in names if n.startswith("area=")])]
    used |= {n for _, g in many for n in g}
    many.insert(0, ("Other design choices", [n for n in names if n not in used]))
    return {"pick_one": [{"group": g, "options": o} for g, o in one], "tick": [{"group": g, "options": o} for g, o in many]}
