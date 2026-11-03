"""Simulation and proving ground for the risk model. Everything here is labelled for what it can and cannot show.

* `core`: a cheap stochastic recruitment core (sites open late, Poisson-gamma enrolment, periodic reviews, funding that ends,
  competing trials, other stops), calibrated to Kasenda et al. 2014. It is a SCENARIO tool: it shows how the simulator responds,
  never real-world value, until it passes the backtest gate (G4: calibrated on one era, it beats registry features on the next era's
  real outcomes). G4 is blocked today: the planned enrolment target at registration is not in the data we hold.
  There are no personas in this build, so the "no-persona control" is the core itself.
* `recovery`: plant known effects (and a hidden "prime mover" that drives several factors and the outcome) into real factor rows,
  then ask whether the risk model finds them, and how much label noise costs.
* `controls`: negative controls on the real registry (shuffled outcomes, random columns, a placebo outcome).
* `replay`: the honest baseline on real data, split by date, headlined on prospectively registered trials, with the metrics that do not
  flatter (AUPRC against its guessing level, precision at a review budget, calibration), by sponsor, phase and area, and against a
  baseline that already knows who runs the trial.
* `whatif`: model-implied change in risk for a protocol lever versus the stratified observed difference. Level 1 evidence only.
The sealed vault is never read here.
"""
import json
import math

import numpy as np

from . import risk
from .core import iso_now, utc_stamp

LEVEL = {1: "associated with failure (observational)", 2: "supported (also seen within trials, or consistent with published evidence)",
         3: "shown to cause (randomised or strong quasi-experimental)"}


def _p_two_sided(z):
    return math.erfc(abs(z) / math.sqrt(2))


def bh(p, q=0.05):
    """Benjamini-Hochberg: boolean array of discoveries at false-discovery rate q."""
    p = np.asarray(p)
    o = np.argsort(p)
    m = len(p)
    ok = p[o] <= q * (np.arange(1, m + 1) / m)
    k = np.max(np.where(ok)[0]) + 1 if ok.any() else 0
    out = np.zeros(m, bool)
    out[o[:k]] = True
    return out


def discoveries(model, q=0.05):
    """Terms whose effect survives false-discovery control, using the bootstrap spread. Needs a model fitted with boot >= 10."""
    sd = model.boot.std(0)[: len(model.beta) - 1]
    z = model.beta[:-1] / np.maximum(sd, 1e-9)
    p = np.array([_p_two_sided(v) for v in z])
    return bh(p, q), p


# -- the stochastic core, calibrated to Kasenda 2014 -----------------------------------------------------------------------------

ANCHORS = {"recruitment_stop_rate": 0.099, "any_stop_rate": 0.249, "median_fraction_at_recruitment_stop": 0.409,
           "industry_over_investigator_recruitment_stop": 8.4 / 26.5, "piloted_recruitment_stop_rate_max": 0.03}
DEFAULT = dict(mu_over=-0.1, a_strict=0.6, sig_over=0.45, review_stop=0.1, hazard_other=0.03, industry_other=2.0, fund_ext_inv=0.3, fund_ext_ind=0.8,
               compete=0.15, open_delay=3.0, het=8.0, fund_stop=0.15)


