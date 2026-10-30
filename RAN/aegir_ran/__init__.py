"""RAN: the AEGIR answer-key tool (Registry and Article Net). Uses the shared package aegir_core (../shared in the repository)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                     # the RAN folder: config/queries, demo/, data/, state/ live here
try:
    import aegir_core  # noqa: F401
except ImportError:                                           # running from the repository: the shared package sits beside RAN/
    sys.path.insert(0, str(ROOT.parent / "shared"))
    import aegir_core  # noqa: F401,E402

from aegir_core import core as _core  # noqa: E402
_core.DEFAULT_ROOT = ROOT

from aegir_core.core import VERSION as __version__  # noqa: F401,E402
from aegir_core.context import make_ctx  # noqa: F401,E402
