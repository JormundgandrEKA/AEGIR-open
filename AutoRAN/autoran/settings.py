"""Per-user settings, kept outside the project folder so they are never committed or shared.

Windows: %APPDATA%\\AutoRAN\\settings.json     other systems: ~/.config/autoran/settings.json     (override with AUTORAN_SETTINGS)

Fields (all optional):
  workspace      folder that holds data/ and state/ (and a copy of config/). Default: the AutoRAN folder. Applies after a restart.
  aegir_tool     folder that contains aegir_ran/ (RAN). Default: looked for next to AutoRAN. Applies after a restart.
  history_dir    folder of RAN's browser-collected trial histories (optional input; makes a few more inputs "clean").
  contact_email  added to the User-Agent of requests, so a registry operator can reach you. Never needed to run AutoRAN.
  hf_token       Hugging Face access token. Optional: raises the Open Targets download's rate limit.
  ncbi_api_key   NCBI API key. Optional and not used by AutoRAN's own fetches (ClinicalTrials.gov needs no key); passed on to RAN's NCBI client.

Secrets (tokens and keys) are stored encrypted for this Windows user (DPAPI) and are never sent back to the page; the page only learns whether one is set.
This module imports nothing from the rest of AutoRAN, so it can run before anything else.
"""
import base64
import json
import os
import sys
from pathlib import Path

FIELDS = ("workspace", "aegir_tool", "history_dir", "contact_email", "hf_token", "ncbi_api_key")
SECRETS = ("hf_token", "ncbi_api_key")
PATHS = ("workspace", "aegir_tool", "history_dir")


def path():
    env = os.environ.get("AUTORAN_SETTINGS")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "AutoRAN" / "settings.json"
    return Path.home() / ".config" / "autoran" / "settings.json"


# -- secret storage ---------------------------------------------------------------

def _dpapi(data, protect):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("n", wintypes.DWORD), ("p", ctypes.POINTER(ctypes.c_char))]

    src = Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_char)))
    out = Blob()
    f = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not f(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.p, out.n)
    finally:
        ctypes.windll.kernel32.LocalFree(out.p)


def _seal(text):
    raw = text.encode("utf-8")
    if os.name == "nt":
        try:
            return "dpapi:" + base64.b64encode(_dpapi(raw, True)).decode()
        except Exception:
            pass
    return "plain:" + base64.b64encode(raw).decode()      # file is user-only (chmod 600) where the system allows it


def _open(blob):
    try:
        kind, _, b = (blob or "").partition(":")
        raw = base64.b64decode(b)
        return (_dpapi(raw, False) if kind == "dpapi" else raw).decode("utf-8")
    except Exception:
        return ""


# -- read / write -----------------------------------------------------------------

_cache = {"mtime": None, "data": {}}


def _raw():
    p = path()
    try:
        m = p.stat().st_mtime_ns
    except OSError:
        return {}
    if _cache["mtime"] != m:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        _cache.update(mtime=m, data=d if isinstance(d, dict) else {})
    return _cache["data"]


def get(name, default=""):
    """The value of one setting. Secrets are decrypted here, in memory, and should never be logged."""
    v = _raw().get(name, "")
    if name in SECRETS:
        v = _open(v)
    return v or default


def public():
    """What the page may see: values for plain settings, only {set: bool} for secrets."""
    d = _raw()
    out = {k: ({"set": bool(d.get(k))} if k in SECRETS else (d.get(k) or "")) for k in FIELDS}
    out["settings_file"] = str(path())
    return out


def validate(name, value):
    value = (value or "").strip()
    if not value:
        return ""
    if name in PATHS:
        p = Path(os.path.expandvars(os.path.expanduser(value)))
        if name == "aegir_tool" and not (p / "aegir_ran" / "__init__.py").is_file():
            raise ValueError("that folder does not contain aegir_ran/ (choose the RAN 'tool' folder)")
        if name == "history_dir" and not p.is_dir():
            raise ValueError("history folder not found")
        if name == "workspace":
            p.mkdir(parents=True, exist_ok=True)
            if not os.access(p, os.W_OK):
                raise ValueError("that folder is not writable")
        return str(p)
    if name == "contact_email":
        if "@" not in value or " " in value or len(value) > 120 or value.startswith("@") or value.endswith("@"):
            raise ValueError("that does not look like an email address")
        return value
    if any(c in value for c in " \r\n\t") or len(value) > 300:
        raise ValueError("a token or key has no spaces or line breaks")
    return value


def save(changes):
    """Apply {field: value}. An empty string clears a field; a field left out is unchanged. Returns public()."""
    d = dict(_raw())
    for k, v in (changes or {}).items():
        if k not in FIELDS:
            raise ValueError(f"unknown setting: {k}")
        if v is None:
            continue
        v = validate(k, v)
        if not v:
            d.pop(k, None)
        else:
            d[k] = _seal(v) if k in SECRETS else v
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, p)
    _cache["mtime"] = None
    apply_env()
    return public()


def apply_env():
    """Hand the NCBI key/email to RAN's client the way it already expects them (environment), without writing them to any project file."""
    for env, name in (("NCBI_API_KEY", "ncbi_api_key"), ("NCBI_EMAIL", "contact_email")):
        v = get(name)
        if v:
            os.environ[env] = v
        elif env in os.environ and os.environ.get("AUTORAN_ENV_SET_" + env):
            os.environ.pop(env, None)
        if v:
            os.environ["AUTORAN_ENV_SET_" + env] = "1"


def user_agent():
    from . import __version__
    e = get("contact_email")
    return f"AutoRAN/{__version__}" + (f" (contact: {e})" if e else "")


def seed_workspace(ws, code_root):
    """A workspace needs config/ beside its data/. Copy it from the program folder when missing (never overwrite)."""
    ws, code_root = Path(ws), Path(code_root)
    if ws.resolve() == code_root.resolve():
        return
    (ws / "config").mkdir(parents=True, exist_ok=True)
    for f in (code_root / "config").glob("*.json"):
        t = ws / "config" / f.name
        if not t.exists():
            t.write_bytes(f.read_bytes())
