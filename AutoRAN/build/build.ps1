# Build AutoRAN.exe (desktop app) into the AutoRAN folder.
#   powershell -ExecutionPolicy Bypass -File build\build.ps1
# Needs the AutoRAN virtual environment (.venv) with torch, numpy, pandas, matplotlib, pyarrow, pywebview and pyinstaller:
#   uv venv .venv --python 3.13
#   uv pip install --python .venv/Scripts/python.exe --torch-backend=auto torch numpy pandas pyarrow matplotlib plotly scipy pywebview pyinstaller
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Set-Location $here
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Missing .venv: see the header of this script." }
& $py -m PyInstaller --noconfirm --clean --distpath "$here\dist" --workpath "$here\work" autoran.spec
# the clickable file goes in the AutoRAN folder, next to config\ and data\ (it looks for them there)
$out = Join-Path $here "dist\AutoRAN"
if (-not (Test-Path (Join-Path $out "AutoRAN.exe"))) { throw "Build did not produce AutoRAN.exe" }
try {
    if (Test-Path (Join-Path $root "_internal")) { Remove-Item (Join-Path $root "_internal") -Recurse -Force }
    Copy-Item (Join-Path $out "AutoRAN.exe") (Join-Path $root "AutoRAN.exe") -Force
    Copy-Item (Join-Path $out "_internal") (Join-Path $root "_internal") -Recurse -Force
    Write-Host "Built $root\AutoRAN.exe"
} catch {
    Write-Host "Could not replace the running app ($($_.Exception.Message)). The new build is in $out : close AutoRAN and copy AutoRAN.exe and _internal\ over."
}
