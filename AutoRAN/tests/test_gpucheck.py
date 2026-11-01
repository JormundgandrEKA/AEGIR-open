"""The GPU check and the PyTorch installer, tested with fake cards, fake Pythons and a fake pip. Nothing is downloaded or installed."""
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import autoran  # noqa: E402,F401  (puts ../shared on the path)
from autoran import gpucheck, server  # noqa: E402

TAG = gpucheck.BUNDLED_TAG
CARD = {"gpu": "NVIDIA GeForce RTX 4070", "driver": "595.59", "memory_mb": 12282, "max_cuda": "13.2"}


def probe(tag=TAG, torch=None, cuda=False, pip=True, exe="C:\\Py\\python.exe", site="C:\\Py\\Lib\\site-packages"):
    p = {"python": f"{tag[2]}.{tag[3:]}.1", "tag": tag, "exe": exe, "has_pip": pip, "numpy": "2.5.0", "torch": torch}
    if torch:
        p.update(cuda_build="12.8", cuda_ok=cuda, site=site)
    return p


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["AEGIR_STATE_DIR"] = str(self.tmp / "AEGIR" / "state")
        gpucheck.INSTALL.update(state="idle", log=[], progress=0.0, message="", started=None, finished=None)
        gpucheck.SCAN.update(state="idle", started=None)


class TestVerdict(Base):
    def test_reads_the_card(self):
        def fake(args, **kw):
            out = "NVIDIA GeForce RTX 4070, 595.59, 12282\n" if "--query-gpu=name,driver_version,memory.total" in args else "| NVIDIA-SMI 595.59  Driver Version: 595.59  CUDA Version: 13.2 |\n"
            return types.SimpleNamespace(stdout=out, returncode=0)
        with mock.patch.object(gpucheck, "RUN", fake), mock.patch("shutil.which", return_value="nvidia-smi"):
            self.assertEqual(gpucheck.smi(), CARD)
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(gpucheck.smi()["gpu"])

    def test_states(self):
        d = gpucheck.decide
        self.assertEqual(d({"gpu": None}, [probe(torch="2.1", cuda=False)])["state"], "no_gpu")
        self.assertEqual(d(CARD, [], in_process={"torch": "2.11", "cuda_ok": True})["state"], "ready")
        found = d(CARD, [probe(torch="2.11.0+cu128", cuda=True, site="S1"), probe(torch="2.14.1+cu126", cuda=True, site="S2")])
        self.assertEqual((found["state"], found["site"]), ("found", "S2"))            # the newer one
        self.assertEqual(d(CARD, [probe(torch="2.11.0", cuda=False)])["state"], "incompatible")
        other = d(CARD, [probe(tag="cp314", torch="2.11.0", cuda=True)])
        self.assertEqual(other["state"], "incompatible")
        self.assertIn("needs a build for Python", other["text"])
        nf = d(CARD, [probe()])
        self.assertEqual((nf["state"], nf["can_install"]), ("not_found", True))
        self.assertFalse(d(CARD, [probe(pip=False)])["can_install"])


class TestInstallPlan(Base):
    def test_picks_the_cuda_build_the_driver_supports(self):
        self.assertEqual(gpucheck.indexes_for("13.2"), ["cu130", "cu128", "cu126"])
        self.assertEqual(gpucheck.indexes_for("12.6"), ["cu126", "cu124", "cu121"])
        self.assertEqual(gpucheck.indexes_for("11.9"), ["cu118"])
        self.assertEqual(gpucheck.indexes_for(None), ["cu126"])

    def test_commands_and_refusals(self):
        with mock.patch("shutil.disk_usage", return_value=types.SimpleNamespace(free=50 * 2 ** 30)):
            plan = gpucheck.install_plan(CARD, [probe()])
            self.assertTrue(plan["ok"])
            step1, step2 = plan["commands"][0]["cmds"]
            self.assertIn("--target", step1)
            self.assertEqual(step1[step1.index("--index-url") + 1], "https://download.pytorch.org/whl/cu130")
            self.assertNotIn("--extra-index-url", step1)                              # PyPI must not be able to supply a CPU-only torch
            self.assertIn("--no-deps", step1)
            self.assertNotIn("--index-url", step2)                                    # the small dependencies come from PyPI
            self.assertTrue(any(x.startswith("sympy") for x in step2))
            self.assertNotIn("--python-version", step1)
            self.assertTrue(plan["target"].endswith("gpu_pack"))
            other = gpucheck.install_plan(CARD, [probe(tag="cp312")])               # pip from another Python can still fetch our wheels
            c2 = other["commands"][0]["cmds"][0]
            self.assertEqual(c2[c2.index("--python-version") + 1], f"{TAG[2]}.{TAG[3:]}")
            self.assertEqual(c2[c2.index("--progress-bar") + 1], "off")               # the extra flags did not split an option
            self.assertIn("--platform", c2)
            self.assertFalse(gpucheck.install_plan({"gpu": None}, [probe()])["ok"])
            self.assertFalse(gpucheck.install_plan(CARD, [probe(pip=False)])["ok"])
        with mock.patch("shutil.disk_usage", return_value=types.SimpleNamespace(free=2 * 2 ** 30)):
            self.assertIn("Not enough free disk space", gpucheck.install_plan(CARD, [probe()])["why"])

    def test_install_tries_the_next_build_and_activates(self):
        plan = {"ok": True, "target": str(self.tmp / "gp"), "expected_gb": 3.0, "free_gb": 99, "python": "x", "python_version": "3.13.1",
                "commands": [{"index": "cu130", "cmds": [["a"], ["a2"]]}, {"index": "cu128", "cmds": [["b"], ["b2"]]}]}
        calls = []

        class FakePopen:
            def __init__(self, cmd, **kw):
                calls.append(cmd[0])
                self.stdout = iter([f"Collecting torch ({cmd[0]})\n"])
                self.rc = 1 if cmd[0] == "a" else 0

            def wait(self):
                return self.rc
        with mock.patch.object(gpucheck.subprocess, "Popen", FakePopen), mock.patch.object(gpucheck, "activate", return_value={"torch": "2.11.0", "cuda_ok": True}), \
                mock.patch.object(gpucheck, "scan_cache_refresh"):
            res = gpucheck.run_install(plan)
        self.assertEqual(calls, ["a", "b", "b2"])                                 # a failed at step 1, so a2 never ran
        self.assertEqual(res["state"], "done")
        self.assertIn("found your GPU", res["message"])
        self.assertTrue(any("cu130 build failed" in l for l in res["log"]))

    def test_install_failure_is_reported(self):
        plan = {"ok": True, "target": str(self.tmp / "gp"), "expected_gb": 3.0, "free_gb": 99, "python": "x", "python_version": "3",
                "commands": [{"index": "cu126", "cmds": [["a"]]}]}

        class Bad:
            def __init__(self, cmd, **kw):
                self.stdout = iter(["ERROR: no matching distribution\n"])

            def wait(self):
                return 1
        with mock.patch.object(gpucheck.subprocess, "Popen", Bad):
            res = gpucheck.run_install(plan)
        self.assertEqual(res["state"], "failed")


