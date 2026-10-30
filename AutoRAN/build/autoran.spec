# PyInstaller spec for AutoRAN.exe: one folder, windowed, with Python, the window library, PyTorch (CUDA), numpy, pandas and matplotlib inside.
# Build with build\build.ps1. The spec lives in build/, so paths are relative to that folder.
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

HERE = os.path.abspath(".")
ROOT = os.path.dirname(HERE)
TOOL = os.path.abspath(os.path.join(ROOT, "..", "AEGIR", "tool"))         # RAN's package, bundled into the exe
if not os.path.isdir(os.path.join(TOOL, "aegir_ran")):
    TOOL = os.path.abspath(os.path.join(ROOT, "..", "AEGIR-open", "tool"))

datas, binaries, hidden = [], [], []
for pkg in ("webview",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h
hidden += collect_submodules("autoran") + collect_submodules("aegir_ran")
hidden += ["clr_loader", "pythonnet", "matplotlib.backends.backend_agg", "matplotlib.ticker", "pyarrow.pandas_compat", "scipy.special._cdflib"]

a = Analysis(
    [os.path.join(HERE, "entry_gui.py")],
    pathex=[ROOT, TOOL],
    datas=datas,
    binaries=binaries,
    hiddenimports=hidden,
    excludes=["tkinter", "IPython", "jupyter", "notebook", "PyQt5", "PyQt6", "PySide6", "sphinx", "pytest", "torch.utils.tensorboard",
              "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_qt5agg", "matplotlib.backends.backend_qtagg"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AutoRAN", console=False, upx=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="AutoRAN", upx=False)
