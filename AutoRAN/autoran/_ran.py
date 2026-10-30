"""Find RAN's package (aegir_ran) so AutoRAN can reuse its client, limits, store and text tools.

Search order: the Settings page (aegir_tool), AEGIR_TOOL, then ../tool (AutoRAN as a submodule of AEGIR-open), ../AEGIR/tool, ../AEGIR-open/tool.
AutoRAN adds no code to RAN and changes nothing in it.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def find_tool():
    cands = []
    from . import settings
    if settings.get("aegir_tool"):
        cands.append(Path(settings.get("aegir_tool")))
    if os.environ.get("AEGIR_TOOL"):
        cands.append(Path(os.environ["AEGIR_TOOL"]))
    cands += [HERE.parent / "tool", HERE.parent / "AEGIR" / "tool", HERE.parent / "AEGIR-open" / "tool"]
    for c in cands:
        if (c / "aegir_ran" / "__init__.py").is_file():
            return c
    return None


def ensure():
    try:
        import aegir_ran  # noqa: F401
    except ImportError:
        tool = find_tool()
        if tool is None:
            raise SystemExit("AutoRAN needs RAN (aegir_ran). Put AutoRAN inside the AEGIR-open folder, next to AEGIR, or set AEGIR_TOOL "
                             "to the folder that contains aegir_ran/, or choose it on the Settings page.")
        sys.path.insert(0, str(tool))


ensure()
