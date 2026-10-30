"""`autoran serve`: dashboard, findings browser, trial inspector and supervisor review tools. 127.0.0.1 only, Host-checked, stdlib."""
import json
import random
import threading
import webbrowser
from collections import Counter, OrderedDict, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__, audit, labeller as L, stats
from .core import Paths, iter_jsonl, read_gz_json
from .metrics import load_metrics
from .opentargets import normalise_reason
from .scorers import Logistic, input_view, load_scores
from .ui import HTML

F = dict(nct=0, title=1, status=2, klass=3, stop=4, src=5, conf=6, dis=7, phase=8, areas=9, year=10, sponsor=11, region=12,
         state=13, reg=14, split=15, why=16, span=17, rules=18, enr=19, page=20, pos=21, sites=22, crit=23)
CANARY_EVERY = 12


class State:
    def __init__(self, ctx, cfg, labeller):
        self.ctx, self.cfg, self.labeller = ctx, cfg, labeller
        self.paths = Paths(ctx.root).ensure()
        f = self.paths.latest("index_*.jsonl")
        self.empty = not f                       # first run: nothing fetched yet; the app still opens (Settings, Run, About)
        self.rows = list(iter_jsonl(f)) if f else []
        self.by_nct = {r[0]: i for i, r in enumerate(self.rows)}
        self.metrics = load_metrics(self.paths)
        self.scores = load_scores(self.paths)
        self.models = {}
        for name in ("logistic", "logistic_text"):
            mf = sorted(self.paths.derived.glob(f"model_{name}_*.json"))
            if mf:
                self.models[name] = Logistic.load(json.loads(mf[-1].read_text(encoding="utf-8")))
        from .jobs import Jobs
        self.stale = False
        self.jobs = Jobs(on_done=lambda job: setattr(self, 'stale', True))
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.canary_truth = {}
        self.refresh_audit()
        self.rule_idx = defaultdict(list)
        for i, r in enumerate(self.rows):
            for rid in r[F["rules"]]:
                self.rule_idx[rid].append(i)

    def refresh_audit(self):
        self.audited = audit.checked(self.paths, self.labeller)

    def page(self, rel):
        with self.lock:
            if rel in self.cache:
                self.cache.move_to_end(rel)
                return self.cache[rel]
        data = read_gz_json(self.ctx.root / rel)
        with self.lock:
            self.cache[rel] = data
            while len(self.cache) > 3:
                self.cache.popitem(last=False)
        return data

    # -- queries ---------------------------------------------------------------------------
    def facets(self):
        cov = self.metrics["coverage"] if self.metrics else {}
        f = {k: list(v.keys()) for k, v in cov.items()}
        f["split"] = ["train", "dev", "test"]
        f["scorers"] = sorted(self.scores)
        return f

    def match(self, q):
        """Indices of rows matching the filters in the query dict (values are lists of strings)."""
        def one(k):
            v = q.get(k)
            return v[0] if v else None
        klass, stop, area, phase = one("class"), one("stop_class"), one("area"), one("phase")
        state, region, sponsor, src, status = one("input_state"), one("region"), one("sponsor_class"), one("label_source"), one("status")
        reg, split, text = one("registration"), one("split"), (one("q") or "").lower().strip()
        dis, audited, conf_lt = one("disagree"), one("audited"), one("conf_lt")
        year_from, year_to = one("year_from"), one("year_to")
        yf = int(year_from) if year_from else None
        yt = int(year_to) if year_to else None
        cl = int(float(conf_lt) * 1000) if conf_lt else None
        out = []
        for i, r in enumerate(self.rows):
            if klass and r[3] != klass:
                continue
            if stop and r[4] != stop:
                continue
            if area and area not in r[9]:
                continue
            if phase and r[8] != phase:
                continue
            if state and r[13] != state:
                continue
            if region and r[12] != region:
                continue
            if sponsor and r[11] != sponsor:
                continue
            if src and r[5] != src:
                continue
            if status and r[2] != status:
                continue
            if reg and r[14] != reg:
                continue
            if split and r[15] != split:
                continue
            if dis == "1" and not r[7]:
                continue
            if cl is not None and (r[6] >= cl or r[2] != "TERMINATED"):
                continue
            if yf is not None and (r[10] is None or r[10] < yf):
                continue
            if yt is not None and (r[10] is None or r[10] > yt):
                continue
            if audited == "1" and r[0] not in self.audited:
                continue
            if audited == "0" and r[0] in self.audited:
                continue
            if text and text not in r[1].lower() and text not in r[16].lower() and text != r[0].lower():
                continue
            out.append(i)
        return out

    def row_json(self, r, with_scores=True):
        d = {"nct": r[0], "title": r[1], "status": r[2], "class": r[3], "stop_class": r[4], "label_source": r[5], "conf": r[6] / 1000,
             "disagree": bool(r[7]), "phase": r[8], "areas": r[9], "year": r[10], "sponsor_class": r[11], "region": r[12],
             "input_state": r[13], "registration": r[14], "split": r[15], "why_stopped": r[16], "span": r[17], "rules": r[18],
             "enrollment": r[19], "sites": r[22], "criteria": r[23], "audit": (self.audited.get(r[0]) or {}).get("verdict")}
        if with_scores:
            d["scores"] = {k: round(v[r[0]], 4) for k, v in self.scores.items() if r[0] in v}
        d["evidence"] = None
        if r[17] and r[16]:
            txt = L.fix_typos(normalise_reason(r[16]))
            if r[17][1] <= len(txt):
                d["evidence"] = txt[r[17][0]:r[17][1]]
        return d

    def trials(self, q, page=0, size=50):
        idx = self.match(q)
        sort = (q.get("sort") or [""])[0]
        if sort in self.scores:
            sc = self.scores[sort]
            idx.sort(key=lambda i: -sc.get(self.rows[i][0], -1))
        elif sort == "conf":
            idx.sort(key=lambda i: self.rows[i][6])
        elif sort == "year":
            idx.sort(key=lambda i: -(self.rows[i][10] or 0))
        part = idx[page * size:(page + 1) * size]
        return {"total": len(idx), "page": page, "size": size, "rows": [self.row_json(self.rows[i]) for i in part]}

    def trial(self, nct):
        i = self.by_nct.get(nct)
        if i is None:
            return None
        r = self.rows[i]
        study = self.page(r[20])["studies"][r[21]]
        ps = study.get("protocolSection", {})
        from .normalise import normalise_study
        rec = normalise_study(study, r[20], r[21], {})
        view = input_view(rec)
        explain = {n: m.explain(view) for n, m in self.models.items()}
        el = ps.get("eligibilityModule", {})
        d = self.row_json(r)
        d.update({"eligibility_text": el.get("eligibilityCriteria") or "", "conditions": rec["conditions"], "mesh": rec["mesh"], "sponsor": rec["sponsor"],
                  "dates": {k: rec[k] for k in ("start", "primary_completion", "completion", "first_posted", "last_update")},
                  "countries": rec["countries"], "n_primary": rec["n_primary"], "n_arms": rec["n_arms"], "allocation": rec["allocation"],
                  "masking": rec["masking"], "intervention_types": rec["intervention_types"], "enrollment_info": rec["enrollment"],
                  "elig": rec["eligibility"], "pmids": rec["pmids"], "explain": explain,
                  "provenance": {"page": r[20], "pos": r[21], "grade": "A+", "source": "ClinicalTrials.gov API v2 (current record)",
                                 "data_timestamp": (self.metrics or {}).get("pipeline", {}).get("data_timestamp")},
                  "links": {"study": f"https://clinicaltrials.gov/study/{nct}", "history": f"https://clinicaltrials.gov/study/{nct}?tab=history"},
                  "caveats": self.caveats(r)})
        return d

    def caveats(self, r):
        c = []
        if r[13] == "current":
            c.append("Current record: it may include changes made after the trial started (hindsight).")
        if r[13] == "never_updated":
            c.append("Never updated after first posting, so this is the first submission. Such trials tend to be small and simple.")
        if r[14] == "retrospective":
            c.append("Registered after the start date.")
        if r[3] == "negative_completed":
            c.append("Completed. The original planned enrolment is not kept once the actual figure is posted, so under-enrolment cannot be seen here.")
        if r[7]:
            c.append("Rules and the text model disagree about this stop reason.")
        return c

    # -- supervisor sheets --------------------------------------------------------------------
    def sheet(self, q):
        src = (q.get("source") or ["random"])[0]
        n = int((q.get("n") or ["24"])[0])
        seed = int((q.get("seed") or [str(random.randrange(10 ** 6))])[0])
        klass = (q.get("class") or ["positive_recruitment"])[0]
        skip_done = (q.get("fresh") or ["1"])[0] == "1"
        rnd = random.Random(seed)
        if src == "rule":
            pool = list(self.rule_idx.get((q.get("rule") or [""])[0], []))
        elif src == "disagree":
            pool = [i for i, r in enumerate(self.rows) if r[7]]
        elif src == "uncertain":
            pool = [i for i, r in enumerate(self.rows) if r[3] == klass and r[2] == "TERMINATED" and r[5] != "exact"]
            pool.sort(key=lambda i: self.rows[i][6])
            pool = pool[:max(n * 20, 400)]
        elif src == "suspect_negative":
            pool = [i for i, r in enumerate(self.rows) if r[3] == "negative_completed" and r[19] is not None and r[19] <= 5 and r[8] in ("Phase 2", "Phase 2/3", "Phase 3")]
        else:
            pool = [i for i, r in enumerate(self.rows) if r[3] == klass]
        if skip_done:
            pool = [i for i in pool if self.rows[i][0] not in self.audited]
        rnd.shuffle(pool)
        pick = pool[:n]
        cards = [self.row_json(self.rows[i], with_scores=False) for i in pick]
        cn = max(1, n // CANARY_EVERY) if (q.get("canary") or ["1"])[0] == "1" and len(cards) >= CANARY_EVERY else 0
        if cn:
            can = audit.canaries(self.paths, cn, seed)
            for k, cc in enumerate(can):
                self.canary_truth[cc["nct"]] = cc["true_labels"]
                host = None
                while host is None:                       # a random real terminated trial lends its title, phase and areas
                    cand = self.rows[rnd.randrange(len(self.rows))]
                    host = cand if cand[2] == "TERMINATED" else None
                cards.insert(min(len(cards), (k + 1) * CANARY_EVERY - 1 - k), {
                    "nct": cc["nct"], "title": host[1], "status": "TERMINATED", "class": "other_stop", "stop_class": cc["stop_class"],
                    "why_stopped": cc["why_stopped"], "label_source": "rules", "conf": 0.9, "span": None, "rules": [], "phase": host[8],
                    "areas": host[9], "year": host[10], "enrollment": None, "disagree": False, "audit": None, "evidence": None})
        return {"source": src, "class": klass, "seed": seed, "population": len(pool), "cards": cards,
                "question": QUESTIONS.get(klass, "Is the label right?")}

    def submit(self, body):
        verdicts = body.get("cards", [])
        klass, src = body.get("class"), body.get("source")
        sec = float(body.get("seconds") or 0)
        canary_n = canary_ok = 0
        by_rule = defaultdict(lambda: [0, 0])
        real = 0
        for c in verdicts:
            if c["nct"] in self.canary_truth:
                canary_n += 1
                canary_ok += c["verdict"] == "disagree"
                continue
            i = self.by_nct.get(c["nct"])
            if i is None:
                continue
            r = self.rows[i]
            audit.append(self.paths, self.labeller, {"kind": "trial", "nct_id": c["nct"], "class": r[3], "stop_class": r[4], "verdict": c["verdict"],
                                                      "note": c.get("note", ""), "mode": "sheet" if len(verdicts) > 1 else "single",
                                                      "labeller_file": None, "autoran_version": __version__})
            real += 1
            if src == "rule":
                for rid in r[18]:
                    if rid == body.get("rule"):
                        by_rule[rid][0] += c["verdict"] in ("agree", "disagree")
                        by_rule[rid][1] += c["verdict"] == "agree"
        for rid, (k, a) in by_rule.items():
            audit.append(self.paths, self.labeller, {"kind": "rule", "rule_id": rid, "n_checked": k, "n_agree": a})
        audit.append(self.paths, self.labeller, {"kind": "sheet", "source": src, "class": klass, "n": real, "flagged": sum(1 for c in verdicts if c["verdict"] == "disagree" and c["nct"] not in self.canary_truth),
                                                  "seconds": round(sec, 1), "canaries": canary_n, "canaries_caught": canary_ok})
        self.refresh_audit()
        return {"ok": True, "recorded": real, "canaries": canary_n, "canaries_caught": canary_ok}

    def audit_summary(self):
        trial = Counter()
        per = defaultdict(Counter)
        sheets, secs, ncards, can, caught = 0, 0.0, 0, 0, 0
        d = self.paths.data / "labels"
        for f in sorted(d.glob("*/autoran_audit.jsonl")) if d.is_dir() else []:
            latest = {}
            for r in iter_jsonl(f):
                if r.get("kind") == "trial":
                    latest[r["nct_id"]] = r
                elif r.get("kind") == "sheet":
                    sheets += 1
                    secs += r["seconds"]
                    ncards += r["n"]
                    can += r["canaries"]
                    caught += r["canaries_caught"]
            for r in latest.values():
                per[r["class"]][r["verdict"]] += 1
        out = {}
        for k, c in per.items():
            kk, n = c["agree"], c["agree"] + c["disagree"]
            lo, hi = stats.wilson(kk, n)
            out[k] = {"agree": c["agree"], "disagree": c["disagree"], "unsure": c["unsure"], "n": n, "p": round(kk / n, 4) if n else None,
                      "lo": lo, "hi": hi, "half_width": round((hi - lo) / 2, 4) if n else None}
        return {"per_class": out, "sheets": sheets, "cards": ncards, "seconds": round(secs, 1),
                "seconds_per_card": round(secs / ncards, 1) if ncards else None, "canaries": can, "canaries_caught": caught,
                "canary_catch_rate": round(caught / can, 3) if can else None}

    def rules(self):
        m = (self.metrics or {}).get("labeller") or {}
        counts = (self.metrics or {}).get("rule_counts", {})
        reviews = (self.metrics or {}).get("rule_review", {})
        out = []
        for rid, v in (m.get("rule_table") or {}).items():
            rv = reviews.get(rid)
            real = None
            if rv and rv.get("n_checked"):
                lo, hi = stats.wilson(rv["n_agree"], rv["n_checked"])
                real = {"n": rv["n_checked"], "p": round(rv["n_agree"] / rv["n_checked"], 3), "lo": lo, "hi": hi}
            out.append({"rule_id": rid, "class": v["class"], "weight": v["weight"], "curated_fired": v["fired"], "curated_precision": v["precision"],
                        "registry_fired": counts.get(rid, 0), "registry_review": real})
        return sorted(out, key=lambda x: -x["registry_fired"])


QUESTIONS = {"positive_recruitment": "Did this trial stop because it could not recruit enough participants?",
             "other_stop": "Is the stop reason class right (and is it NOT a recruitment failure)?",
             "unlabelled": "Is 'no usable stop reason' right? (Could a person tell why it stopped?)",
             "negative_completed": "Is this a normal completion (not a hidden under-enrolment)?"}


def gpu_info():
    try:
        from . import gpu
        return gpu.info()
    except BaseException as e:                # SystemExit when PyTorch is missing
        return {"cuda_available": False, "torch": None, "note": str(e)[:160]}


def dispatch(state, method, path, q, body):
    """One routing table for both front ends (the desktop window and the optional local web server). Returns (status, json-able payload)."""
    try:
        if method == "GET":
            if path == "/api/metrics":
                return 200, state.metrics or {}
            if path == "/api/facets":
                return 200, state.facets()
            if path == "/api/trials":
                return 200, state.trials(q, int((q.get("page") or ["0"])[0]))
            if path.startswith("/api/trial/"):
                d = state.trial(path.rsplit("/", 1)[1])
                return (200, d) if d else (404, {"error": "not found"})
            if path == "/api/sheet":
                return 200, state.sheet(q)
            if path == "/api/audit-summary":
                return 200, state.audit_summary()
            if path == "/api/rules":
                return 200, state.rules()
            if path == "/api/about":
                return 200, {"version": __version__, "labeller": state.labeller, "sources": state.cfg["sources"], "scope": state.cfg["scope"],
                             "grade_floor": state.cfg["grade_floor"]}
            if path == "/api/plots":
                from . import plots
                return 200, plots.listing(state.ctx.root)
            if path == "/api/plot":
                from . import plots
                return 200, plots.render(state.ctx.root, state.metrics, (q.get("name") or [""])[0], (q.get("device") or ["auto"])[0])
            if path == "/api/jobs":
                return 200, state.jobs.status()
            if path == "/api/gpu":
                return 200, gpu_info()
            if path == "/api/status":              # browser mode; the desktop window answers this itself
                return 200, {"ready": True, "empty": state.empty, "error": None, "message": "", "seconds": 0, "stale": state.stale,
                             "jobs_running": state.jobs.running()}
            if path == "/api/settings":
                from . import settings, core
                out = settings.public()
                out.update(active_workspace=str(core.ROOT), program_folder=str(core.CODE_ROOT), user_agent=settings.user_agent())
                return 200, out
        else:
            if path == "/api/settings":
                from . import settings
                return 200, settings.save(body)
            if path == "/api/submit":
                return 200, state.submit(body)
            if path == "/api/run":
                return 200, state.jobs.start(body["stage"], body.get("device", "auto"))
            if path == "/api/open":                # the only URLs the app will hand to the system browser
                url = str(body.get("url", ""))
                if (urlsplit(url).hostname or "") not in ("clinicaltrials.gov", "www.clinicaltrials.gov") or not url.startswith("https://"):
                    raise ValueError("only https://clinicaltrials.gov links can be opened")
                webbrowser.open(url)
                return 200, {"ok": True}
    except (ValueError, KeyError, FileNotFoundError) as e:
        return 400, {"error": str(e)}
    return 404, {"error": "not found"}


def make_handler(state):
    class H(BaseHTTPRequestHandler):
        server_version = "autoran"

        def log_message(self, *a):
            pass

        def _ok_host(self):
            return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=True).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._ok_host():
                return self._send(403, {"error": "host"})
            u = urlsplit(self.path)
            if u.path == "/":
                return self._send(200, HTML.encode("utf-8"), "text/html")
            code, obj = dispatch(state, "GET", u.path, parse_qs(u.query), None)
            self._send(code, obj)

        def do_POST(self):
            if not self._ok_host():
                return self._send(403, {"error": "host"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            code, obj = dispatch(state, "POST", urlsplit(self.path).path, {}, body)
            self._send(code, obj)
    return H


def serve(ctx, cfg, port=8780, labeller="supervisor", open_browser=True):
    from .labeller import CLASSES  # noqa: F401
    state = State(ctx, cfg, labeller)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    import sys
    print(f"AutoRAN dashboard at {url}  ({len(state.rows):,} trials; Ctrl+C to stop)", file=sys.stderr)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return {"url": url}
