# Build AutoRAN.exe (desktop app).
#   powershell -ExecutionPolicy Bypass -File build\build.ps1          small build (about 190 MB, no PyTorch inside): AutoRAN.exe + _internal\ in the AutoRAN folder,
#                                                                      and build\dist-lite\AutoRAN-lite-win64.zip for sharing
#   powershell -ExecutionPolicy Bypass -File build\build.ps1 -Full    also bundles PyTorch + CUDA (about 4 GB); only for a machine with no Python of its own
# Needs Python 3.11+ with the packages in requirements.txt and pyinstaller (run setup.ps1 -Build). Uses .venv\ if there is one, else `python` on PATH.
# The small build runs on the CPU. For the GPU it uses an existing PyTorch install: Settings > "GPU pack folder", or a gpu_pack\ folder beside the exe.
param([switch]$Full)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Set-Location $here
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python -ErrorAction Stop).Source }
if ($Full) { $env:AUTORAN_LITE = "0"; $dist = "$here\dist"; $work = "$here\work" } else { $env:AUTORAN_LITE = "1"; $dist = "$here\dist-lite"; $work = "$here\work-lite" }
& $py -m PyInstaller --noconfirm --clean --distpath $dist --workpath $work autoran.spec
$out = Join-Path $dist "AutoRAN"
if (-not (Test-Path (Join-Path $out "AutoRAN.exe"))) { throw "Build did not produce AutoRAN.exe" }
if (-not $Full) {
    foreach ($f in "LICENSE", "NOTICE", "THIRD_PARTY.md", "DISCLAIMERS.md") { Copy-Item (Join-Path $root $f) $out -Force }
    Copy-Item (Join-Path $root "config") (Join-Path $out "config") -Recurse -Force
    Copy-Item (Join-Path $root "plugins") (Join-Path $out "plugins") -Recurse -Force
    $zip = Join-Path $dist "AutoRAN-lite-win64.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path $out -DestinationPath $zip
    Write-Host ("Zip for sharing: {0} ({1:N0} MB)" -f $zip, ((Get-Item $zip).Length / 1MB))
}
# the clickable file goes in the AutoRAN folder, next to config\ and data\ (it looks for them there)
try {
    if (Test-Path (Join-Path $root "_internal")) { Remove-Item (Join-Path $root "_internal") -Recurse -Force }
    Copy-Item (Join-Path $out "AutoRAN.exe") (Join-Path $root "AutoRAN.exe") -Force
    Copy-Item (Join-Path $out "_internal") (Join-Path $root "_internal") -Recurse -Force
    Write-Host "Built $root\AutoRAN.exe"
} catch {
    Write-Host "Could not replace the running app ($($_.Exception.Message)). The new build is in $out : close AutoRAN and copy AutoRAN.exe and _internal\ over."
}