def core(n, p=None, seed=28, intervene=None, given=None):
    """Simulate n trials. `intervene` overrides design choices (cap_criteria, pilot_all, min_sites) while every random draw stays the same,
    so a control run and a test run differ only by the intervention (common random numbers)."""
    p = dict(DEFAULT, **(p or {}))
    iv = intervene or {}
    if given is not None:
        n = len(given["target"])
    r = np.random.default_rng(seed)
    industry = r.random(n) < 0.45
    pilot = r.random(n) < 0.03
    crit = np.maximum(2, np.round(np.exp(r.normal(2.7 + 0.2 * industry, 0.5)))).astype(float)
    target = np.maximum(20, np.round(np.exp(r.normal(5.0 + 0.4 * industry, 0.9))))
    rp = np.exp(r.normal(math.log(0.7), 0.5, n))                  # planned patients per site per month
    D = np.clip(r.normal(30, 10, n), 10, 96)                       # planned duration, and the sites a planner thinks it needs to meet it
    sites = np.maximum(1, np.ceil(target / (rp * (D - 4.0) * 0.9)))   # D stays fixed under an intervention; sites and criteria can change
    noise_o, noise_het, noise_k, noise_fund, u_other = r.normal(size=n), r.gamma(p["het"], 1 / p["het"], n), r.poisson(p["compete"] * 3, n), r.random(n), r.random((n, 4))
    if given is not None:                                          # run the core on real trials: their sponsor type, criteria, planned size and sites
        industry = np.asarray(given["industry"], bool)
        crit = np.asarray(given["crit"], float)
        target = np.maximum(10.0, np.asarray(given["target"], float))
        if "sites" in given:
            sites = np.maximum(1.0, np.asarray(given["sites"], float))
            D = np.clip(target / (rp * sites * 0.9) + 4.0, 10, 96)  # a plan consistent with the sites it has
    if "cap_criteria" in iv:
        crit = np.minimum(crit, iv["cap_criteria"])
    if iv.get("pilot_all"):
        pilot = np.ones(n, bool)
    if "min_sites" in iv:
        sites = np.maximum(sites, iv["min_sites"])
    strict = np.clip((crit - 10) / 20, 0, 1.5)
    over = np.exp(p["mu_over"] * (~pilot) + p["a_strict"] * strict * (~pilot) + p["sig_over"] * noise_o * np.where(pilot, 0.15, 1.0))
    lam = rp / over / (1 + 0.3 * noise_k) * noise_het              # true per-site rate; more sites now mean more capacity, not a longer plan
    delay = p["open_delay"] * np.where(industry, 0.6, 1.0)

    def expo(t):                                                  # site-months of exposure by month t, given staggered openings
        return t - delay * (1 - np.exp(-t / delay))
    fund_end = np.where(industry, D * (1 + p["fund_ext_ind"] * noise_fund), D * (1 + p["fund_ext_inv"] * noise_fund))
    enrolled = np.zeros(n)
    done = np.zeros(n, bool)
    reason = np.full(n, "completed", dtype=object)
    frac_at_stop = np.full(n, np.nan)
    tmax = np.ceil(D * 1.5).astype(int)
    T = int(tmax.max())
    for t in range(1, T + 1):
        active = ~done & (t <= tmax)
        if not active.any():
            break
        openf = 1 - np.exp(-t / delay)
        add = r.poisson(np.where(active, lam * sites * openf, 0))
        enrolled = np.where(active, enrolled + add, enrolled)
        full = active & (enrolled >= target)
        done |= full
        # other ways to stop, per month
        h = p["hazard_other"] / 12 * np.where(industry, p["industry_other"], 1.0)
        stop_other = active & ~full & (r.random(n) < h)
        reason = np.where(stop_other & ~done, "other", reason)
        frac_at_stop = np.where(stop_other & ~done, enrolled / target, frac_at_stop)
        done |= stop_other
        if t % 6 == 0:                                            # a review: projected shortfall can end the trial
            active = ~done & (t <= tmax)
            projected = enrolled / np.maximum(expo(t), 0.5) * expo(D)
            behind = projected < 0.8 * target
            stop_rec = active & behind & (t >= 0.25 * D) & (r.random(n) < p["review_stop"])
            reason = np.where(stop_rec, "recruitment", reason)
            frac_at_stop = np.where(stop_rec, enrolled / target, frac_at_stop)
            done |= stop_rec
        # funding ends: the trial stops, and when it was behind that is a recruitment consequence recorded with its cause
        active = ~done & (t <= tmax)
        late = enrolled / np.maximum(expo(t), 0.5) * expo(D) < 0.8 * target
        fund_stop = active & (t >= fund_end) & (enrolled < 0.8 * target) & (u_other[:, 0] < p["fund_stop"])    # only a trial that is well behind loses its money
        reason = np.where(fund_stop, np.where(late, "recruitment", "funding"), reason)
        frac_at_stop = np.where(fund_stop, enrolled / target, frac_at_stop)
        done |= fund_stop
    tail = ~done                                                  # ran out of time: 90% of target counts as complete, less is a recruitment stop
    short = tail & (enrolled < 0.9 * target)
    reason = np.where(short, "recruitment", reason)
    frac_at_stop = np.where(short, enrolled / target, frac_at_stop)
    return {"industry": industry, "pilot": pilot, "sites": sites, "crit": crit, "target": target, "reason": reason, "frac": frac_at_stop,
            "enrolled_frac": enrolled / target, "compete": noise_k}


def stop_probability(given, params, reps=20, seed=100):
    """For each real trial: the share of `reps` simulated runs that end in a recruitment stop, plus the mean share of target reached."""
    k = np.zeros(len(given["target"]))
    frac = np.zeros(len(given["target"]))
    for i in range(reps):
        c = core(0, params, seed + i, given=given)
        k += (c["reason"] == "recruitment")
        frac += np.minimum(c["enrolled_frac"], 1.5)
    return k / reps, frac / reps


def anchors_of(c):
    rs = c["reason"]
    rec = rs == "recruitment"
    ind, inv = c["industry"], ~c["industry"]
    return {"recruitment_stop_rate": float(rec.mean()), "any_stop_rate": float((rs != "completed").mean()),
            "median_fraction_at_recruitment_stop": float(np.nanmedian(c["frac"][rec])) if rec.any() else float("nan"),
            "industry_over_investigator_recruitment_stop": float(rec[ind].mean() / max(rec[inv].mean(), 1e-9)),
            "piloted_recruitment_stop_rate_max": float(rec[c["pilot"]].mean())}


def _loss(a):
    t = ANCHORS
    return (math.log(max(a["recruitment_stop_rate"], 1e-4) / t["recruitment_stop_rate"]) ** 2 + math.log(max(a["any_stop_rate"], 1e-4) / t["any_stop_rate"]) ** 2
            + (a["median_fraction_at_recruitment_stop"] - t["median_fraction_at_recruitment_stop"]) ** 2 * 8
            + math.log(max(a["industry_over_investigator_recruitment_stop"], 1e-3) / t["industry_over_investigator_recruitment_stop"]) ** 2
            + max(0.0, a["piloted_recruitment_stop_rate_max"] - t["piloted_recruitment_stop_rate_max"]) * 20)


