"""HTTP client: the request governor (shared limits, margin, cool-down), request budget, retries, key redaction."""
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .core import VERSION, iso_now, load_json, redact_params, redact_url, scrub, sha256, shared_state_dir
from .governor import Governor, Paused  # noqa: F401  (Paused is raised when a host is cooling down)

NCBI_HOSTS = {"eutils.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov"}


class BudgetExceeded(Exception):
    pass


class WindowRefused(Exception):
    pass


class HostBlocked(Exception):
    pass


class Response:
    def __init__(self, status, body, url, params, method, headers=None, duration_ms=0, error=None):
        self.status, self.body, self.url, self.params = status, body, url, params
        self.method, self.headers, self.duration_ms, self.error = method, headers or {}, duration_ms, error

    @property
    def ok(self):
        return self.error is None and self.status is not None and 200 <= self.status < 300

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    def meta(self, **extra):
        m = {"url": self.url, "params": self.params, "method": self.method, "retrieved_at": iso_now(),
             "http_status": self.status, "sha256": sha256(self.body), "bytes": len(self.body)}
        m.update(extra)
        return m


def load_ncbi_credentials(root):
    """Environment wins over config/ncbi.local.json. Values stay in memory; never printed."""
    key, email = os.environ.get("NCBI_API_KEY"), os.environ.get("NCBI_EMAIL")
    if not (key and email):
        f = load_json(root / "config" / "ncbi.local.json", {}) or {}
        key = key or f.get("api_key")
        email = email or f.get("email")
    return key or None, email or None


def eastern_now(now=None):
    now = now or datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("America/New_York"))
    except Exception:  # no tz database (plain Windows): assume standard time
        return now.astimezone(timezone(timedelta(hours=-5)))


def is_ncbi_daytime(now=None):
    """Weekday between 5 AM and 9 PM Eastern: NCBI asks large jobs to wait."""
    t = eastern_now(now)
    return t.weekday() < 5 and 5 <= t.hour < 21


class Client:
    def __init__(self, ctx, sleep=None):
        self.ctx = ctx
        self.sleep = sleep or time.sleep
        self.used = 0
        self.ncbi_used = 0
        self.planned = []
        self.planned_count = 0
        self.key, self.email = load_ncbi_credentials(ctx.root)
        self.tool = ctx.cfg.get("tool_name", "aegir-ran")
        self.blocked_hosts = set()
        # one governor for every host: margin, rolling quota, server signals, cool-down; its state is shared by all programs on this computer
        self._skew = 0.0                                 # a stubbed sleep (tests) advances a virtual clock instead of waiting
        self.gov = Governor(shared_state_dir() / "governor.json",
                            ctx.cfg.get("governor"), clock=self._clock, sleep=self._sleep, notify=self._notify,
                            has_token={h: bool(self.key) for h in NCBI_HOSTS})
        self.alerts = []

    def _clock(self):
        return time.time() + self._skew

    def _sleep(self, s):
        if self.sleep is time.sleep:
            time.sleep(s)
        else:
            self.sleep(s)
            self._skew += s

    def _notify(self, ev):
        if ev["level"] in ("warn", "error", "notice"):
            self.alerts.append(ev)
            self.ctx.notes.setdefault("alerts", []).append(f"{ev['level']}: {ev['text']}")

    # -- limits -------------------------------------------------------------
    def _check_budget(self, host):
        if self.used >= self.ctx.max_requests:
            raise BudgetExceeded(
                f"request budget {self.ctx.max_requests} reached; rerun with a higher --max-requests")
        if host in NCBI_HOSTS:
            thr = self.ctx.cfg.get("ncbi_daytime_threshold", 1000)
            if self.ncbi_used >= thr and not self.ctx.daytime_ok and is_ncbi_daytime():
                raise WindowRefused(
                    f"more than {thr} NCBI requests on a weekday between 5 AM and 9 PM Eastern; "
                    "run overnight or at a weekend, or pass --daytime-ok")

    def check_window(self, estimate):
        """Early refusal for a command whose estimate is already known."""
        thr = self.ctx.cfg.get("ncbi_daytime_threshold", 1000)
        if estimate > thr and not self.ctx.daytime_ok and not self.ctx.dry_run and is_ncbi_daytime():
            raise WindowRefused(
                f"estimated {estimate} NCBI requests on a weekday between 5 AM and 9 PM Eastern; "
                "run overnight or at a weekend, or pass --daytime-ok")

    # -- requests -------------------------------------------------------
    def log(self, resp, file=None):
        self.ctx.store.append("fetch_log.jsonl", {
            "ts": iso_now(), "url": resp.url, "status": resp.status, "file": file,
            "sha256": sha256(resp.body) if resp.body else None,
            "duration_ms": resp.duration_ms, "error": resp.error})

    def get(self, url, params=None, *, method="GET", data=None):
        """Return a Response, or None for --dry-run / --offline (nothing is sent).

        A successful response is logged by the caller via `log(resp, file=...)`
        once it knows where the body was stored; failures are logged here.
        """
        params = dict(params or {})
        host = urlsplit(url).hostname
        if host in NCBI_HOSTS:
            params["tool"] = self.tool
            if self.email:
                params["email"] = self.email
            if self.key:
                params["api_key"] = self.key
        query = urllib.parse.urlencode(params) if params else ""
        full = url + ("?" + query if query and data is None else "")
        shown = redact_url(full)
        if self.ctx.dry_run:
            self.planned_count += 1
            if len(self.planned) < 5:
                self.planned.append(shown)
            self.ctx.notes["first_planned_requests"] = self.planned
            return None
        if self.ctx.offline:
            return None
        if host in self.blocked_hosts:
            raise HostBlocked(host)
        secrets = (self.key, self.email)
        resp = None
        for attempt in range(4):
            self._check_budget(host)
            self.gov.acquire(host)
            self.used += 1
            if host in NCBI_HOSTS:
                self.ncbi_used += 1
            t0 = time.time()
            status, body, headers, err = None, b"", {}, None
            try:
                hdrs = {"User-Agent": f"{self.tool}/{VERSION.rsplit('.', 1)[0]}"}
                if data is not None:
                    hdrs["Content-Type"] = "application/x-www-form-urlencoded"
                req = urllib.request.Request(full, data=data, method=method, headers=hdrs)
                with urllib.request.urlopen(req, timeout=60) as r:
                    status, body, headers = r.status, r.read(), dict(r.headers)
            except urllib.error.HTTPError as e:
                status, body, headers = e.code, e.read(), dict(e.headers or {})
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
                err = scrub(getattr(e, "reason", e), secrets)
                if "Tunnel connection failed: 403" in err:
                    self.blocked_hosts.add(host)
                    err = f"host not on the network allowlist: {host} (add it to domains.txt)"
            ms = int((time.time() - t0) * 1000)
            resp = Response(status, body, shown, redact_params(params), method, headers, ms, err)
            self.gov.record(host, status, headers, err)
            retryable = ((err is not None and host not in self.blocked_hosts)
                         or status == 429 or (status or 0) >= 500)
            if not retryable or attempt == 3:
                break
            self.log(resp)                               # the governor has already paused and slowed this host; the next acquire waits
        if not resp.ok:
            self.log(resp)
            if host in self.blocked_hosts:
                raise HostBlocked(resp.error)
        return resp
