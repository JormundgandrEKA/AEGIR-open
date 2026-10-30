# PyInstaller spec for AutoRAN.exe: one folder, windowed, with Python, the window library, PyTorch (CUDA), numpy, pandas and matplotlib inside.
# Build with build\build.ps1. The spec lives in build/, so paths are relative to that folder.
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

HERE = os.path.abspath(".")
ROOT = os.path.dirname(HERE)
# The shared package (aegir_core) and its config, bundled into the exe: ../shared in the repository, or AEGIR_SHARED
_cands = ([os.environ["AEGIR_SHARED"]] if os.environ.get("AEGIR_SHARED") else []) + [os.path.join(ROOT, "..", "shared")]
SHARED = next((os.path.abspath(c) for c in _cands if os.path.isfile(os.path.join(c, "aegir_core", "__init__.py"))), None)
if SHARED is None:
    raise SystemExit("build: cannot find the shared folder (shared/aegir_core). Build from a full clone of AEGIR-open, or set AEGIR_SHARED.")

datas, binaries, hidden = [(os.path.join(SHARED, "config", "aegir.json"), "defaults"), (os.path.join(SHARED, "config", "grades.json"), "defaults")], [], []
for pkg in ("webview",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
hidden += collect_submodules("autoran") + collect_submodules("aegir_core")
LITE = os.environ.get("AUTORAN_LITE") == "1"            # small build: no PyTorch/CUDA inside (CPU everywhere; GPU via a gpu_pack folder)
if LITE:   # PyTorch is loaded at run time from the user's own install; it needs standard-library modules this app never imports itself
    import sys as _sys
    _skip = {"tkinter", "idlelib", "test", "turtledemo", "turtle", "lib2to3", "ensurepip", "distutils", "this", "antigravity", "__main__", "_tkinter"}
    hidden += sorted(m for m in _sys.stdlib_module_names if m not in _skip and not m.startswith("_") and not m.startswith("test"))
hidden += ["clr_loader", "pythonnet", "matplotlib.backends.backend_agg", "matplotlib.ticker", "pyarrow.pandas_compat"]

a = Analysis(
    [os.path.join(HERE, "entry_gui.py")],
    pathex=[ROOT, SHARED],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden,
    excludes=["scipy", "plotly", "tkinter", "pytest", "IPython", "jupyter", "notebook", "PyQt5", "PyQt6", "PySide6", "sphinx", "pytest", "torch.utils.tensorboard",
              "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_qt5agg", "matplotlib.backends.backend_qtagg"] + (["torch", "torchgen", "functorch", "sympy", "networkx", "numba", "triton", "sklearn", "lxml", "openpyxl", "sqlalchemy"] if LITE else []),
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AutoRAN", console=False, upx=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="AutoRAN", upx=False)
