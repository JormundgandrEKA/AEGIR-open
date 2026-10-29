"""Paths, config, append-only storage and provenance sidecars."""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.1.0"
NCT_RE = re.compile(r"NCT\d{8}")
_REDACT_RE = re.compile(r"([?&])(api_key|email)=[^&\s]*")
_SECRET_KEYS = ("api_key", "email")


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_root():
    """AEGIR_ROOT, else the folder holding RAN.exe (frozen build) or the source checkout."""
    env = os.environ.get("AEGIR_ROOT")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve().parent
        return exe if (exe / "config").is_dir() or not (Path.cwd() / "config").is_dir() else Path.cwd()
    return Path(__file__).resolve().parents[2]


def bundled(name):
    """Default config shipped inside the frozen executable (used when the folder has none)."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "defaults" / name if base else None


def demo_batch_path():
    """The demo batch: inside RAN.exe, or demo/ in the repository. None if it is not there."""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parents[2]
    p = root / "demo" / "ran-demo-batch.json"
    return p if p.is_file() else None


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def redact_url(url):
    return _REDACT_RE.sub(r"\1\2=REDACTED", url)


def redact_params(params):
    return {k: v for k, v in (params or {}).items() if k not in _SECRET_KEYS}


def scrub(text, secrets=()):
    text = redact_url(str(text))
    for s in secrets:
        if s:
            text = text.replace(s, "REDACTED")
    return text


def read_jsonl(path):
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except FileNotFoundError:
        pass
    return out


def latest_by(records, key):
    """Latest line per key (readers take the last line; nothing is rewritten)."""
    out = {}
    for r in records:
        if key in r:
            out[r[key]] = r
    return out


class Store:
    """All data writes go through here. Files are only ever created, never replaced."""

    def __init__(self, root, scratch=False, dry_run=False):
        self.root = Path(root)
        self.scratch = scratch
        self.dry_run = dry_run
        self.data = self.root / "data"
        self.base = self.data / "scratch" if scratch else self.data
        self.files_written = 0

    def raw_dir(self, *parts):
        return self.base.joinpath("raw", *parts)

    def derived_dir(self):
        return self.base / "derived"

    def cat_path(self, name):
        return self.base / "catalogue" / name

    def rel(self, path):
        try:
            return Path(path).relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def write_new(self, path, data):
        """Create `path` (adding _2, _3 ... if it exists). Never overwrites."""
        path = Path(path)
        if self.dry_run:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        n = 1
        while True:
            p = path if n == 1 else path.with_name(f"{path.stem}_{n}{path.suffix}")
            try:
                with open(p, "xb") as f:
                    f.write(data)
                self.files_written += 1
                return p
            except FileExistsError:
                n += 1

    def write_json_new(self, path, obj):
        return self.write_new(path, (json.dumps(obj, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))

    def save_raw(self, parts, name, body, meta):
        """Write a raw file plus `<file>.meta.json` provenance sidecar. Returns the path."""
        path = self.write_new(self.raw_dir(*parts) / name, body)
        meta = dict(meta)
        meta.setdefault("sha256", sha256(body))
        meta.setdefault("bytes", len(body))
        meta.setdefault("tool_version", VERSION)
        meta.setdefault("retrieved_at", iso_now())
        self.write_json_new(path.with_name(path.name + ".meta.json"), meta)
        return path

    def append(self, catalogue, record):
        if self.dry_run:
            return
        path = self.cat_path(catalogue)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def records(self, catalogue):
        return read_jsonl(self.cat_path(catalogue))

    def latest(self, catalogue, key):
        return latest_by(self.records(catalogue), key)

    def latest_file(self, parts, suffix=None):
        """Newest non-sidecar file in a raw directory (stamps sort chronologically)."""
        d = self.raw_dir(*parts)
        if not d.is_dir():
            return None
        files = sorted(p for p in d.iterdir()
                       if p.is_file() and not p.name.endswith(".meta.json")
                       and (suffix is None or p.name.endswith(suffix)))
        return files[-1] if files else None


def delimit(label, text):
    """Fetched text is untrusted data: wrap it so a reader never mistakes it for instructions."""
    return f"<<<UNTRUSTED FETCHED TEXT: {label}>>>\n{text}\n<<<END UNTRUSTED FETCHED TEXT>>>"
