"""Tests for the desktop-app layer: routing, link whitelist, plot plug-ins, job rules, root detection. Offline; no trial data needed."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from autoran import jobs, plots, server  # noqa: E402


class Stub:
    """Just enough of State for the routes under test."""
    def __init__(self, root):
        self.jobs = jobs.Jobs()
        self.metrics = {"scorers": {}}
        self.ctx = type("C", (), {"root": Path(root)})()
        self.cfg, self.labeller = {"sources": {}, "scope": {}, "grade_floor": "B-"}, "t"


class TestDispatch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.st = Stub(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unknown_routes_are_404(self):
        self.assertEqual(server.dispatch(self.st, "GET", "/api/nope", {}, None)[0], 404)
        self.assertEqual(server.dispatch(self.st, "POST", "/api/nope", {}, {})[0], 404)

    def test_only_clinicaltrials_links_open(self):
        for bad in ("https://evil.example/x", "http://clinicaltrials.gov/study/NCT1", "file:///c:/windows/system32", "javascript:alert(1)", ""):
            self.assertEqual(server.dispatch(self.st, "POST", "/api/open", {}, {"url": bad})[0], 400, bad)

    def test_jobs_listing_and_unknown_stage(self):
        code, obj = server.dispatch(self.st, "GET", "/api/jobs", {}, None)
        self.assertEqual(code, 200)
        self.assertIn("label", obj["stages"])
        self.assertEqual(server.dispatch(self.st, "POST", "/api/run", {}, {"stage": "rm -rf"})[0], 400)

    def test_gpu_info_never_raises(self):
        code, obj = server.dispatch(self.st, "GET", "/api/gpu", {}, None)
        self.assertEqual(code, 200)
        self.assertIn("cuda_available", obj)


class TestPlugins(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "plugins").mkdir()
        (self.tmp / "config").mkdir()
        self.before = dict(plots.REGISTRY)

    def tearDown(self):
        plots.REGISTRY.clear()
        plots.REGISTRY.update(self.before)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_plugin_is_discovered_and_rendered(self):
        (self.tmp / "plugins" / "demo.py").write_text(
            "from autoran.plots import plot\n"
            "@plot('Demo plot', 'a test plot', needs_frame=False)\n"
            "def demo(ctx):\n"
            "    import matplotlib.pyplot as plt\n"
            "    fig, ax = plt.subplots(figsize=(3, 2)); ax.plot([1, 2, 3]); return fig\n", encoding="utf-8")
        d = plots.listing(self.tmp)
        names = {p["name"]: p for p in d["plots"]}
        self.assertIn("Demo plot", names)
        self.assertFalse(names["Demo plot"]["builtin"])
        self.assertEqual(d["plugin_errors"], [])
        r = plots.render(self.tmp, {}, "Demo plot")
        self.assertNotIn("error", r)
        import base64
        self.assertTrue(base64.b64decode(r["png"]).startswith(b"\x89PNG"))
        self.assertTrue(Path(r["saved"]).is_file())

    def test_broken_plugin_is_reported_not_fatal(self):
        (self.tmp / "plugins" / "bad.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
        (self.tmp / "plugins" / "worse.py").write_text("from autoran.plots import plot\n@plot('Fails')\ndef f(ctx):\n    raise ValueError('nope')\n", encoding="utf-8")
        d = plots.listing(self.tmp)
        self.assertTrue(any("bad.py" in e for e in d["plugin_errors"]))
        r = plots.render(self.tmp, {}, "Fails")
        self.assertIn("ValueError", r["error"])

    def test_builtin_plots_present_and_unknown_rejected(self):
        names = {p["name"] for p in plots.listing(self.tmp)["plots"]}
        self.assertIn("Scorers: AUROC with intervals", names)
        self.assertIn("AUROC bootstrap distribution (computed on the GPU)", names)
        with self.assertRaises(ValueError):
            plots.render(self.tmp, {}, "no such plot")


class TestJobsAndRoot(unittest.TestCase):
    def test_only_one_job_at_a_time(self):
        j = jobs.Jobs()
        j.items.append({"id": 1, "stage": "label", "device": "cpu", "state": "running", "log": [], "started": "", "finished": None, "seconds": None, "summary": None})
        with self.assertRaises(ValueError):
            j.start("metrics")
        self.assertTrue(j.running())

    def test_every_stage_is_a_known_command(self):
        from autoran.cli import build_parser
        known = set(build_parser()._subparsers._group_actions[0].choices)
        for stage in jobs.STAGES:
            self.assertIn({"fetch-delta": "fetch", "fetch-full": "fetch", "run-all": "run"}.get(stage, stage), known, stage)

    def test_frozen_root_search_goes_upward(self):
        from autoran import core
        self.assertTrue((core.ROOT / "config" / "autoran.json").is_file())

class TestSettingsRoute(unittest.TestCase):
    def test_settings_route_hides_secrets(self):
        import os, tempfile
        from autoran import server, settings
        os.environ["AUTORAN_SETTINGS"] = os.path.join(tempfile.mkdtemp(), "s.json")
        try:
            code, out = server.dispatch(None, "POST", "/api/settings", {}, {"hf_token": "hf_abc", "contact_email": "x@y.org"})
            self.assertEqual(code, 200)
            self.assertEqual(out["hf_token"], {"set": True})
            code, out = server.dispatch(None, "GET", "/api/settings", {}, None)
            self.assertNotIn("hf_abc", str(out))
            code, out = server.dispatch(None, "POST", "/api/settings", {}, {"contact_email": "bad"})
            self.assertEqual(code, 400)
        finally:
            os.environ.pop("AUTORAN_SETTINGS", None)
            os.environ.pop("NCBI_EMAIL", None)
            os.environ.pop("AUTORAN_ENV_SET_NCBI_EMAIL", None)



if __name__ == "__main__":
    unittest.main()
