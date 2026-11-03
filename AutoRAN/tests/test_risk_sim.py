"""Risk model and simulation harness. Synthetic data only; nothing is read from the registry and the vault is never touched."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import autoran  # noqa: E402,F401
import datetime  # noqa: E402
from autoran import astro, risk, sim  # noqa: E402
from autoran.core import Paths  # noqa: E402


def toy(n=20000, seed=1):
    r = np.random.default_rng(seed)
    X = (r.random((n, 6)) < [0.5, 0.3, 0.2, 0.4, 0.1, 0.6]).astype(np.uint8)
    z = -2.5 + 1.2 * X[:, 0] - 0.8 * X[:, 1] + 1.5 * X[:, 2] * X[:, 3]
    y = (r.random(n) < risk._sig(z)).astype(np.int8)
    return X, y, ["a", "b", "c", "d", "e", "f"]


class TestRisk(unittest.TestCase):
    def test_fit_recovers_effects_and_ignores_a_null_factor(self):
        X, y, names = toy()
        m = risk.RiskModel("t", names).fit(X[:14000], y[:14000], X[14000:], y[14000:], boot=12, log=lambda *_: None)
        eff = {e["term"]: e for e in m.effects()}
        self.assertGreater(eff["a"]["logodds"], 0.8)
        self.assertLess(eff["b"]["logodds"], -0.4)
        self.assertLess(abs(eff["e"]["logodds"]), 0.35)
        self.assertTrue(eff["a"]["stable"])
        self.assertIn(("c", "d"), [(names[i], names[j]) for i, j in m.pairs])        # the planted product term is found and kept

    def test_explain_names_raising_lowering_and_missing_protective_factors(self):
        X, y, names = toy()
        m = risk.RiskModel("t", names).fit(X, y, interactions=False)
        e = m.explain(np.array([1, 0, 0, 0, 0, 0]))
        self.assertTrue(any(r["factor"] == "a" for r in e["raising"]))
        self.assertFalse(any(r["factor"] == "b" for r in e["missing_protective"]))        # not a choice a protocol writer can make: never offered as advice
        from unittest import mock
        with mock.patch.object(risk, "MODIFIABLE", ["b"]):
            e = m.explain(np.array([1, 0, 0, 0, 0, 0]))
        self.assertTrue(any(r["factor"] == "b" and r["modifiable"] for r in e["missing_protective"]))

    def test_metrics_and_ties(self):
        y = np.array([0, 0, 1, 1])
        self.assertEqual(risk.auroc(y, np.array([0.1, 0.2, 0.8, 0.9])), 1.0)
        self.assertEqual(risk.auroc(y, np.array([0.5, 0.5, 0.5, 0.5])), 0.5)
        self.assertTrue(np.isnan(risk.auroc(np.zeros(4), np.arange(4))))

    def test_dump_and_load_give_the_same_scores(self):
        X, y, names = toy(4000)
        m = risk.RiskModel("t", names).fit(X, y, X, y, boot=4, log=lambda *_: None)
        w = risk.RiskModel.load(m.dump())
        self.assertTrue(np.allclose(m.score(X), w.score(X)))

    def test_the_vault_takes_a_random_tenth_plus_2019_and_2020_and_is_stable(self):
        p = Paths(tempfile.mkdtemp())
        nct = np.array([f"NCT{i:08d}" for i in range(5000)])
        year = np.array([2012] * 2500 + [2019] * 1250 + [2020] * 1250)
        v1 = risk.vault_mask(p, nct, year)
        v2 = risk.vault_mask(p, nct, year)
        self.assertTrue((v1 == v2).all())                                             # same salt, same vault
        self.assertTrue(v1[2500:].all())                                              # every 2019-2020 start
        self.assertAlmostEqual(v1[:2500].mean(), 0.10, delta=0.03)
        risk.log_vault_look(p, "test", "m0", "unit test", {"auroc": 0.5})
        self.assertEqual(len((p.root / "state" / "vault_looks.jsonl").read_text().splitlines()), 1)

    def test_design_columns_are_yes_no_and_the_same_for_every_row_source(self):
        n = 3
        b = {"sites": np.array([1, 5, 30.0]), "crit": np.array([8, 15, 40.0]), "n_excl": np.array([2, 8, 20.0]), "words": np.array([50, 200, 500.0]),
             "n_countries": np.array([1, 1, 3.0]), "arms": np.array([1, 2, 4.0]), "primary": np.array([1, 1, 3.0]), "year": np.array([2008, 2016, 2024.0]),
             "min_age": np.array([np.nan, 18, 0.0]), "max_age": np.array([np.nan, 65, 17.0]), "us_only": np.array([True, False, False]), "no_us": np.array([False, True, True]),
             "hv": np.zeros(n, bool), "one_sex": np.array([False, True, False]), "phase": np.array(["PHASE1", "PHASE2", "NA"], object),
             "sponsor": np.array(["INDUSTRY", "OTHER", "NIH"], object), "mask": np.array(["NONE", "DOUBLE", "NONE"], object), "alloc": np.array(["RANDOMIZED"] * 3, object),
             "purpose": np.array(["TREATMENT"] * 3, object), "itype": {t: np.zeros(n, bool) for t in risk.ITYPES}, "area": {a: np.zeros(n, bool) for a in risk.AREAS}}
        X, names = risk.design(b)
        col = lambda k: X[:, names.index(k)].tolist()
        self.assertEqual(col("sites=1"), [1, 0, 0])
        self.assertEqual(col("sites>20"), [0, 0, 1])
        self.assertEqual(col("criteria>30"), [0, 0, 1])
        self.assertEqual(col("paediatric"), [0, 0, 1])
        self.assertEqual(col("start>=2023"), [0, 0, 1])
        self.assertEqual(len(set(names)), len(names))


class TestSim(unittest.TestCase):
    def test_benjamini_hochberg(self):
        p = np.array([0.001, 0.009, 0.04, 0.2, 0.9])
        self.assertEqual(sim.bh(p, 0.05).tolist(), [True, True, False, False, False])

    def test_core_is_reproducible_and_levers_use_common_random_numbers(self):
        a, b = sim.core(5000, None, 3), sim.core(5000, None, 3)
        self.assertTrue((a["reason"] == b["reason"]).all())
        t = sim.core(5000, None, 3, {"pilot_all": True})
        self.assertTrue((t["target"] == a["target"]).all())                           # same trials, only the lever differs
        self.assertLess((t["reason"] == "recruitment").mean(), (a["reason"] == "recruitment").mean())

    def test_more_sites_never_lengthen_the_plan(self):
        a, t = sim.core(5000, None, 3), sim.core(5000, None, 3, {"min_sites": 20})
        self.assertLessEqual((t["reason"] == "recruitment").mean(), (a["reason"] == "recruitment").mean() + 1e-9)

    def test_scenario_is_labelled_as_a_scenario(self):
        out = sim.scenario(sim.DEFAULT, n=3000)
        self.assertIn("SCENARIO", out["label"])
        self.assertEqual(set(out["levers"]), {"cap criteria at 15", "pilot with real consent for all", "at least 8 sites", "all three"})


class TestLedgerAndStars(unittest.TestCase):
    def test_mercury_matches_published_retrograde_dates(self):
        d = datetime.date
        self.assertTrue(astro.retrograde_on(d(2024, 4, 10)))
        self.assertTrue(astro.retrograde_on(d(2024, 8, 15)))
        self.assertTrue(astro.retrograde_on(d(2020, 6, 25)))
        self.assertFalse(astro.retrograde_on(d(2024, 5, 20)))
        self.assertFalse(astro.retrograde_on(d(2020, 9, 1)))
        p = astro.periods(2024, 2024)
        self.assertEqual([(a.month, a.day) for a, _ in p[1:]], [(4, 2), (8, 5), (11, 26)])            # within a day of the published start dates
        share = sum((b - a).days + 1 for a, b in astro.periods(2010, 2019)) / 3652
        self.assertTrue(0.15 < share < 0.23)                                                          # about one day in five

    def test_the_ledger_ranks_a_real_signal_above_a_control_and_flags_constants(self):
        r = np.random.default_rng(2)
        n = 12000
        sig = (r.random(n) < 0.4).astype(np.float32)
        y = (r.random(n) < risk._sig(-2.5 + 1.3 * sig)).astype(np.int8)
        blocks = {"signal": ("protocol", True, sig[:, None]), "noise": ("control", True, (r.random((n, 3)) < 0.5).astype(np.float32)),
                  "constant": ("trend", True, np.ones((n, 1), np.float32))}
        train = np.arange(n) < 8000
        out = sim.source_ledger(blocks, y, train, ~train, {"all": np.ones(n, bool)}, boot=60, log=lambda *_: None)
        rows = {x["family"]: x for x in out["groups"]["all"]["rows"]}
        self.assertGreater(rows["signal"]["alone_auroc"], 0.6)
        self.assertGreater(rows["signal"]["unique_gain"], 0.05)
        self.assertLess(abs(rows["noise"]["alone_auroc"] - 0.5), 0.04)
        self.assertTrue(rows["constant"]["constant_in_test"])


if __name__ == "__main__":
    unittest.main()
