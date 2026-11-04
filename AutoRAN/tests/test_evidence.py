"""Evidence summary and the factor combiner. Synthetic workbenches only; nothing is read from the registry."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import autoran  # noqa: E402,F401
from autoran import evidence, risk, server  # noqa: E402
from autoran.core import Paths  # noqa: E402


def make_root():
    root = Path(tempfile.mkdtemp())
    d = root / "data" / "derived" / "sim"
    d.mkdir(parents=True)
    r = np.random.default_rng(1)
    ntr, nte = 6000, 3000
    z = lambda n: np.column_stack([r.normal(size=n), r.normal(size=n), r.normal(size=n), np.zeros(n)])      # three families and one constant
    Ztr, Zte = z(ntr), z(nte)
    link = lambda Z: -3 + 1.2 * Z[:, 0] + 0.5 * Z[:, 1]
    ytr = (r.random(ntr) < risk._sig(link(Ztr))).astype(np.int8)
    yte = (r.random(nte) < risk._sig(link(Zte))).astype(np.int8)
    np.savez_compressed(d / "workbench_registry_20260101T000000Z.npz", fam=np.array(["signal", "weaker", "noise", "constant"]), kind=np.array(["protocol", "who", "control", "trend"]),
                        ytr=ytr, yte=yte, pros_te=(r.random(nte) < 0.5), Ztr=Ztr.astype(np.float32), Zte=Zte.astype(np.float32), meta=np.array(json.dumps({"train": "t", "test": "u"})))
    n = 2500
    Z = np.column_stack([r.normal(size=n), r.normal(size=n)])
    base = r.normal(size=n)
    y = (r.random(n) < risk._sig(-3 + 0.8 * base + 0.9 * Z[:, 0])).astype(np.int8)
    np.savez_compressed(d / "workbench_protocol_20260101T000000Z.npz", fam=np.array(["doc signal", "doc noise"]), kind=np.array(["protocol", "control"]), y=y, base=base, Z=Z.astype(np.float32),
                        pros=(r.random(n) < 0.5), meta=np.array(json.dumps({"cohort": "x"})))
    return root


class TestEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = Paths(make_root())

    def test_a_real_family_beats_noise_and_a_combination_beats_either(self):
        a = evidence.combine(self.paths, "registry", ["signal"], "all")
        b = evidence.combine(self.paths, "registry", ["noise"], "all")
        c = evidence.combine(self.paths, "registry", ["signal", "weaker"], "all")
        self.assertGreater(a["auroc"], 0.65)
        self.assertLess(abs(b["auroc"] - 0.5), 0.06)
        self.assertGreater(c["auroc"], a["auroc"] - 0.005)
        self.assertEqual(c["reference"]["best_single_family"], "signal")
        self.assertEqual(len(c["at_budget"]), 4)
        self.assertGreater(c["at_budget"][1]["lift"], 1.5)

    def test_prospective_subset_is_smaller_and_curves_are_well_formed(self):
        p = evidence.combine(self.paths, "registry", ["signal"], "prospective")
        a = evidence.combine(self.paths, "registry", ["signal"], "all")
        self.assertLess(p["n"], a["n"])
        self.assertEqual(p["roc"][0], [0.0, 0.0])
        self.assertTrue(all(0 <= x <= 1 and 0 <= y <= 1 for x, y in p["roc"]))
        self.assertTrue(all(0 <= x <= 1 and 0 <= y <= 1 for x, y in p["pr"]))
        self.assertEqual(set(p["weights"]), {"signal"})
        json.dumps(p)                                                      # the answer must be valid JSON

    def test_protocol_setting_uses_the_baseline_and_can_leave_it_out(self):
        with_base = evidence.combine(self.paths, "protocol", ["doc signal"], "all", True)
        without = evidence.combine(self.paths, "protocol", ["doc signal"], "all", False)
        self.assertIn("registry baseline", with_base["weights"])
        self.assertNotIn("registry baseline", without["weights"])
        self.assertGreater(with_base["auroc"], without["auroc"])
        self.assertEqual(with_base["reference"]["baseline_only_auroc"] > 0.5, True)

    def test_bad_requests_are_refused(self):
        with self.assertRaises(ValueError):
            evidence.combine(self.paths, "registry", ["nonsense"], "all")
        with self.assertRaises(ValueError):
            evidence.combine(self.paths, "registry", [], "all")
        with self.assertRaises(ValueError):
            evidence.combine(Paths(tempfile.mkdtemp()), "registry", ["signal"], "all")

    def test_correlation_has_no_nan_for_a_constant_family(self):
        c = evidence.correlation(self.paths, "registry")
        self.assertEqual(c["families"][3], "constant")
        self.assertTrue(all(v is None for v in c["matrix"][3]))
        json.loads(json.dumps(c))

    def test_summary_works_on_an_empty_folder_and_lists_workbenches(self):
        e = evidence.summary(Paths(tempfile.mkdtemp()))
        self.assertFalse(any(e["parts"].values()))
        self.assertEqual(e["headline"]["cards"], [])
        s = evidence.summary(self.paths)
        self.assertEqual({k for k in s["workbench"]}, {"registry", "protocol"})
        self.assertEqual([f["name"] for f in s["workbench"]["registry"]["families"]], ["signal", "weaker", "noise", "constant"])
        self.assertTrue(any(g["gate"] == "G4" for g in s["gates"]))

    def test_routes(self):
        class S:
            pass
        s = S()
        s.paths = self.paths
        code, e = server.dispatch(s, "GET", "/api/evidence", {}, None)
        self.assertEqual(code, 200)
        code, r = server.dispatch(s, "POST", "/api/evidence/combine", {}, {"setting": "registry", "families": ["signal", "weaker"], "subset": "all"})
        self.assertEqual(code, 200)
        self.assertGreater(r["auroc"], 0.6)
        code, r = server.dispatch(s, "POST", "/api/evidence/combine", {}, {"setting": "registry", "families": ["nope"], "subset": "all"})
        self.assertEqual(code, 400)


if __name__ == "__main__":
    unittest.main()
