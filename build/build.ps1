# Build RAN.exe (portable, one file) into the AEGIR folder.
# Usage:  powershell -ExecutionPolicy Bypass -File build\build.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Set-Location $here
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --quiet --disable-pip-version-check -r requirements-build.txt
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath "$here\dist" --workpath "$here\work" ran.spec
# The exe goes next to config\ and data\, which is where it looks for them.
# If the old RAN.exe is running (for example a labelling session), Windows locks it: save as RAN-new.exe instead.
try {
    Copy-Item "$here\dist\RAN.exe" "$root\RAN.exe" -Force
    Write-Host "Built $root\RAN.exe"
} catch {
    Copy-Item "$here\dist\RAN.exe" "$root\RAN-new.exe" -Force
    Write-Host "RAN.exe is in use. Built $root\RAN-new.exe: close the running tool, then rename it to RAN.exe."
}
