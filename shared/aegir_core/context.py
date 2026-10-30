"""Run context shared by all commands: config, store, client, summary."""
import sys
from pathlib import Path

from .core import Store, bundled, find_root, load_json, shared_config
from .http import Client


class Ctx:
    def __init__(self, root=None, *, dry_run=False, offline=False, refresh=False, scratch=False,
                 max_requests=None, daytime_ok=False, verbose=False, max_items=None, sleep=None):
        self.root = find_root() if root is None else Path(root)
        self.cfg = self._conf("aegir.json")
        self.grades = self._conf("grades.json")
        self.dry_run, self.offline, self.refresh = dry_run, offline, refresh
        self.verbose, self.max_items, self.daytime_ok = verbose, max_items, daytime_ok
        self.store = Store(self.root, scratch=scratch, dry_run=dry_run)
        self.max_requests = max_requests if max_requests is not None else self.cfg.get("default_max_requests", 500)
        self.client = Client(self, sleep=sleep)
        self.counts, self.errors, self.notes = {}, [], {}
        self.cache = {}

    def _conf(self, name):
        """The tool's own config/ wins; then the shared one (shared/config/); then the copy bundled in a frozen exe."""
        d = load_json(self.root / "config" / name)
        if d is None and shared_config(name):
            d = load_json(shared_config(name))
        if d is None and bundled(name):
            d = load_json(bundled(name))
        return d or {}

    def count(self, name, n=1):
        self.counts[name] = self.counts.get(name, 0) + n

    def error(self, msg):
        self.errors.append(str(msg))

    def log(self, msg):
        if self.verbose:
            print(msg, file=sys.stderr)

    def limit(self, items):
        items = list(items)
        return items[: self.max_items] if self.max_items else items

    def query(self, query_id, source):
        q = load_json(self.root / "config" / "queries" / f"{query_id}.json")
        if q is None:
            raise FileNotFoundError(
                f"no named query config/queries/{query_id}.json (gold-set pulls need a named query)")
        if q.get("source") != source:
            raise ValueError(f"query {query_id} has source {q.get('source')!r}, expected {source!r}")
        return q

    def summary(self, command):
        return {
            "command": command,
            "ok": not self.errors,
            "dry_run": self.dry_run,
            "scratch": self.store.scratch,
            "counts": self.counts,
            "files_written": self.store.files_written,
            "requests_used": self.client.used,
            "planned_requests": self.client.planned_count if self.dry_run else None,
            "errors": self.errors[:20],
            **({"notes": self.notes} if self.notes else {}),
        }


def make_ctx(**kw):
    return Ctx(**kw)