def calibrate(n=40000, iters=160, seed=28, log=print):
    """Random search around the defaults. Fitted parameters reproduce published rates; they are not evidence the mechanism is right."""
    r = np.random.default_rng(seed)
    best = dict(DEFAULT)
    best_l = _loss(anchors_of(core(n, best, seed)))
    for i in range(iters):
        cand = {k: float(min(DEFAULT[k] * 4, max(DEFAULT[k] / 4, v * math.exp(r.normal(0, 0.18 * (1 - i / iters) + 0.03))))) if DEFAULT[k] > 0 else v for k, v in best.items()}
        cand["fund_stop"] = min(cand["fund_stop"], 1.0)
        l = _loss(anchors_of(core(n, cand, seed)))
        if l < best_l:
            best, best_l = cand, l
    a = anchors_of(core(n * 2, best, seed + 1))               # re-measured on fresh draws
    log(f"[calibrate] loss {best_l:.4f}")
    return {"params": best, "loss": best_l, "achieved": a, "anchors": ANCHORS}


def scenario(params, n=100000, seed=28):
    """Control versus test with common random numbers. Reports how the SIMULATOR responds to each lever. Nothing more."""
    base = anchors_of(core(n, params, seed))["recruitment_stop_rate"]
    out = {"control_recruitment_stop_rate": round(base, 4), "levers": {}}
    for name, iv in (("cap criteria at 15", {"cap_criteria": 15}), ("pilot with real consent for all", {"pilot_all": True}), ("at least 8 sites", {"min_sites": 8}),
                     ("all three", {"cap_criteria": 15, "pilot_all": True, "min_sites": 8})):
        t = anchors_of(core(n, params, seed, iv))["recruitment_stop_rate"]
        out["levers"][name] = {"recruitment_stop_rate": round(t, 4), "relative_change": round(t / base - 1, 3)}
    out["label"] = "SCENARIO ANALYSIS: how the simulator responds. Not real-world value (needs the G4 backtest and G5)."
    return out


# -- recovery of planted effects --------------------------------------------------------------------------------------------------

def recovery(m, seeds=6, noise_levels=(0.0, 0.05, 0.15), boot=16, n=60000, log=print):
    """Plant effects into real factor rows; fit; compare. Also plants a hidden prime mover U (driven by three real factors, acting on the
    outcome directly) so we can see what an unmeasured common cause does to the factors that share it."""
    X = m["X"][(m["split"] == "train")]
    names = m["names"]
    sup = X.mean(0)
    usable = [j for j in range(len(names)) if 0.03 <= sup[j] <= 0.7 and not names[j].startswith("start")]
    rows = []
    for seed in range(seeds):
        r = np.random.default_rng(100 + seed)
        idx = r.integers(0, len(X), n)
        Xs = X[idx]
        pick = list(r.choice(usable, 13, replace=False))
        true_main, conf = pick[:10], pick[10:]
        w = {j: float(r.choice([-1, 1]) * r.uniform(0.35, 0.9)) for j in true_main}
        pairs = []
        tries = 0
        while len(pairs) < 3 and tries < 400:
            a, b = r.choice(true_main, 2, replace=False)
            if (Xs[:, a] & Xs[:, b]).mean() > 0.02 and names[a].split("=")[0] != names[b].split("=")[0]:
                pairs.append((int(a), int(b)))
            tries += 1
        wp = [float(r.choice([-1, 1]) * 0.9) for _ in pairs]
        U = Xs[:, conf].astype(float).sum(1) + r.normal(0, 0.5, n)
        U = (U - U.mean()) / U.std()
        z = sum(w[j] * Xs[:, j] for j in true_main) + sum(c * Xs[:, a] * Xs[:, b] for c, (a, b) in zip(wp, pairs)) + 0.7 * U
        b0 = -3.5
        for _ in range(30):
            pbar = risk._sig(z + b0).mean()
            b0 += 0.7 * (math.log(0.04 / (1 - 0.04)) - math.log(pbar / (1 - pbar)))
        p_true = risk._sig(z + b0)
        y_true = (r.random(n) < p_true).astype(np.int8)
        for q in noise_levels:
            y = y_true.copy()
            lose = (y == 1) & (r.random(n) < q)                  # failures the labeller missed
            gain = (y == 0) & (r.random(n) < q * 0.04 / 0.96)    # false alarms, scaled to keep the base rate
            y[lose], y[gain] = 0, 1
            cut = int(n * 0.7)
            mod = risk.RiskModel("sim", names).fit(Xs[:cut], y[:cut], Xs[cut:], y[cut:], boot=boot, log=lambda *_: None)
            disc, pv = discoveries(mod)
            wh = mod.beta[:-1]
            tm = np.array([w[j] for j in true_main])
            wh_t = np.array([wh[j] for j in true_main])
            null_terms = [j for j in range(len(names)) if j not in true_main and j not in conf]
            found_pairs = {tuple(sorted(pp)) for pp in mod.pairs}
            true_pairs = {tuple(sorted(pp)) for pp in pairs}
            ps = mod.score(Xs[cut:])
            ok = y_true[cut:]
            rows.append({"seed": seed, "noise": q,
                         "sign_correct": float(np.mean(np.sign(wh_t) == np.sign(tm))), "corr_true_est": float(np.corrcoef(tm, wh_t)[0, 1]),
                         "rmse": float(np.sqrt(np.mean((wh_t - tm) ** 2))), "true_effects_found_fdr": float(np.mean([disc[j] for j in true_main])),
                         "null_factors_flagged_fdr": float(np.mean([disc[j] for j in null_terms])),
                         "prime_mover_factors_flagged_fdr": float(np.mean([disc[j] for j in conf])),
                         "pair_precision": len(found_pairs & true_pairs) / max(1, len(found_pairs)), "pair_recall": len(found_pairs & true_pairs) / max(1, len(true_pairs)),
                         "pairs_found": len(found_pairs), "auroc_vs_true_outcome": risk.auroc(ok, ps), "auroc_oracle": risk.auroc(ok, p_true[cut:]),
                         "ece": risk.calibration(y[cut:], ps)[1]})
        log(f"[recovery] seed {seed + 1}/{seeds} done")
    out = {}
    for q in noise_levels:
        rs = [x for x in rows if x["noise"] == q]
        out[str(q)] = {k: round(float(np.mean([x[k] for x in rs])), 4) for k in rs[0] if k not in ("seed", "noise")}
    return {"by_label_noise": out, "seeds": seeds, "n_rows": n,
            "reading": "Label noise is the share of true failures the labeller missed (with false alarms added to hold the base rate). A factor that only shares a hidden "
                       "common cause is flagged at the 'prime_mover_factors_flagged_fdr' rate: this is what 'associated with' means, and why nothing here is level 3."}


