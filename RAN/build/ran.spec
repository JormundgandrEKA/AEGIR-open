# PyInstaller spec: one-file, console, portable. Build with build/build.ps1.
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["ran_entry.py"],
    pathex=["..", "../../shared"],
    datas=[("../../shared/config/aegir.json", "defaults"), ("../../shared/config/grades.json", "defaults"),
           ("../demo/ran-demo-batch.json", "demo")]
          + collect_data_files("tzdata"),
    hiddenimports=["zoneinfo", "aegir_core"],
    excludes=["tkinter", "unittest", "pydoc", "test"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="RAN", console=True, upx=False,
          runtime_tmpdir=None)
