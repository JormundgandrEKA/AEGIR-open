"""Is this computer ready for GPU scoring, and if not, what can be done about it. Standard library only.

AutoRAN's small exe has no PyTorch inside. It can borrow one that is already on the computer (any Python with a CUDA build of PyTorch
for the same Python version as the exe), or install one for itself into a private folder. This module:

  * reads the graphics card and driver from nvidia-smi (CUDA itself comes inside the PyTorch wheels; only the driver is needed);
  * scans the computer's Pythons for PyTorch, in the background, and caches the answer for a week;
  * decides: ready / found / incompatible / not_found / no_gpu;
  * makes a found PyTorch usable (adds its folder to the search path) and checks that it imports;
  * installs PyTorch with pip into %LOCALAPPDATA%\\AEGIR\\gpu_pack, choosing the CUDA build that the driver supports.

PyTorch is installed from pip wheels (download.pytorch.org), not from git. Nothing here touches any system Python.
"""
import glob
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import _shared  # noqa: F401  (makes aegir_core importable)
from aegir_core.core import shared_state_dir

BUNDLED_TAG = "cp%d%d" % sys.version_info[:2]                  # the Python this program runs on, e.g. cp313
CACHE_DAYS = 7
EXPECTED_GB = 3.0                                              # about what a CUDA PyTorch needs on disk
TORCH_DEPS = ["filelock", "typing-extensions>=4.10.0", "setuptools>=77.0.3", "sympy>=1.13.3", "networkx>=2.5.1", "jinja2", "fsspec>=0.8.5"]   # torch 2.14 Requires-Dist, besides itself
CUDA_INDEXES = [("cu130", 13.0), ("cu128", 12.8), ("cu126", 12.6), ("cu124", 12.4), ("cu121", 12.1), ("cu118", 11.8)]
NOWIN = 0x08000000 if os.name == "nt" else 0                   # no console flash for child processes

RUN = subprocess.run                                           # tests replace this

PROBE = r'''
import json, sys, os
o = {"python": sys.version.split()[0], "tag": "cp%d%d" % sys.version_info[:2], "exe": sys.executable}
try:
    import pip; o["has_pip"] = True
except Exception:
    o["has_pip"] = False
try:
    import numpy; o["numpy"] = numpy.__version__
except Exception:
    o["numpy"] = None
try:
    import torch
    o["torch"] = torch.__version__; o["cuda_build"] = torch.version.cuda; o["cuda_ok"] = bool(torch.cuda.is_available())
    o["site"] = os.path.dirname(os.path.dirname(torch.__file__))
except Exception as e:
    o["torch"] = None; o["why"] = type(e).__name__
print(json.dumps(o))
'''

_lock = threading.Lock()
SCAN = {"state": "idle", "started": None}
INSTALL = {"state": "idle", "log": [], "progress": 0.0, "message": "", "started": None, "finished": None}


# -- places ----------------------------------------------------------------------------------

def cache_path():
    return shared_state_dir() / "gpu_probe.json"


def managed_dir():
    """The private PyTorch folder AutoRAN installs into (shared by every AutoRAN on this computer)."""
    return shared_state_dir().parent / "gpu_pack"