class TestActivateAndCache(Base):
    def test_activate_adds_a_folder_only_when_torch_is_in_it(self):
        site = self.tmp / "site"
        (site / "torch").mkdir(parents=True)
        (site / "torch" / "__init__.py").write_text("__version__ = '9.9.9'"+chr(10), encoding="utf-8")
        empty = self.tmp / "empty"
        empty.mkdir()
        before = list(sys.path)
        try:
            with mock.patch.object(gpucheck, "in_process_info", return_value={"torch": "x", "cuda_ok": True}) as seen:
                gpucheck.activate(str(empty))
                self.assertNotIn(str(empty), sys.path)
                info = gpucheck.activate(str(site))
                self.assertIn(str(site), sys.path)
                self.assertEqual(info["torch"], "x")
                self.assertEqual(seen.call_count, 2)
        finally:
            sys.path[:] = before

    def test_cache_freshness(self):
        self.assertFalse(gpucheck.cache_is_fresh())
        gpucheck.cache_path().parent.mkdir(parents=True, exist_ok=True)
        gpucheck.cache_path().write_text(json.dumps({"ts": time.time(), "verdict": {"state": "not_found"}}), encoding="utf-8")
        self.assertTrue(gpucheck.cache_is_fresh())
        gpucheck.cache_path().write_text(json.dumps({"ts": time.time() - 8 * 86400}), encoding="utf-8")
        self.assertFalse(gpucheck.cache_is_fresh())

    def test_scan_writes_the_verdict(self):
        with mock.patch.object(gpucheck, "smi", return_value=CARD), mock.patch.object(gpucheck, "candidates", return_value=["p1", "p2"]), \
                mock.patch.object(gpucheck, "probe_python", side_effect=[probe(), probe(tag="cp312", torch="2.0", cuda=True, exe="C:\\Q\\python.exe")]):
            out = gpucheck.scan()
        self.assertEqual(out["verdict"]["state"], "incompatible")
        self.assertEqual(gpucheck.load_cache()["verdict"]["state"], "incompatible")


class TestRoutes(Base):
    def test_check_and_dry_run_install(self):
        code, st = server.dispatch(None, "GET", "/api/gpu/check", {}, None)
        self.assertEqual(code, 200)
        self.assertIn("install", st)
        gpucheck.cache_path().parent.mkdir(parents=True, exist_ok=True)
        gpucheck.cache_path().write_text(json.dumps({"ts": time.time(), "smi": CARD, "pythons": [probe()], "verdict": gpucheck.decide(CARD, [probe()])}), encoding="utf-8")
        with mock.patch("shutil.disk_usage", return_value=types.SimpleNamespace(free=50 * 2 ** 30)):
            code, r = server.dispatch(None, "POST", "/api/gpu/install", {}, {"dry_run": True})
        self.assertEqual(code, 200)
        self.assertTrue(r["plan"]["ok"])
        self.assertFalse(r["started"])
        self.assertEqual(gpucheck.INSTALL["state"], "idle")                       # a dry run starts nothing


if __name__ == "__main__":
    unittest.main()
