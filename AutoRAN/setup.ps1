# Check this computer's Python and install what AutoRAN is missing. Nothing is installed without your say-so.
#   powershell -ExecutionPolicy Bypass -File setup.ps1            core app packages (about 300 MB)
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Gpu       also PyTorch for an NVIDIA GPU (about 3 GB)
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Build     also PyInstaller, to build AutoRAN.exe
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Ran       also clone RAN (aegir_ran) from AEGIR-open with git if it is not beside AutoRAN
param([switch]$Gpu, [switch]$Build, [switch]$Ran)
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
$tool = @("$here\..\tool", "$here\..\AEGIR\tool", "$here\..\AEGIR-open\tool") | Where-Object { Test-Path "$_\aegir_ran\__init__.py" } | Select-Object -First 1
if ($tool) { Write-Host "RAN found: $tool" }
elseif ($Ran) {
    git clone --depth 1 https://github.com/JormundgandrEKA/AEGIR-open.git "$here\..\AEGIR-open"
    Write-Host "Cloned AEGIR-open next to AutoRAN."
} else { Write-Host "RAN (aegir_ran) not found. Put AutoRAN inside the AEGIR-open folder, run this with -Ran, or set the RAN folder in Settings." }
Write-Host "Done. Start the app with:  python -m autoran.app"