def load_cache():
    try:
        d = json.loads(cache_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def cache_is_fresh(d=None):
    d = d if d is not None else load_cache()
    return bool(d) and (time.time() - d.get("ts", 0)) < CACHE_DAYS * 86400


# -- the card and driver ----------------------------------------------------------------------

def smi():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"gpu": None, "why": "no NVIDIA driver found (nvidia-smi is missing)"}
    try:
        q = RUN([exe, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=20, creationflags=NOWIN)
        line = q.stdout.strip().splitlines()[0]
        full = RUN([exe], capture_output=True, text=True, timeout=20, creationflags=NOWIN).stdout
        m = re.search(r"CUDA Version:\s*([\d.]+)", full)
        name, drv, mem = [x.strip() for x in line.split(",")]
        return {"gpu": name, "driver": drv, "memory_mb": int(float(mem)), "max_cuda": m.group(1) if m else None}
    except Exception as e:
        return {"gpu": None, "why": f"nvidia-smi did not answer ({type(e).__name__})"}


# -- the computer's Pythons --------------------------------------------------------------------

def candidates():
    seen, out = set(), []

    def add(p):
        if not p:
            return
        p = os.path.normcase(os.path.abspath(p))
        base = os.path.basename(p)
        if base.startswith("pythonw") or not os.path.isfile(p) or p in seen:
            return
        if getattr(sys, "frozen", False) and os.path.normcase(os.path.abspath(sys.executable)) == p:
            return                                               # that is AutoRAN.exe itself
        seen.add(p)
        out.append(p)
    add(shutil.which("python"))
    try:
        for line in RUN(["py", "-0p"], capture_output=True, text=True, timeout=15, creationflags=NOWIN).stdout.splitlines():
            m = re.search(r"([A-Za-z]:\\.*python\.exe)", line)
            if m:
                add(m.group(1))
    except Exception:
        pass
    for pat in (r"%APPDATA%\uv\python\*\python.exe", r"%LOCALAPPDATA%\Programs\Python\*\python.exe", r"C:\ProgramData\anaconda3\python.exe",
                r"%USERPROFILE%\anaconda3\python.exe", r"%USERPROFILE%\miniconda3\python.exe", r"%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe",
                r"%LOCALAPPDATA%\Microsoft\WindowsApps\python3*.exe", r"C:\Program Files\Python*\python.exe"):
        for p in glob.glob(os.path.expandvars(pat)):
            add(p)
    if os.name != "nt":
        for n in ("python3", "python3.13", "python3.12", "python3.11"):
            add(shutil.which(n))
    return out


def probe_python(exe, timeout=90):
    try:
        r = RUN([exe, "-c", PROBE], capture_output=True, text=True, timeout=timeout, creationflags=NOWIN)
        lines = [l for l in r.stdout.splitlines() if l.startswith("{")]
        return json.loads(lines[-1]) if lines else None
    except Exception:
        return None


def _tver(v):
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


# -- the verdict -------------------------------------------------------------------------------

def decide(smi_info, probes, in_process=None):
    """One of: ready, found, incompatible, not_found, no_gpu, with a plain sentence and what to do."""
    pip_py = next((p for p in sorted(probes, key=lambda p: p["tag"] != BUNDLED_TAG) if p.get("has_pip")), None)
    base = {"can_install": bool(pip_py and smi_info.get("gpu")), "pip_python": pip_py["exe"] if pip_py else None}
    if in_process and in_process.get("cuda_ok"):
        return dict(base, state="ready", torch=in_process.get("torch"), text=f"Ready. AutoRAN is using PyTorch {in_process.get('torch')} on your {smi_info.get('gpu') or 'GPU'}.")
    if not smi_info.get("gpu"):
        return dict(base, state="no_gpu", text="No NVIDIA graphics card or driver was found, so AutoRAN uses the CPU. Everything works, just more slowly. Nothing to install.")
    ok = [p for p in probes if p.get("torch") and p["tag"] == BUNDLED_TAG and p.get("cuda_ok")]
    if ok:
        best = max(ok, key=lambda p: _tver(p["torch"]))
        return dict(base, state="found", python=best["exe"], site=best["site"], torch=best["torch"],
                    text=f"Found a CUDA-ready PyTorch {best['torch']} (Python {best['python']}). AutoRAN can use it without installing anything.")
    same_cpu = [p for p in probes if p.get("torch") and p["tag"] == BUNDLED_TAG and not p.get("cuda_ok")]
    other = [p for p in probes if p.get("torch") and p["tag"] != BUNDLED_TAG]
    why = []
    if same_cpu:
        why.append(f"PyTorch {same_cpu[0]['torch']} in Python {same_cpu[0]['python']} cannot see your GPU (a CPU-only build, or a driver problem)")
    if other:
        why.append(f"PyTorch {other[0]['torch']} exists only in Python {other[0]['python']}, but this AutoRAN needs a build for Python {BUNDLED_TAG[2]}.{BUNDLED_TAG[3:]}")
    if why:
        return dict(base, state="incompatible", text="Found PyTorch, but it cannot be used: " + "; ".join(why) + ". You can install a matching one for AutoRAN.")
    return dict(base, state="not_found", text=f"Your {smi_info['gpu']} is ready for CUDA (driver {smi_info.get('driver')}), but PyTorch is not installed anywhere AutoRAN can use. You can install it for AutoRAN (about {EXPECTED_GB:g} GB).")


def in_process_info():
    """What this program sees right now (imports PyTorch if it can be found; slow the first time)."""
    try:
        import torch
        d = {"torch": torch.__version__, "cuda_ok": bool(torch.cuda.is_available())}
        if d["cuda_ok"]:
            d["device"] = torch.cuda.get_device_name(0)
        return d
    except Exception as e:
        return {"torch": None, "cuda_ok": False, "why": f"{type(e).__name__}: {str(e)[:120]}"}


# -- making a found PyTorch usable ------------------------------------------------------------

def activate(site=None):
    """Add a PyTorch folder to the search path and check it imports. Returns in_process_info() (or why not)."""
    managed = str(managed_dir())
    if (Path(managed) / "torch" / "__init__.py").is_file() and managed not in sys.path and (site is None or site == managed):
        sys.path.insert(0, managed)                                # our own install wins over any other PyTorch on the PC
    elif site and (Path(site) / "torch" / "__init__.py").is_file() and site not in sys.path:
        sys.path.append(site)                                      # someone else's folder goes last so it cannot shadow the bundled libraries
    importlib.invalidate_caches()
    return in_process_info()


def scan(force=False):
    """Probe the card and every Python; cache and return the verdict. Safe to call from a thread."""
    with _lock:
        if SCAN["state"] == "running":
            return load_cache()
        SCAN.update(state="running", started=time.time())
    return _do_scan()


def _do_scan():
    try:
        s = smi()
        exes = candidates()
        results = [None] * len(exes)

        def work(i, e):
            results[i] = probe_python(e)
        ts = [threading.Thread(target=work, args=(i, e), daemon=True) for i, e in enumerate(exes)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(120)
        probes, seen = [], set()
        for p in results:
            if p:
                k = (p["tag"], p.get("torch"), p.get("site"), p["python"])
                if k not in seen:                                  # the Store Python answers under several names
                    seen.add(k)
                    probes.append(p)
        verdict = decide(s, probes)
        out = {"ts": time.time(), "smi": s, "pythons": probes, "verdict": verdict, "bundled_tag": BUNDLED_TAG}
        try:
            cache_path().parent.mkdir(parents=True, exist_ok=True)
            cache_path().write_text(json.dumps(out), encoding="utf-8")
        except OSError:
            pass
        if verdict["state"] == "found":
            activate(verdict["site"])                              # auto-use: no setting, no restart
        return out
    finally:
        SCAN["state"] = "idle"


def start_scan():
    with _lock:
        if SCAN["state"] == "running":
            return False
        SCAN.update(state="running", started=time.time())
    threading.Thread(target=_do_scan, daemon=True).start()
    return True


def wait_for_scan(timeout=90):
    t = time.time()
    while SCAN["state"] == "running" and time.time() - t < timeout:
        time.sleep(0.3)


def status():
    """Everything the Settings page shows about the GPU."""
    c = load_cache()
    return {"scan": dict(SCAN), "cache": c, "fresh": cache_is_fresh(c), "install": dict(INSTALL, log=INSTALL["log"][-40:]),
            "managed_dir": str(managed_dir()), "bundled_tag": BUNDLED_TAG, "expected_gb": EXPECTED_GB}


def ensure_scanned():
    """At start-up: if PyTorch is not usable yet and the answer is missing or a week old, look in the background."""
    if cache_is_fresh():
        return False
    try:
        import torch  # noqa: F401
        return False
    except ImportError:
        return start_scan()


# -- installing --------------------------------------------------------------------------------

def indexes_for(max_cuda, limit=3):
    try:
        mx = float(max_cuda)
    except (TypeError, ValueError):
        return [CUDA_INDEXES[2][0]]                                # unknown: the widely supported cu126
    return [name for name, v in CUDA_INDEXES if v <= mx][:limit] or [CUDA_INDEXES[-1][0]]


def install_plan(smi_info=None, probes=None):
    c = load_cache() or {}
    smi_info = smi_info or c.get("smi") or smi()
    probes = probes if probes is not None else c.get("pythons", [])
    pip_py = next((p for p in sorted(probes, key=lambda p: p["tag"] != BUNDLED_TAG) if p.get("has_pip")), None)
    target = managed_dir()
    free_gb = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        free_gb = round(shutil.disk_usage(target.parent).free / 2 ** 30, 1)
    except OSError:
        pass
    plan = {"ok": False, "target": str(target), "expected_gb": EXPECTED_GB, "free_gb": free_gb, "commands": [], "python": None}
    if not smi_info.get("gpu"):
        plan["why"] = "No NVIDIA graphics card or driver was found, so there is nothing to install."
        return plan
    if not pip_py:
        plan["why"] = "No Python with pip was found. Install Python 3.11 or newer from python.org (tick 'Add to PATH'), then check again."
        return plan
    if free_gb is not None and free_gb < EXPECTED_GB * 2:
        plan["why"] = f"Not enough free disk space: {free_gb} GB free, about {EXPECTED_GB * 2:g} GB needed while installing."
        return plan
    for idx in indexes_for(smi_info.get("max_cuda")):
        base = [pip_py["exe"], "-m", "pip", "install", "--no-cache-dir", "--progress-bar", "off", "--only-binary=:all:", "--target", str(target)]
        if pip_py["tag"] != BUNDLED_TAG:                           # pip from another Python can still fetch wheels for ours
            base[4:4] = ["--python-version", f"{BUNDLED_TAG[2]}.{BUNDLED_TAG[3:]}", "--platform", "win_amd64" if os.name == "nt" else "manylinux2014_x86_64"]
        # step 1 takes torch from the PyTorch index ONLY: PyPI's Windows torch is a CPU build and would win on version number.
        # step 2 takes its small dependencies from PyPI.
        step1 = base + ["--upgrade", "--no-deps", "--index-url", f"https://download.pytorch.org/whl/{idx}", "torch"]
        step2 = base + ["--upgrade"] + TORCH_DEPS
        plan["commands"].append({"index": idx, "cmds": [step1, step2]})
    plan.update(ok=True, python=pip_py["exe"], python_version=pip_py["python"])
    return plan


def _folder_gb(p):
    n = 0
    try:
        for dp, dn, fn in os.walk(p):
            for f in fn:
                try:
                    n += os.path.getsize(os.path.join(dp, f))
                except OSError:
                    pass
    except OSError:
        pass
    return n / 2 ** 30


def _log(line):
    INSTALL["log"].append(line.rstrip()[:300])
    del INSTALL["log"][:-300]


def run_install(plan=None):
    """Run pip (blocking). Tries the highest CUDA build the driver supports first, then lower ones. Returns INSTALL."""
    plan = plan or install_plan()
    if not plan["ok"]:
        INSTALL.update(state="failed", message=plan.get("why", "cannot install"), finished=time.time())
        return INSTALL
    INSTALL.update(state="running", log=[], progress=0.0, message="Installing PyTorch. This downloads about 3 GB and takes several minutes.", started=time.time(), finished=None)
    stop = threading.Event()

    def watch():
        while not stop.wait(2):
            INSTALL["progress"] = round(min(0.95, _folder_gb(plan["target"]) / plan["expected_gb"]), 3)
    threading.Thread(target=watch, daemon=True).start()
    try:
        for item in plan["commands"]:
            _log(f"trying the {item['index']} build")
            rc = 0
            for n, cmd in enumerate(item["cmds"], 1):
                _log(f"step {n} of {len(item['cmds'])}: " + ("PyTorch itself" if n == 1 else "its small dependencies"))
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=NOWIN)
                for line in p.stdout:
                    _log(line)
                rc = p.wait()
                if rc != 0:
                    break
            if rc == 0:
                info = activate()
                if info.get("torch"):
                    INSTALL.update(state="done", progress=1.0, message=f"Installed PyTorch {info['torch']}" + (" and found your GPU." if info.get("cuda_ok") else ", but it cannot see the GPU. Update your NVIDIA driver."), finished=time.time())
                    scan_cache_refresh()
                    return INSTALL
                _log("installed, but it did not import: " + info.get("why", ""))
            _log(f"the {item['index']} build failed")
        INSTALL.update(state="failed", message="PyTorch could not be installed. The details are in the log below.", finished=time.time())
    except Exception as e:
        INSTALL.update(state="failed", message=f"Install stopped: {type(e).__name__}: {e}", finished=time.time())
    finally:
        stop.set()
    return INSTALL


def scan_cache_refresh():
    try:
        scan()
    except Exception:
        pass


def start_install(plan=None):
    if INSTALL["state"] == "running":
        return False
    threading.Thread(target=run_install, args=(plan,), daemon=True).start()
    return True
