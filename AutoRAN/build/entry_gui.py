"""Entry point for AutoRAN.exe (windowed: no console). Same as `python -m autoran.app`."""
import os
import sys

# a windowed exe has no console: give libraries that print something harmless to write to
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from autoran.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
