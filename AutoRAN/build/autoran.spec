# PyInstaller spec for AutoRAN.exe: one folder, windowed, with Python, the window library, PyTorch (CUDA), numpy, pandas and matplotlib inside.
# Build with build\build.ps1. The spec lives in build/, so paths are relative to that folder.
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

HERE = os.path.abspath(".")
ROOT = os.path.dirname(HERE)
# RAN's package, bundled into the exe: AEGIR_TOOL, then ../tool (AutoRAN inside AEGIR-open), ../AEGIR/tool, ../AEGIR-open/tool
_cands = ([os.environ["AEGIR_TOOL"]] if os.environ.get("AEGIR_TOOL") else []) + [os.path.join(ROOT, "..", *p) for p in (("RAN",), ("tool",), ("AEGIR", "tool"), ("AEGIR-open", "tool"))]
TOOL = next((os.path.abspath(c) for c in _cands if os.path.isfile(os.path.join(c, "aegir_ran", "__init__.py"))), None)
if TOOL is None:
    raise SystemExit("build: cannot find RAN (aegir_ran). Put AutoRAN inside AEGIR-open or set AEGIR_TOOL to the folder that contains aegir_ran/.")

datas, binaries, hidden = [], [], []
for pkg in ("webview",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
hidden += collect_submodules("autoran") + collect_submodules("aegir_ran")
LITE = os.environ.get("AUTORAN_LITE") == "1"            # small build: no PyTorch/CUDA inside (CPU everywhere; GPU via a gpu_pack folder)
if LITE:   # PyTorch is loaded at run time from the user's own install; it needs standard-library modules this app never imports itself
    import sys as _sys
    _skip = {"tkinter", "idlelib", "test", "turtledemo", "turtle", "lib2to3", "ensurepip", "distutils", "this", "antigravity", "__main__", "_tkinter"}
    hidden += sorted(m for m in _sys.stdlib_module_names if m not in _skip and not m.startswith("_") and not m.startswith("test"))
hidden += ["clr_loader", "pythonnet", "matplotlib.backends.backend_agg", "matplotlib.ticker", "pyarrow.pandas_compat"]

a = Analysis(
    [os.path.join(HERE, "entry_gui.py")],
    pathex=[ROOT, TOOL],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden,
    excludes=["scipy", "plotly", "tkinter", "pytest", "IPython", "jupyter", "notebook", "PyQt5", "PyQt6", "PySide6", "sphinx", "pytest", "torch.utils.tensorboard",
              "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_qt5agg", "matplotlib.backends.backend_qtagg"] + (["torch", "torchgen", "functorch", "sympy", "networkx", "numba", "triton", "sklearn", "lxml", "openpyxl", "sqlalchemy"] if LITE else []),
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AutoRAN", console=False, upx=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="AutoRAN", upx=False)
