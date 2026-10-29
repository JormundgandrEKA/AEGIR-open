"""PyInstaller entry point for RAN.exe (the same as `python -m aegir_ran`)."""
import sys

from aegir_ran.cli import run

if __name__ == "__main__":
    sys.exit(run())
