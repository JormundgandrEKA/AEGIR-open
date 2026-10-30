"""GPU backend tests. They run only where PyTorch is installed (use the AutoRAN virtual environment); CUDA is used if present."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import numpy as np
    import torch
    HAVE = True
except ImportError:
    HAVE = False

if HAVE:
    from autoran import gpu, stats


@unittest.skipUnless(HAVE, "PyTorch not installed in this Python")
class TestGpu(unittest.TestCase):
    def synthetic(self, n=6000, d=12, seed=1):
        rng = np.random.default_rng(seed)
        X = rng.normal(size=(n, d)).astype("float32")
        z = 1.2 * X[:, 0] - 0.8 * X[:, 1] + 0.3 * rng.normal(size=n) - 2.2
        y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype("float32")
        split = np.array(["train"] * int(n * .7) + ["dev"] * int(n * .1) + ["test"] * (n - int(n * .7) - int(n * .1)))
        return X, y, split

    def test_linear_and_mlp_learn_a_known_signal(self):
        X, y, split = self.synthetic()
        dev = gpu.device("auto")
        for hidden in (0, 64):
            net = gpu.Net("t", hidden=hidden, text=False, dev=dev).fit(X, y, split, T=X.shape[1], epochs=60, batch=256)
            p = net.predict(X)
            te = split == "test"
            a = stats.auroc(y[te].astype(int).tolist(), p[te].tolist())
            self.assertGreater(a, 0.78, f"hidden={hidden} auroc={a:.3f}")
            self.assertTrue(((p >= 0) & (p <= 1)).all())

    def test_gpu_bootstrap_matches_the_cpu_bootstrap(self):
        rnd = random.Random(3)
        y = [1 if rnd.random() < 0.08 else 0 for _ in range(6000)]
        s = [rnd.random() + 0.45 * v for v in y]
        g = gpu.bootstrap_gpu(y, s, resamples=400, seed=5)
        c = stats.bootstrap_ci(y, s, resamples=400, seed=5)
        for k in ("auroc", "auprc"):
            for i in (0, 1):
                self.assertAlmostEqual(g[k][i], c[k][i], delta=0.02)

    def test_bootstrap_is_seeded(self):
        y = [0, 1] * 500
        s = [0.1, 0.9] * 250 + [0.9, 0.1] * 250
        self.assertEqual(gpu.bootstrap_gpu(y, s, 100, seed=2), gpu.bootstrap_gpu(y, s, 100, seed=2))

    def test_split_features_separates_text_hash_from_tabular(self):
        tab, txt = gpu._split_features({"n_incl": 1.0, "phase=PHASE2": 1.0, "w17": 0.5, "w2065": 0.5})
        self.assertEqual(set(tab), {"n_incl", "phase=PHASE2"})
        self.assertEqual(set(txt), {17, 2065 % gpu.TEXT_DIM})

    def test_device_choice(self):
        self.assertEqual(gpu.device("cpu").type, "cpu")


if __name__ == "__main__":
    unittest.main()