# -- negative controls on the real registry ----------------------------------------------------------------------------------------

def controls(m, boot=16, log=print):
    sp = m["split"]
    tr, dv = (sp == "train"), (sp == "dev")
    X, names = m["X"], m["names"]
    y = m["y"]["recruitment"]
    r = np.random.default_rng(5)
    out = {}
    k = dv & (y >= 0)
    ok = np.where(tr & (y >= 0))[0]
    nulls, flagged, kept = [], [], []
    for i in range(8):                                            # one shuffle is noisy on a small dev set, so build an empirical null
        ytr = y.copy()
        ytr[ok] = y[np.random.default_rng(10 + i).permutation(ok)]
        mod = risk.RiskModel("shuffled", names).fit(X[tr], ytr[tr], X[dv], y[dv], boot=boot if i == 0 else 0, log=lambda *_: None)
        nulls.append(risk.auroc(y[k], mod.score(X[k])))
        kept.append(len(mod.pairs))
        if i == 0:
            flagged.append(int(discoveries(mod)[0].sum()))
    out["shuffled_labels"] = {"dev_auroc_mean": round(float(np.mean(nulls)), 4), "dev_auroc_sd": round(float(np.std(nulls)), 4), "dev_auroc_range": [round(min(nulls), 4), round(max(nulls), 4)],
                              "expected": "mean about 0.5", "terms_flagged_fdr": flagged[0], "interactions_kept_max": max(kept), "shuffles": 8}
    fake = r.random((len(X), 12)) < r.uniform(0.05, 0.3, 12)
    Xf = np.hstack([X, fake.astype(np.uint8)])
    fn = names + [f"fake_{i}" for i in range(12)]
    mod = risk.RiskModel("fake", fn).fit(Xf[tr], y[tr], interactions=False, boot=boot, log=lambda *_: None)
    disc, _ = discoveries(mod)
    out["random_columns"] = {"fake_flagged_fdr": int(disc[len(names):].sum()), "of": 12, "expected": "0 or 1", "largest_fake_abs_logodds": round(float(np.abs(mod.beta[len(names):-1]).max()), 4)}
    nct = m["nct"]
    plc = np.array([(int(str(c)[-1]) % 2) for c in nct], np.int8)   # last digit of the NCT number: the protocol cannot cause it
    mod = risk.RiskModel("placebo", names).fit(X[tr], plc[tr], interactions=False)
    out["placebo_outcome"] = {"dev_auroc": round(risk.auroc(plc[dv], mod.score(X[dv])), 4), "expected": "about 0.5"}
    out["passed"] = bool(abs(out["shuffled_labels"]["dev_auroc_mean"] - 0.5) < 0.03 and out["shuffled_labels"]["terms_flagged_fdr"] <= 1 and out["random_columns"]["fake_flagged_fdr"] <= 1 and abs(out["placebo_outcome"]["dev_auroc"] - 0.5) < 0.03)
    log(f"[controls] passed={out['passed']}")
    return out


# -- the honest baseline on real data ------------------------------------------------------------------------------------------------

def _ci(y, s, fn, b=200, seed=1):
    r = np.random.default_rng(seed)
    v = []
    for _ in range(b):
        i = r.integers(0, len(y), len(y))
        if y[i].sum() and y[i].sum() < len(i):
            v.append(fn(y[i], s[i]))
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]


def at_budget(y, s, frac):
    k = max(1, int(len(y) * frac))
    top = np.argsort(-s, kind="mergesort")[:k]
    return {"precision": round(float(y[top].mean()), 4), "recall": round(float(y[top].sum() / max(1, y.sum())), 4), "lift": round(float(y[top].mean() / max(y.mean(), 1e-9)), 2)}


