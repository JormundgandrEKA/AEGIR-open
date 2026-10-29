"""Labelling tool: the local web app (stdlib http.server, 127.0.0.1 only). Batches are built in batches.py."""
import json
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .batches import build_batch, labels_dir  # noqa: F401  (build_batch re-exported for the CLI)
from .core import demo_batch_path, iso_now, read_jsonl, utc_stamp
from .labels_ui import HTML
from .taxonomy import AVOID_VALUE, CAUSES, CHANGE_ENUM, LABEL, SEVERITY, page_defs

SCHEMA = "gold-label/0.1"
CAUSE_IDS = {c[0] for c in CAUSES}
SEVERITY_IDS = {s[0] for s in SEVERITY}


def safe_name(name):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name or ""):
        raise ValueError("labeller must be 1-40 letters, digits, - or _")
    return name


class Session:
    def __init__(self, ctx, labeller, batch_path):
        self.ctx, self.labeller = ctx, safe_name(labeller)
        self.batch = json.loads(batch_path.read_text(encoding="utf-8"))
        self.cases = {c["case_id"]: c for c in self.batch["cases"]}
        # demo sessions are kept apart so they never mix with real labels in data/labels/;
        # where they go is the "demo_output_dir" setting (default data/demo)
        base = (ctx.root / ctx.cfg.get("demo_output_dir", "data/demo") if self.batch.get("name") == "ran-demo"
                else labels_dir(ctx))
        self.dir = base / self.labeller
        (self.dir / "sessions").mkdir(parents=True, exist_ok=True)
        self.labels_file = self.dir / "labels.jsonl"
        self.session_file = self.dir / "sessions" / f"{utc_stamp()}.jsonl"
        self.lock = threading.Lock()
        self.revealed = set()
        self.stats = {"saved": 0, "skipped": 0, "notes": 0, "active_seconds": 0.0}
        self.event({"type": "session_start", "batch": self.batch["name"], "labeller": self.labeller,
                    "hidden_by_design": [c["case_id"] for c in self.batch["cases"]
                                         if c["provisional_mode"] != "collapsed"]})

    def _append(self, path, rec):
        with self.lock, open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def event(self, rec):
        rec = dict(rec)
        rec["server_ts"] = iso_now()
        self._append(self.session_file, rec)

    def public_case(self, c):
        return {k: v for k, v in c.items() if k not in ("provisional", "_design")}

    def state(self):
        done, drafts = {}, {}
        for r in read_jsonl(self.labels_file):
            if r.get("batch") == self.batch["name"]:
                done[r["case_id"]] = {
                    "real_change": r.get("real_change"),
                    "change_types": r.get("change_types") or ([r["change_type_ui"]] if r.get("change_type_ui") else []),
                    "avoidable": r.get("avoidable_level") or r.get("avoidable_ui"), "cause": r.get("cause") or [],
                    "severity": r.get("severity_ui") if r.get("severity_ui") else r.get("severity"),
                    "agree_with_provisional": r.get("agree_with_provisional"), "note": r.get("note")}
        for r in read_jsonl(self.dir / "drafts.jsonl"):
            if r.get("batch") == self.batch["name"] and r.get("case_id") not in done:
                drafts[r["case_id"]] = r["answers"]
        return {"labeller": self.labeller, "batch": self.batch["name"], "notepad": self.notepad_text(),
                "defs": page_defs(), "notice": self.batch.get("notice"), "cases": [self.public_case(c) for c in self.batch["cases"]],
                "done": done, "drafts": drafts}

    def draft_save(self, body):
        cid = body["case_id"]
        if cid in self.cases:
            self._append(self.dir / "drafts.jsonl", {"ts": iso_now(), "batch": self.batch["name"], "case_id": cid,
                                                     "answers": body.get("answers", {})})
        return {"ok": True}

    def notepad_text(self):
        rows = read_jsonl(self.dir / "notepad.jsonl")
        return rows[-1]["text"] if rows else ""

    def notepad_save(self, body):
        text = str(body.get("text", ""))[:200000]
        if text != self.notepad_text():
            self._append(self.dir / "notepad.jsonl", {"ts": iso_now(), "case_id": body.get("case_id"),
                                                      "labeller": self.labeller, "text": text})
            self.stats["notepad_chars"] = len(text)
        return {"ok": True}

    def reveal(self, cid):
        c = self.cases[cid]
        if c["provisional_mode"] != "collapsed":
            return {"hidden": True}
        self.revealed.add(cid)
        return c["provisional"]

    def save(self, body):
        cid = body["case_id"]
        c, a = self.cases[cid], body.get("answers", {})
        rc = a.get("real_change")
        if rc not in LABEL:
            raise ValueError("real_change required")
        cts = [x for x in (a.get("change_types") or []) if x in CHANGE_ENUM]
        substantive_types = [x for x in cts if not x.startswith("wording_")]
        if rc == "yes" and not substantive_types:
            raise ValueError("choose at least one change type from groups 2a-2c when the change is real")
        level = a.get("avoidable") if a.get("avoidable") in AVOID_VALUE else None
        shown = "hidden_by_design" if c["provisional_mode"] != "collapsed" else (cid in self.revealed)
        t = body.get("timing", {})
        main = (substantive_types or cts or [None])[0]
        rec = {
            "schema": SCHEMA, "id": c["nct_id"], "case_id": cid, "batch": self.batch["name"], "track": 1,
            "labeller": f"human:{self.labeller}", "provisional": False,
            "label": LABEL[rc], "real_change": rc,
            "change_type": CHANGE_ENUM.get(main), "change_types": cts,
            "change_types_enum": sorted({CHANGE_ENUM[x] for x in cts}),
            "avoidable": AVOID_VALUE.get(level, "unknown") if rc == "yes" else "unknown", "avoidable_level": level,
            "cause": [x for x in (a.get("cause") or []) if x in CAUSE_IDS],
            "severity": a.get("severity") if a.get("severity") in SEVERITY_IDS else "unknown",
            "agree_with_provisional": a.get("agree_with_provisional") if shown is True else None,
            "provisional_shown": shown,
            "evidence": [{"source": f"ctgov:v{c['a']['version']}->v{c['b']['version']}",
                          "location": c.get("focus"), "quote": c.get("evidence_quote", "")}],
            "reason_stated": None, "note": (a.get("note") or "")[:2000],
            "timing": {k: t.get(k) for k in ("shown_at", "first_input_at", "provisional_revealed_at", "saved_at",
                                             "active_seconds", "answer_changes", "full_text_opened",
                                             "links_opened")},
            "labelled_at": iso_now()}
        self._append(self.labels_file, rec)
        self.stats["saved"] += 1
        self.stats["active_seconds"] += float(t.get("active_seconds") or 0)
        self.event({"type": "save", "case_id": cid, "active_seconds": t.get("active_seconds")})
        return {"ok": True}

    def summary(self):
        return {"command": "labels serve", "ok": True, "labeller": self.labeller, "batch": self.batch["name"],
                "cases_done": self.stats["saved"], "skipped": self.stats["skipped"],
                "notepad_chars": self.stats.get("notepad_chars", len(self.notepad_text())),
                "active_minutes": round(self.stats["active_seconds"] / 60, 1), "notes": self.stats["notes"],
                "labels_file": str(self.labels_file), "session_file": str(self.session_file)}


