"""Command line: python -m aegir_ran <group> <command> [options]. Ends with one JSON summary line."""
import argparse
import json
import sys

from . import batches, ctgov, derive, epmc, labels, link, pmc, pubmed, reports
from .context import Ctx
from .http import BudgetExceeded, HostBlocked, WindowRefused


NL = chr(10)


def _params(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        out[k] = v
    return out


def _common():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--dry-run", action="store_true", help="print requests and an estimate; fetch nothing")
    p.add_argument("--max", type=int, dest="max_items", help="maximum items")
    p.add_argument("--max-requests", type=int, help="request budget (default 500)")
    p.add_argument("--refresh", action="store_true", help="refetch even if catalogued")
    p.add_argument("--resume", action="store_true", help="skip what is catalogued (the default)")
    p.add_argument("--offline", action="store_true", help="stored files only")
    p.add_argument("--scratch", action="store_true", help="write to data/scratch/ (never gold-set eligible)")
    p.add_argument("--daytime-ok", action="store_true", help="allow large NCBI jobs on weekday daytime")
    p.add_argument("--verbose", action="store_true")
    return p


def build_parser():
    c = _common()
    ap = argparse.ArgumentParser(prog="aegir_ran", description="RAN: the AEGIR fetcher")
    g = ap.add_subparsers(dest="group", required=True)

    def leaf(sub, name, fn, **kw):
        p = sub.add_parser(name, parents=[c], **kw)
        p.set_defaults(func=fn, label=name if sub.dest == "group" else f"{sub.dest} {name}")
        return p

    ct = g.add_parser("ctgov").add_subparsers(dest="ctgov", required=True)
    p = leaf(ct, "search", lambda x, a: ctgov.search(x, a.query_id, _params(a.param)))
    p.add_argument("--query-id")
    p.add_argument("--param", action="append", help="exploratory key=value (forces --scratch)")
    leaf(ct, "study", lambda x, a: ctgov.study(x, a.ncts)).add_argument("ncts", nargs="+")
    leaf(ct, "import-history", lambda x, a: ctgov.import_history(x, a.files)).add_argument("files", nargs="+")
    p = leaf(ct, "history", lambda x, a: ctgov.history(x, a.ncts, a.versions))
    p.add_argument("ncts", nargs="+")
    p.add_argument("--versions", choices=["index", "all", "window"], default="window")

    pm = g.add_parser("pubmed").add_subparsers(dest="pubmed", required=True)
    p = leaf(pm, "search", lambda x, a: pubmed.search(x, a.query_id, a.term))
    p.add_argument("--query-id")
    p.add_argument("--term", help="exploratory term (forces --scratch)")
    leaf(pm, "fetch", lambda x, a: pubmed.fetch(x, a.pmids)).add_argument("pmids", nargs="+")

    pc = g.add_parser("pmc").add_subparsers(dest="pmc", required=True)
    leaf(pc, "licence", lambda x, a: pmc.licence(x, a.pmcids)).add_argument("pmcids", nargs="+")
    leaf(pc, "fulltext", lambda x, a: pmc.fulltext(x, a.pmcids)).add_argument("pmcids", nargs="+")

    lk = g.add_parser("link").add_subparsers(dest="link", required=True)
    leaf(lk, "from-registry", lambda x, a: link.from_registry(x, a.ncts)).add_argument("ncts", nargs="+")
    leaf(lk, "from-pubmed", lambda x, a: link.from_pubmed(x, a.pmids)).add_argument("pmids", nargs="+")

    dv = g.add_parser("derive").add_subparsers(dest="derive", required=True)
    for name, fn in (("label-flags", derive.label_flags), ("flags", derive.label_flags),
                     ("content-flags", derive.content_flags)):
        leaf(dv, name, lambda x, a, fn=fn: fn(x, a.pool)).add_argument("--pool", required=True)
    p = leaf(dv, "diff", lambda x, a: derive.diff(x, a.nct, a.from_version, a.to_version))
    p.add_argument("nct")
    p.add_argument("--from", dest="from_version", type=int, required=True)
    p.add_argument("--to", dest="to_version", type=int, required=True)

    ep = g.add_parser("epmc").add_subparsers(dest="epmc", required=True)
    p = leaf(ep, "licence", lambda x, a: epmc.licence(x, a.pmids, a.from_query))
    p.add_argument("pmids", nargs="*")
    p.add_argument("--from-query", help="PMIDs of a stored pubmed search")

    lb = g.add_parser("labels").add_subparsers(dest="labels", required=True)
    p = leaf(lb, "build-batch", lambda x, a: batches.build_batch(x, a.source, a.positives, a.negatives, a.seed,
                                                                a.name, a.synthetic))
    p.add_argument("--from", dest="source", help="content-flags JSON file")
    p.add_argument("--positives", type=int, default=50)
    p.add_argument("--negatives", type=int, default=50)
    p.add_argument("--seed", type=int, default=28)
    p.add_argument("--name")
    p.add_argument("--synthetic", type=int, default=0, help="N synthetic cases for testing the tool")
    p = leaf(lb, "audit", lambda x, a: batches.audit(x, a.batches))
    p.add_argument("batches", nargs="+", help="batch names or files")
    p = leaf(lb, "serve", lambda x, a: labels.serve(x, a.labeller, a.batch, a.port, not a.no_browser))
    p.add_argument("--labeller", required=True)
    p.add_argument("--batch", help="batch name or file (default: newest)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")

    rp = g.add_parser("report").add_subparsers(dest="report", required=True)
    leaf(rp, "efficiency", lambda x, a: reports.efficiency(x))
    p = leaf(rp, "log-minutes", lambda x, a: reports.log_minutes(x, a.track, a.minutes, a.note))
    p.add_argument("--track", type=int, required=True)
    p.add_argument("--minutes", type=float, required=True)
    p.add_argument("--note", default="")

    leaf(g, "grade", lambda x, a: pmc.regrade(x), help="recompute licence grades")
    leaf(g, "tally", lambda x, a: reports.tally(x))
    p = leaf(g, "status", lambda x, a: reports.status(x, a.check_key))
    p.add_argument("--check-key", action="store_true")
    leaf(g, "attribution", lambda x, a: reports.attribution(x))
    p = leaf(g, "snapshot", lambda x, a: reports.snapshot(x, a.id, a.from_query))
    p.add_argument("--id", required=True)
    p.add_argument("--from", dest="from_query", required=True, metavar="QUERY_ID")
    return ap


def _pause():
    try:
        input(NL + "Press Enter to close this window...")
    except (EOFError, KeyboardInterrupt):
        pass


def interactive():
    """Double-click / no-argument start: ask who is labelling and open the labelling tool."""
    from pathlib import Path
    from .core import find_root
    from .labels import safe_name
    root = find_root()
    print("RAN labelling tool" + NL)
    batches = sorted((root / "data" / "labels" / "batches").glob("*.json"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if not batches:
        print("No batch found in data/labels/batches. Ask design to build one, or run:" + NL
              + "  RAN.exe labels build-batch --from <content_flags file> --name <name>")
        return 1
    batch = batches[0]
    if len(batches) > 1:
        for i, b in enumerate(batches, 1):
            print(f"  {i}. {b.stem}")
        pick = input(f"Batch number [1 = {batches[0].stem}]: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(batches):
            batch = batches[int(pick) - 1]
    last = root / "state" / "last_labeller.txt"
    default = last.read_text(encoding="utf-8").strip() if last.is_file() else ""
    while True:
        name = input(f"Your name (letters, digits, - or _){' [' + default + ']' if default else ''}: ").strip() or default
        try:
            safe_name(name)
            break
        except ValueError as e:
            print(e)
    last.parent.mkdir(parents=True, exist_ok=True)
    last.write_text(name, encoding="utf-8")
    print(NL + "Starting. A browser tab opens; if not, open the address shown below." + NL)
    return main(["labels", "serve", "--labeller", name, "--batch", str(batch)])


def run(argv=None):
    """Entry point: no arguments starts the labelling tool; any crash is shown and logged, not lost."""
    import sys
    import traceback
    argv = sys.argv[1:] if argv is None else argv
    try:
        if not argv:
            code = interactive()
            _pause()
            return code
        return main(argv)
    except SystemExit:
        raise
    except Exception:
        from .core import find_root, iso_now
        tb = traceback.format_exc()
        print(tb)
        try:
            with open(find_root() / "RAN-error.log", "a", encoding="utf-8") as f:
                f.write(f"--- {iso_now()} argv={argv}" + NL + tb + NL)
            print("This was also written to RAN-error.log next to RAN.exe.")
        except OSError:
            pass
        if not argv:
            _pause()
        return 1


def main(argv=None):
    args = build_parser().parse_args(argv)
    ctx = Ctx(dry_run=args.dry_run, offline=args.offline, refresh=args.refresh, scratch=args.scratch,
              max_requests=args.max_requests, daytime_ok=args.daytime_ok, verbose=args.verbose,
              max_items=args.max_items)
    code = 0
    try:
        args.func(ctx, args)
    except BudgetExceeded as e:
        ctx.error(str(e))
        ctx.notes["stopped"] = "budget"
        ctx.notes["estimate"] = f"{ctx.client.used} requests used before stopping"
        code = 2
    except WindowRefused as e:
        ctx.error(str(e))
        ctx.notes["stopped"] = "ncbi_window"
        code = 2
    except HostBlocked as e:
        ctx.error(f"host not on the network allowlist: {e}")
        code = 1
    except (FileNotFoundError, ValueError) as e:
        ctx.error(str(e))
        code = 1
    if ctx.errors and code == 0:
        code = 1
    print(json.dumps(ctx.summary(args.label), ensure_ascii=False))
    return code