def replay(m, log=print, boot_ci=200):
    """Train on starts up to 2014 (never the vault, never the frozen test split), score 2016-2018. Headline: prospectively registered trials."""
    sp, yr, pr, X, names = m["split"], m["year"], m["prospective"], m["X"], m["names"]
    y = m["y"]["recruitment"]
    a = (sp != "vault") & (sp != "test") & (yr <= 2014) & (y >= 0)
    b = (sp != "vault") & (sp != "test") & (yr >= 2016) & (yr <= 2018) & (y >= 0)
    full = risk.RiskModel("recruitment", names).fit(X[a], y[a], interactions=False)
    ctx_cols = [j for j, n in enumerate(names) if n.startswith(("sites", "sponsor=", "start", "multi_country", "us_only", "no_us"))]
    ctx = risk.RiskModel("context", [names[j] for j in ctx_cols]).fit(X[a][:, ctx_cols], y[a], interactions=False)
    crit = X[:, [names.index(n) for n in ("criteria<=10", "criteria 11-20", "criteria 21-30", "criteria>30")]] @ np.array([5, 15, 25, 40])
    out = {"train": f"starts up to 2014 (n={int(a.sum())}, positives {int(y[a].sum())})", "score": "starts 2016-2018", "groups": {}}
    for label, mask in (("prospective (headline)", b & pr), ("retrospective", b & ~pr), ("all", b)):
        k = mask
        yy = y[k].astype(int)
        sf, sc, sr = full.score(X[k]), ctx.score(X[k][:, ctx_cols]), crit[k].astype(float)
        row = {"n": int(k.sum()), "positives": int(yy.sum()), "base_rate": round(float(yy.mean()), 4),
               "full": {"auroc": round(risk.auroc(yy, sf), 4), "auroc_ci": _ci(yy, sf, risk.auroc, boot_ci), "auprc": round(risk.auprc(yy, sf), 4),
                        "auprc_guessing_level": round(float(yy.mean()), 4), "top5": at_budget(yy, sf, 0.05), "top10": at_budget(yy, sf, 0.10), "ece": round(risk.calibration(yy, sf)[1], 4)},
               "who_runs_it_only": {"auroc": round(risk.auroc(yy, sc), 4), "auroc_ci": _ci(yy, sc, risk.auroc, boot_ci)},
               "criteria_count_only": {"auroc": round(risk.auroc(yy, sr), 4)}}
        d = np.random.default_rng(3)
        gain = []
        for _ in range(boot_ci):
            i = d.integers(0, len(yy), len(yy))
            if yy[i].sum():
                gain.append(risk.auroc(yy[i], sf[i]) - risk.auroc(yy[i], sc[i]))
        row["gain_over_who_runs_it"] = {"auroc": round(row["full"]["auroc"] - row["who_runs_it_only"]["auroc"], 4), "ci": [round(float(np.percentile(gain, 2.5)), 4), round(float(np.percentile(gain, 97.5)), 4)]}
        out["groups"][label] = row
    # by sponsor, phase, area on the prospective headline subset
    k0 = b & pr
    sf = full.score(X[k0])
    yy = y[k0].astype(int)
    strata = {}
    for fam, pref in (("sponsor", "sponsor="), ("phase", "phase="), ("area", "area=")):
        for j, n in enumerate(names):
            if not n.startswith(pref):
                continue
            s = X[k0][:, j] == 1
            if s.sum() >= 400 and 0 < yy[s].sum() < s.sum() and yy[s].sum() >= 25:
                strata[n] = {"n": int(s.sum()), "positives": int(yy[s].sum()), "auroc": round(risk.auroc(yy[s], sf[s]), 4), "auroc_ci": _ci(yy[s], sf[s], risk.auroc, 100)}
    out["by_stratum_prospective"] = strata
    out["calibration_prospective"] = risk.calibration(yy, sf)[0]
    out["models"] = {"full": full, "context": ctx}
    log("[replay] done")
    return out


# -- the source ledger: how much information each kind of source carries, measured the same way for all of them -----------------------------

KINDS = {"protocol": "a protocol choice", "who": "who runs the trial", "trend": "time and registration trend", "hindsight": "hindsight risk (known only later, or as edited later)",
         "incidental": "incidental and unlikely to matter", "control": "control (should carry nothing)", "joke": "astrology (a joke measure, used nowhere)"}


