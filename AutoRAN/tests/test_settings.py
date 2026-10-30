import os
import tempfile
import unittest
from pathlib import Path


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["AUTORAN_SETTINGS"] = str(self.tmp / "s" / "settings.json")
        from autoran import settings
        self.s = settings
        settings._cache["mtime"] = None

    def tearDown(self):
        os.environ.pop("AUTORAN_SETTINGS", None)
        for k in ("NCBI_API_KEY", "NCBI_EMAIL", "AUTORAN_ENV_SET_NCBI_API_KEY", "AUTORAN_ENV_SET_NCBI_EMAIL"):
            os.environ.pop(k, None)

    def test_roundtrip_and_secret_never_public(self):
        out = self.s.save({"contact_email": "a@b.org", "hf_token": "hf_secret123", "workspace": str(self.tmp / "ws")})
        self.assertEqual(out["contact_email"], "a@b.org")
        self.assertEqual(out["hf_token"], {"set": True})
        self.assertNotIn("hf_secret123", (self.tmp / "s" / "settings.json").read_text())
        self.assertEqual(self.s.get("hf_token"), "hf_secret123")
        self.assertIn("a@b.org", self.s.user_agent())

    def test_clear_and_validation(self):
        self.s.save({"contact_email": "a@b.org"})
        self.assertEqual(self.s.save({"contact_email": ""})["contact_email"], "")
        for bad in ({"contact_email": "nope"}, {"gpu_site": str(self.tmp)}, {"hf_token": "has space"}, {"bogus": "x"}):
            with self.assertRaises(ValueError):
                self.s.save(bad)

    def test_env_for_ran_client(self):
        self.s.save({"ncbi_api_key": "k123", "contact_email": "a@b.org"})
        self.assertEqual(os.environ["NCBI_API_KEY"], "k123")
        self.assertEqual(os.environ["NCBI_EMAIL"], "a@b.org")

    def test_seed_workspace_does_not_overwrite(self):
        code = self.tmp / "code"; (code / "config").mkdir(parents=True)
        (code / "config" / "x.json").write_text("{}")
        ws = self.tmp / "ws"
        self.s.seed_workspace(ws, code)
        (ws / "config" / "x.json").write_text('{"mine":1}')
        self.s.seed_workspace(ws, code)
        self.assertEqual((ws / "config" / "x.json").read_text(), '{"mine":1}')


if __name__ == "__main__":
    unittest.main()
