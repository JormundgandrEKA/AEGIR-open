"""Command line: python -m autoran <command>. Every command ends with one JSON summary line."""
import argparse
import json
import sys

from . import __version__
from . import core
from aegir_core.http import BudgetExceeded, HostBlocked, WindowRefused


def _common():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--dry-run", action="store_true", help="show the first request and an estimate; fetch nothing")
    p.add_argument("--max-requests", type=int, help="request budget (default 500)")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto",
                   help="where the heavy maths runs: auto uses the GPU when PyTorch and CUDA are available (needs PyTorch; see the README)")
    return p


def build_parser():
    c = _common()
    ap = argparse.ArgumentParser(prog="autoran", description="AutoRAN: automatic labelling of recruitment failure (the silver set)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def leaf(name, **kw):
        return sub.add_parser(name, parents=[c], **kw)

    p = sub.add_parser("settings", help="show or change your per-user settings (workspace, RAN folder, contact email, optional tokens)")
    p.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                   help="names: workspace, history_dir, gpu_site, contact_email, hf_token, ncbi_api_key; an empty value clears it")
    p = leaf("fetch", help="page the ClinicalTrials.gov API (resumable)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--full", action="store_true", help="the whole scope (default)")
    g.add_argument("--delta", action="store_true", help="only records updated since the last finished run")
    p.add_argument("--new", action="store_true", help="start a new run instead of resuming")
    p.add_argument("--max-pages", type=int)
    leaf("labeller-data", help="download the Open Targets curated stop reasons")
    p = leaf("normalise", help="pages to one compact record per trial, with input_state")
    p.add_argument("--partial", action="store_true", help="also accept an unfinished fetch (to try the pipeline on a few pages)")
    leaf("label", help="stop-reason labeller and outcome classes")
    leaf("categorize", help="categories, frozen splits")
    p = leaf("score", help="run scorers on the splits")
    p.add_argument("--scorer", action="append", help="name (default: all)")
    leaf("metrics", help="recompute every metric")
    p = leaf("serve", help="dashboard and inspector on 127.0.0.1")
    p.add_argument("--port", type=int, default=8780)
    p.add_argument("--labeller", default="supervisor")
    p.add_argument("--no-browser", action="store_true")
    p = leaf("audit-sample", help="draw a seeded sample for human spot-checks")
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--class", dest="klass", default="positive_recruitment")
    p.add_argument("--seed", type=int, default=28)
    p = leaf("export", help="silver-set file with licence manifest")
    p.add_argument("--grade-floor")
    leaf("run", help="fetch delta, then label, categorize, score, metrics")
    leaf("status", help="what exists")
    leaf("gpu-info", help="PyTorch, CUDA and the GPU as AutoRAN sees them")
    leaf("frame", help="every trial, label, category and score as one Parquet file for pandas, plots or R")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "settings":
        from . import settings
        try:
            changes = dict(kv.split("=", 1) for kv in args.set)
            print(json.dumps(settings.save(changes) if changes else settings.public(), indent=2))
            return 0
        except ValueError as e:
            print(f"settings: {e}", file=sys.stderr)
            return 1
    ctx = core.make_ctx(dry_run=args.dry_run, offline=args.offline, refresh=args.refresh, verbose=args.verbose,
                        max_requests=args.max_requests)
    cfg = core.load_cfg()
    code = 0
    try:
        from . import commands
        result = commands.run(args.cmd, ctx, cfg, args)
    except BudgetExceeded as e:
        ctx.error(str(e)); ctx.notes["stopped"] = "budget"; result, code = {}, 2
    except WindowRefused as e:
        ctx.error(str(e)); code, result = 2, {}
    except HostBlocked as e:
        ctx.error(f"host not on the network allowlist: {e}"); code, result = 1, {}
    except (FileNotFoundError, ValueError) as e:
        ctx.error(str(e)); code, result = 1, {}
    if ctx.errors and code == 0:
        code = 1
    s = ctx.summary(f"autoran {args.cmd}")
    s["result"] = result
    print(json.dumps(s, ensure_ascii=False, default=str))
    return code


if __name__ == "__main__":
    sys.exit(main())