def ledger_blocks(m):
    """{family: (kind, usable at registration, 0/1 or numeric block)}. Silly families are kept on purpose: they are the noise floor."""
    X, names, ex = m["X"].astype(np.float32), m["names"], m["extras"]
    col = lambda *pre: X[:, [j for j, n in enumerate(names) if n.startswith(pre)]]
    ei = {n: i for i, n in enumerate(risk.EXTRAS)}

    def dummies(v, levels):
        return np.stack([(v == k).astype(np.float32) for k in levels], 1)

    nct = ex[:, ei["nct_num"]]
    qs = np.quantile(nct[nct > 0], np.linspace(0, 1, 9)[1:-1])
    nbin = np.digitize(nct, qs)
    tl = ex[:, ei["title_len"]]
    tb = np.digitize(tl, np.quantile(tl, [0.2, 0.4, 0.6, 0.8]))
    nc = np.minimum(ex[:, ei["n_conditions"]], 4)
    B = {
        "start era": ("trend", True, col("start")),
        "registered before the trial started": ("hindsight", True, ex[:, [ei["prospective"]]].astype(np.float32)),
        "registration order (NCT number)": ("trend", True, dummies(nbin, range(8))),
        "sponsor class": ("who", True, col("sponsor=")),
        "sites and countries": ("who", True, col("sites", "multi_country", "us_only", "no_us")),
        "phase": ("protocol", True, col("phase=")),
        "therapeutic area": ("protocol", True, col("area=")),
        "intervention type": ("protocol", True, col("itype=")),
        "design (arms, masking, allocation, purpose, outcomes)": ("protocol", True, col("masking=", "alloc=", "purpose=", "single_arm", "arms>=3", "primary>=3")),
        "eligibility size (criteria, exclusions, length)": ("protocol", True, col("criteria", "excl_heavy", "elig_words")),
        "eligibility people (age, sex, healthy volunteers)": ("protocol", True, col("age_span", "adult_only", "paediatric", "older_only", "healthy_volunteers", "one_sex")),
        "title length": ("incidental", True, dummies(tb, range(5))),
        "number of conditions": ("incidental", True, dummies(nc, range(5))),
        "start date has no day": ("incidental", True, dummies(ex[:, ei["start_weekday"]], [-1]) ),
        "Mercury in retrograde on the start day": ("joke", True, dummies(ex[:, ei["mercury_retro"]], [0, 1])),
        "start month": ("control", True, dummies(ex[:, ei["start_month"]], range(1, 13))),
        "start weekday": ("control", True, dummies(ex[:, ei["start_weekday"]], range(7))),
        "start day odd or even": ("control", True, dummies(ex[:, ei["start_day_odd"]], [0, 1])),
        "last digit of the NCT number": ("control", True, dummies(ex[:, ei["nct_last_digit"]], range(10))),
    }
    return B


def _eval_sets(m):
    sp, yr, pr, y = m["split"], m["year"], m["prospective"], m["y"]["recruitment"]
    ok = (sp != "vault") & (sp != "test") & (y >= 0)
    return {"train": ok & (yr <= 2014), "test": ok & (yr >= 2016) & (yr <= 2018), "prospective": pr}


def source_ledger(blocks, y, train, test, groups, boot=200, l2=4.0, log=print, seed=11):
    """Each family alone, and each family's unique contribution (full model minus the same model without it), on one date split.
    `groups` = {name: boolean mask over rows} (the subsets the intervals are reported on)."""
    full_cols = np.hstack([b for _, _, b in blocks.values()])
    allx = full_cols
    idx_of, o = {}, 0
    for k, (_, _, b) in blocks.items():
        idx_of[k] = np.arange(o, o + b.shape[1])
        o += b.shape[1]
    fit = lambda cols: risk.fit_logit(allx[train][:, cols], y[train].astype(float), l2)
    pr = lambda beta, cols, rows: risk._sig(allx[rows][:, cols] @ beta[:-1] + beta[-1])
    cols_all = np.arange(allx.shape[1])
    pf = pr(fit(cols_all), cols_all, test)
    out = {"groups": {}, "n_test": int(test.sum()), "failures_test": int(y[test].sum())}
    preds = {}
    for k in blocks:
        ci = idx_of[k]
        rest = np.setdiff1d(cols_all, ci)
        preds[k] = (pr(fit(ci), ci, test), pr(fit(rest), rest, test))
        log(f"[ledger] {k}")
    yt = y[test].astype(int)
    for gname, gm in groups.items():
        g = gm[test]
        rng = np.random.default_rng(seed)
        resamples = [rng.integers(0, g.sum(), g.sum()) for _ in range(boot)]
        yg = yt[g]
        base_auc = risk.auroc(yg, pf[g])
        rows = []
        for k, (kind, usable, _) in blocks.items():
            pa, pd_ = preds[k][0][g], preds[k][1][g]
            alone, uniq = [], []
            for i in resamples:
                if 0 < yg[i].sum() < len(i):
                    alone.append(risk.auroc(yg[i], pa[i]))
                    uniq.append(risk.auroc(yg[i], pf[g][i]) - risk.auroc(yg[i], pd_[i]))
            blk = allx[test][g][:, idx_of[k]]
            const = bool((blk.max(0) == blk.min(0)).all())          # no variation in this test set: nothing can be measured
            rows.append({"family": k, "kind": kind, "usable_at_registration": usable, "columns": int(len(idx_of[k])), "constant_in_test": const,
                         "alone_auroc": round(risk.auroc(yg, pa), 4), "alone_ci": [round(float(np.percentile(alone, 2.5)), 4), round(float(np.percentile(alone, 97.5)), 4)],
                         "unique_gain": round(risk.auroc(yg, pf[g]) - risk.auroc(yg, pd_), 4), "unique_ci": [round(float(np.percentile(uniq, 2.5)), 4), round(float(np.percentile(uniq, 97.5)), 4)]})
        out["groups"][gname] = {"n": int(g.sum()), "failures": int(yg.sum()), "full_model_auroc": round(base_auc, 4), "rows": rows}
    return out


