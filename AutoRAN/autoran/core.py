"""Paths, config, the RAN context, gzip-aware downloads, small shared helpers."""
import gzip
import hashlib
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import settings
from . import _shared  # noqa: F401  (makes aegir_core importable)
from aegir_core.context import Ctx
from aegir_core.core import iso_now, read_jsonl, sha256, utc_stamp  # noqa: F401

from . import __version__

def _find_code_root():
    """The folder that holds config/ and plugins/ as shipped."""
    if getattr(sys, "frozen", False):                       # AutoRAN.exe: look upward from the exe for config/autoran.json
        here = Path(sys.executable).resolve().parent
        for c in [here, *list(here.parents)[:4]]:
            if (c / "config" / "autoran.json").is_file():
                return c
        return Path.cwd()
    return Path(__file__).resolve().parent.parent


def _find_root():
    """Where data/ and state/ live: AUTORAN_ROOT, else the workspace chosen on the Settings page, else the AutoRAN folder."""
    env = os.environ.get("AUTORAN_ROOT")
    if env:
        return Path(env)
    ws = settings.get("workspace")
    if ws:
        try:
            settings.seed_workspace(ws, CODE_ROOT)
            return Path(ws)
        except OSError:
            pass
    return CODE_ROOT


CODE_ROOT = _find_code_root()
ROOT = _find_root()


def _torch_pack():
    """The small exe has no PyTorch inside. If a folder with torch/ is available, make it importable: Settings > gpu_site, then gpu_pack/ beside
    the exe or in the workspace. (pip install --target gpu_pack torch --index-url https://download.pytorch.org/whl/cu128). No effect when torch is bundled or absent."""
    import importlib.util
    if importlib.util.find_spec("torch") is not None:
        return
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else CODE_ROOT
    for c in (settings.get("gpu_site"), exe_dir / "gpu_pack", CODE_ROOT / "gpu_pack", ROOT / "gpu_pack"):
        if c and (Path(c) / "torch" / "__init__.py").is_file():
            sys.path.append(str(c))
            return


_torch_pack()
NL = chr(10)


def load_cfg(root=None):
    root = Path(root or ROOT)
    cfg = json.loads((root / "config" / "autoran.json").read_text(encoding="utf-8"))
    cfg["sources"] = json.loads((root / "config" / "sources.json").read_text(encoding="utf-8"))
    return cfg


def make_ctx(root=None, **kw):
    """A RAN context rooted in the AutoRAN folder (its own data/, state/ and config/)."""
    settings.apply_env()
    return Ctx(Path(root or ROOT), **kw)


class Paths:
    def __init__(self, root=None):
        self.root = Path(root or ROOT)
        self.data = self.root / "data"
        self.derived = self.data / "derived" / "autoran"
        self.catalogue = self.data / "catalogue"
        self.raw = self.data / "raw"

    def ensure(self):
        for p in (self.derived, self.catalogue):
            p.mkdir(parents=True, exist_ok=True)
        return self

    def latest(self, pattern):
        files = sorted(self.derived.glob(pattern))
        return files[-1] if files else None


# -- downloads: ask for gzip, hand RAN's client the decompressed body -----------------

class _Resp:
    def __init__(self, raw):
        self._raw = raw
        self.status = raw.status
        self.headers = raw.headers
        enc = (raw.headers.get("Content-Encoding") or "").lower()
        body = raw.read()
        self._body = gzip.decompress(body) if enc == "gzip" else body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._raw.close()


_installed = False


def install_gzip():
    """RAN's client sends no Accept-Encoding. Wrapping urlopen here (this process only) cuts a 3.4 MB page to about 0.8 MB."""
    global _installed
    if _installed:
        return
    real = urllib.request.urlopen

    def urlopen(req, *a, **k):
        if isinstance(req, urllib.request.Request):
            if not req.has_header("Accept-encoding"):
                req.add_header("Accept-Encoding", "gzip")
            req.add_header("User-Agent", settings.user_agent())          # replaces RAN's; adds the contact email when one is set
            tok = settings.get("hf_token")
            if tok and (urllib.parse.urlsplit(req.full_url).hostname or "").endswith("huggingface.co"):
                req.add_header("Authorization", "Bearer " + tok)
        return _Resp(real(req, *a, **k))
    urllib.request.urlopen = urlopen
    _installed = True


# -- dates ------------------------------------------------------------------------

def norm_date(s):
    """YYYY-MM or YYYY-MM-DD to YYYY-MM-DD (a month alone becomes its first day); '' when missing."""
    s = (s or "")[:10]
    return s + "-01" if len(s) == 7 else (s if len(s) == 10 else "")


def year_of(s):
    s = norm_date(s)
    return int(s[:4]) if s else None


def stable_hash(text, seed=""):
    """Deterministic float in [0, 1) from a string (used for frozen splits)."""
    h = hashlib.sha256((seed + "|" + text).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def write_jsonl(path, rows):
    """Write a NEW jsonl file (never replaces one)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "xb") as f:
        for r in rows:
            f.write((json.dumps(r, ensure_ascii=True, separators=(",", ":")) + NL).encode("utf-8"))
            n += 1
    return n


def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def read_gz_json(path):
    with gzip.open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def summary_line(command, ok=True, **kw):
    print(json.dumps({"command": f"autoran {command}", "ok": ok, "version": __version__, **kw}, ensure_ascii=False))
