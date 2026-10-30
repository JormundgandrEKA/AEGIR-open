# Check this computer's Python and install what AutoRAN is missing. Nothing is installed without your say-so.
#   powershell -ExecutionPolicy Bypass -File setup.ps1            core app packages (about 300 MB)
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Gpu       also PyTorch for an NVIDIA GPU (about 3 GB)
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Build     also PyInstaller, to build AutoRAN.exe
param([switch]$Gpu, [switch]$Build)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "Python 3.11 or newer was not found on PATH. Install it from https://www.python.org/downloads/ and run this again." }
& $py -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 or newer is needed (found: $(& $py --version))." }
Write-Host "Using $py ($(& $py --version))"
function Missing($mods) { $m = @(); foreach ($x in $mods) { & $py -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('$($x[0])') else 1)"; if ($LASTEXITCODE -ne 0) { $m += $x[1] } }; $m }
function Pip($pkgs, $extra) {
    if (-not $pkgs) { return }
    Write-Host "Installing: $($pkgs -join ' ')"
    & $py -m pip install @pkgs @extra
    if ($LASTEXITCODE -ne 0) {      # Pythons marked "externally managed" (uv, Linux distros) need an explicit override
        Write-Host "Retrying with --break-system-packages (this Python is externally managed)."
        & $py -m pip install --break-system-packages @pkgs @extra
    }
}
Pip (Missing @(@("numpy","numpy>=2.0"),@("pandas","pandas>=2.2"),@("pyarrow","pyarrow>=16"),@("matplotlib","matplotlib>=3.9"),@("webview","pywebview>=5.0"))) @()
if ($Gpu)   { Pip (Missing @(,@("torch","torch"))) @("--index-url","https://download.pytorch.org/whl/cu128") }
if ($Build) { Pip (Missing @(,@("PyInstaller","pyinstaller>=6"))) @() }
if (-not (Test-Path "$here\..\shared\aegir_core\__init__.py")) { Write-Host "Note: AutoRAN needs the repository's shared\ folder next to it. Use a full clone of AEGIR-open (git clone https://github.com/JormundgandrEKA/AEGIR-open.git)." }
Write-Host "Done. Start the app with:  python -m autoran.app"