def mercury_report(m):
    """Does the planet matter? Failure rate for trials that started with Mercury in apparent retrograde against those that did not, with its interval, and by year
    (so a fluke in one year is visible). Day-level start dates only; never the vault or the frozen test split."""
    sp, y, ex = m["split"], m["y"]["recruitment"], m["extras"]
    r = ex[:, risk.EXTRAS.index("mercury_retro")]
    ok = (sp != "vault") & (sp != "test") & (y >= 0) & (r >= 0)

    def rr(mask):
        a, b = mask & (r == 1), mask & (r == 0)
        na, nb, ka, kb = int(a.sum()), int(b.sum()), int(y[a].sum()), int(y[b].sum())
        if min(ka, kb) < 3:
            return None
        pa, pb = ka / na, kb / nb
        se = math.sqrt(1 / ka - 1 / na + 1 / kb - 1 / nb)
        z = math.log(pa / pb) / se
        return {"n_retro": na, "n_not": nb, "failures_retro": ka, "failures_not": kb, "rate_retro": round(pa, 5), "rate_not": round(pb, 5), "rr": round(pa / pb, 3),
                "rr_ci": [round(math.exp(math.log(pa / pb) - 1.96 * se), 3), round(math.exp(math.log(pa / pb) + 1.96 * se), 3)], "p": round(_p_two_sided(z), 4)}

    out = {"overall": rr(ok), "by_year": {}, "share_of_trials_in_retrograde": round(float((r[ok] == 1).mean()), 4)}
    for yr in range(2006, 2019):
        v = rr(ok & (m["year"] == yr))
        if v:
            out["by_year"][str(yr)] = v
    out["note"] = ("A joke measure, included on purpose. About one start day in five falls in a retrograde. If the stars mattered, the rate ratio would stay away from 1 across years; "
                   "with 13 years and 5% two-sided tests, about one year in twenty will look 'significant' by luck.")
    return out


def registry_ledger(m, boot=200, log=print):
    """Two settings. Forward: train on early starts, test on later ones (honest prediction; a time trend cannot show because the test years are
    outside the training years). Within period: train and test drawn from the same years by the hash split, so trends can show but the number
    flatters a forward forecast. Never the vault or the frozen test split."""
    sp, yr, pr, y = m["split"], m["year"], m["prospective"], m["y"]["recruitment"]
    ok = (sp != "vault") & (sp != "test") & (y >= 0)
    blocks = ledger_blocks(m)
    allr = np.ones(len(y), bool)
    fwd = source_ledger(blocks, y, ok & (yr <= 2014), ok & (yr >= 2016) & (yr <= 2018), {"prospective (headline)": pr, "all": allr}, boot, log=log)
    fwd.update(train="starts up to 2014", test="starts 2016 to 2018")
    wit = source_ledger(blocks, y, ok & (sp == "train"), ok & (sp == "dev"), {"prospective (headline)": pr, "all": allr}, boot, log=log)
    wit.update(train="hash split: train part, all years", test="hash split: dev part, all years")
    return {"settings": {"forward (honest prediction)": fwd, "within the same years (trends can show)": wit}, "kinds": KINDS, "mercury": mercury_report(m),
            "reading": ("Alone = how well that family predicts on its own. Unique = how much the full model loses without it. Controls and incidental families set the noise floor: an effect "
                        "no bigger than theirs is not distinguishable from chance. Time and registration trends are real and worth communicating and correcting for, but they describe "
                        "when and how a trial was registered, not how to write a protocol. A family marked as constant had no variation in that test set.")}


# -- other heads: one table, with the counts that decide whether to believe it ----------------------------------------------------------

def heads_table(m, log=print):
    sp, yr, X, names = m["split"], m["year"], m["X"], m["names"]
    out = {}
    for h in risk.HEADS:
        y = m["y"][h]
        a = (sp != "vault") & (sp != "test") & (yr <= 2014) & (y >= 0)
        b = (sp != "vault") & (sp != "test") & (yr >= 2016) & (yr <= 2018) & (y >= 0)
        if y[a].sum() < 100 or y[b].sum() < 30:
            out[h] = {"note": "too few failures to fit or test", "train_positives": int(y[a].sum()), "test_positives": int(y[b].sum())}
            continue
        mod = risk.RiskModel(h, names).fit(X[a], y[a], interactions=False)
        s = mod.score(X[b])
        yy = y[b].astype(int)
        out[h] = {"train_positives": int(y[a].sum()), "test_positives": int(yy.sum()), "auroc": round(risk.auroc(yy, s), 4), "auroc_ci": _ci(yy, s, risk.auroc, 100),
                  "auprc": round(risk.auprc(yy, s), 4), "guessing_level": round(float(yy.mean()), 4), "ece": round(risk.calibration(yy, s)[1], 4),
                  "label_source": "silver (machine-made; measured precision for recruitment about 97% on a spot check, others unmeasured)"}
    log("[heads] done")
    return out


# -- what-if: model-implied versus stratified observed (level 1) ------------------------------------------------------------------------

