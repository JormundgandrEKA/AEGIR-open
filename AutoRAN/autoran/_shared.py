"""Make the shared package (aegir_core: HTTP client with polite limits, store, run context, text tools) importable.

It lives in ../shared when AutoRAN runs from the AEGIR-open repository, or inside the executable. Set AEGIR_SHARED to point elsewhere.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def ensure():
    try:
        import aegir_core  # noqa: F401
    except ImportError:
        cands = ([Path(os.environ["AEGIR_SHARED"])] if os.environ.get("AEGIR_SHARED") else []) + [HERE.parent / "shared"]
        for c in cands:
            if (c / "aegir_core" / "__init__.py").is_file():
                sys.path.insert(0, str(c))
                return
        raise SystemExit("AutoRAN needs the shared folder of the AEGIR-open repository (shared/aegir_core). Use a full clone of the repository, "
                         "or set AEGIR_SHARED to the folder that contains aegir_core/.")


ensure()