def make_handler(session, stop):
    class H(BaseHTTPRequestHandler):
        server_version = "ran-labels"

        def log_message(self, *a):
            pass

        def _host_ok(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "host"})
            if self.path == "/":
                return self._send(200, HTML.encode("utf-8"), "text/html")
            if self.path == "/api/state":
                return self._send(200, session.state())
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok():
                return self._send(403, {"error": "host"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                if self.path == "/api/event":
                    t = body.get("type")
                    if t == "note":
                        session.stats["notes"] += 1
                    if t == "skip":
                        session.stats["skipped"] += 1
                        session.stats["active_seconds"] += float(body.get("active_seconds") or 0)
                    session.event(body)
                    return self._send(200, {"ok": True})
                if self.path == "/api/notepad":
                    return self._send(200, session.notepad_save(body))
                if self.path == "/api/draft":
                    return self._send(200, session.draft_save(body))
                if self.path == "/api/reveal":
                    out = session.reveal(body["case_id"])
                    session.event({"type": "reveal", "case_id": body["case_id"], "t": body.get("t")})
                    return self._send(200, out)
                if self.path == "/api/save":
                    return self._send(200, session.save(body))
                if self.path == "/api/quit":
                    self._send(200, {"ok": True})
                    threading.Thread(target=stop, daemon=True).start()
                    return
            except (KeyError, ValueError) as e:
                return self._send(400, {"error": str(e)})
            self._send(404, {"error": "not found"})

    return H


def resolve_batch(ctx, batch):
    p = Path(batch)
    if p.is_file():
        return p
    q = labels_dir(ctx) / "batches" / (batch if batch.endswith(".json") else batch + ".json")
    if not q.is_file() and batch in ("demo", "ran-demo") and demo_batch_path():
        return demo_batch_path()                    # the bundled real-data demo (see demo/ATTRIBUTION.md)
    if not q.is_file():
        raise FileNotFoundError(f"batch not found: {batch}")
    return q


def serve(ctx, labeller, batch, port=8765, open_browser=True):
    if not batch:
        files = sorted((labels_dir(ctx) / "batches").glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not files and demo_batch_path():
            batch = "demo"
        elif not files:
            raise FileNotFoundError("no batch in data/labels/batches; run `labels build-batch` first")
        else:
            batch = str(files[-1])
    session = Session(ctx, labeller, resolve_batch(ctx, batch))
    holder = {}
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(session, lambda: holder["s"].shutdown()))
    holder["s"] = httpd
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    import sys
    print(f"RAN labelling tool at {url}  (Ctrl+C or the Finish key ends the session)", file=sys.stderr)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    session.event({"type": "session_end"})
    ctx.counts.update({"cases_done": session.stats["saved"], "skipped": session.stats["skipped"],
                       "notes": session.stats["notes"]})
    ctx.notes["active_minutes"] = round(session.stats["active_seconds"] / 60, 1)
    ctx.notes["labels_file"] = ctx.store.rel(session.labels_file)