def whatif(m, model, log=print):
    sp, yr, pr, X, names = m["split"], m["year"], m["prospective"], m["X"], m["names"]
    y = m["y"]["recruitment"]
    b = (sp != "vault") & (sp != "test") & (yr >= 2016) & (yr <= 2018) & (y >= 0) & pr
    Xb, yb = X[b], y[b].astype(float)
    ix = lambda n: names.index(n)
    strata = (Xb[:, [ix(n) for n in names if n.startswith("sponsor=")]].argmax(1) * 100 + Xb[:, [ix(n) for n in names if n.startswith("phase=")]].argmax(1) * 10
              + Xb[:, [ix(n) for n in names if n.startswith("start")]].argmax(1))
    rows = []
    for lever in ("criteria>30", "sites=1", "excl_heavy", "elig_words>300", "age_span<=20y", "one_sex", "multi_country", "masking=NONE"):
        j = ix(lever)
        t = Xb[:, j] == 1
        if t.sum() < 300:
            continue
        flip = Xb[t].copy()
        flip[:, j] = 0
        implied = float((model.score(flip) - model.score(Xb[t])).mean())
        num = den = 0.0
        for s in np.unique(strata):
            m1, m0 = (strata == s) & t, (strata == s) & ~t
            if m1.sum() >= 20 and m0.sum() >= 20:
                num += m1.sum() * (yb[m0].mean() - yb[m1].mean())
                den += m1.sum()
        if den:
            rows.append({"lever": lever, "n_with": int(t.sum()), "model_implied_change_if_removed": round(implied, 4), "stratified_observed_change_if_removed": round(num / den, 4),
                         "same_direction": bool(np.sign(implied) == np.sign(num / den))})
    out = {"levels": LEVEL[1], "rows": rows,
           "agreement": round(float(np.mean([r["same_direction"] for r in rows])), 3) if rows else None,
           "reading": "Both columns come from the same observational data. Agreement shows the model matches a simpler stratified read; it does not show that changing the lever "
                      "changes outcomes (sponsor, site and funding choices sit behind both). Level 2 needs within-trial histories (RAN)."}
    log("[whatif] done")
    return out


GATES = [
    ("G0", "The pipeline works", "passed", "Reproduces published accrual prediction within its intervals."),
    ("G1", "This is the honest baseline", "measured", "Prospective, split-by-date baseline with intervals (this page, Headline)."),
    ("G2", "The labels are good enough", "pilot only", "Blind human audit with at least 200 cases per main class is not done."),
    ("G3", "AEGIR adds value", "not started", "Must beat the G1 baseline on the sealed vault."),
    ("G4", "The simulator is meaningful", "not passed", "First backtest (3 Nov): calibrated on trials starting up to 2015 and run on real 2016 to 2018 trials, it scored AUROC 0.52 against 0.80 for registry factors."),
    ("G5", "Preventive advice works", "not started", "Needs within-trial evidence or the prospective ledger."),
    ("G6", "It works in the world", "not started", "Prospective ledger not begun."),
]


def final_model(m, head="recruitment", boot=20, log=print):
    """The model behind the protocol explorer: all years, never the vault or the frozen test split; dev rows only decide whether interactions stay."""
    sp, X, names = m["split"], m["X"], m["names"]
    y = m["y"][head]
    tr, dv = sp == "train", sp == "dev"
    return risk.RiskModel(head, names).fit(X[tr], y[tr], X[dv], y[dv], boot=boot, log=log)


def latest(paths):
    d = paths.data / "derived" / "sim"
    fs = sorted(d.glob("sim_*.json")) if d.is_dir() else []
    return (json.loads(fs[-1].read_text(encoding="utf-8")), fs[-1]) if fs else (None, None)


def run_all(paths, seeds=6, boot=16, calibrate_iters=160, only=None, log=print):
    """Everything above, in order, with a summary file. The vault is never read; `risk.log_vault_look` exists for the day a claim needs it."""
    stamp = utc_stamp()
    only = only or ["calibrate", "controls", "replay", "heads", "recovery", "whatif", "model", "ledger"]
    m = risk.load_or_build(paths)
    out = {"stamp": stamp, "started": iso_now(), "vault_rows_excluded": int((m["split"] == "vault").sum()), "rows_used": int(((m["split"] != "vault") & (m["split"] != "test")).sum()),
           "label_source": "silver", "claim_level": LEVEL[1]}
    models = None
    if "calibrate" in only:
        cal = calibrate(iters=calibrate_iters, log=log)
        out["simulator"] = {"calibration": cal, "scenario": scenario(cal["params"]), "gate_G4": "not started: blocked (planned enrolment target at registration is not in the data)"}
    if "controls" in only:
        out["negative_controls"] = controls(m, boot, log)
    if "replay" in only:
        rp = replay(m, log)
        models = rp.pop("models")
        out["replay"] = rp
    if "heads" in only:
        out["heads"] = heads_table(m, log)
    if "recovery" in only:
        out["recovery"] = recovery(m, seeds=seeds, boot=boot, log=log)
    if "whatif" in only and models:
        out["whatif"] = whatif(m, models["full"], log)
    d = paths.data / "derived" / "sim"
    d.mkdir(parents=True, exist_ok=True)
    if "ledger" in only:
        out["ledger"] = registry_ledger(m, log=log)
    if "model" in only:
        fm = final_model(m, "recruitment", max(boot, 12), log)
        (d / f"model_recruitment_{stamp}.json").write_text(json.dumps(fm.dump()), encoding="utf-8")
        eff = fm.effects()
        out["effects"] = {"head": "recruitment", "level": LEVEL[1], "n": fm.n, "base_rate": round(fm.base, 5), "interactions": [fm.term_names()[len(fm.names) + i] for i in range(len(fm.pairs))],
                          "terms": sorted(eff, key=lambda e: -abs(e["logodds"])), "clusters": risk.clusters(m["X"][m["split"] == "train"], m["names"])}
    out["gates"] = [{"gate": g, "claim": c, "status": st, "note": n} for g, c, st, n in GATES]
    out["finished"] = iso_now()
    f = d / f"sim_{stamp}.json"
    f.write_text(json.dumps(out, indent=1), encoding="utf-8")
    out["file"] = str(f)
    return out
