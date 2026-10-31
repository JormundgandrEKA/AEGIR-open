"""Request governor: keeps every host at a safe fraction of its limit, and tells the user when something goes wrong.

Rules, all configurable (DEFAULTS below; the real thing would live in shared/config/aegir.json):
  * the margin: we use at most `margin` (default 50%) of a host's published maximum per window, so a second fetcher
    on the same IP (or another machine behind it) cannot push the total past the maximum;
  * a rolling window of request times per host, saved to disk and shared by every process using the same state file;
  * server signals (Retry-After, RateLimit / X-RateLimit headers): if the server says the window is already at our margin
    (other users included), hold until it resets;
  * 429 / 503 / 502 / network errors: notify, slow down (halve the rate), pause, and after repeated strikes open a
    saved cool-down (circuit breaker) so a restart does not hammer the host again;
  * every event is appended to events.jsonl (the persistent note) and sent to a notify callback (the on-screen alert);
  * snapshot() gives the numbers a screen needs; estimate() and plan() answer "how long will this take, is it safe?";
    headline() turns the state into one plain sentence ("All clear..." / "Hugging Face is stopped for...").
Everything lives in one small state file shared by every process (both programs, the app and the command line), so two fetchers
at once split the margin instead of doubling the load. Time and sleeping are injectable so tests run in virtual time.
All numbers are settings (config "governor" section); nothing here is hard-wired.
"""
import json
import math
import os
import re
import time
from pathlib import Path

DEFAULTS = {
    "margin": 0.5,                   # fraction of a host's maximum we allow ourselves (0.5 = 50%)
    "target_minutes": 20,            # a full fetch should land within this
    "hold_remaining": 0.10,          # if the server says less than this share of its window is left (others on the IP included), wait for the reset
    "slowdown": 0.5,                 # rate multiplier after 429 / 503
    "slowdown_502": 0.75,            # after 502 / 504 / network error
    "throttle_floor": 0.1,
    "recover_after": 25,             # clean requests before the rate creeps back up
    "recover_factor": 1.25,
    "strikes_to_trip": 3,            # errors within strike_window_s that open the cool-down
    "strike_window_s": 600,
    "cooldown_s": [900, 1800, 3600, 7200],
    "pause_s": {"429": 30, "503": 30, "502": 10, "504": 10, "net": 10},
    "hosts": {
        "clinicaltrials.gov": {"label": "ClinicalTrials.gov", "max": 50, "per_s": 60, "verified": False, "note": "no published limit; about 50 a minute per address is the community figure; the API sends no rate-limit headers"},
        "datasets-server.huggingface.co": {"label": "Hugging Face (Open Targets)", "max": 500, "max_with_token": 1000, "per_s": 300, "verified": True},
        "eutils.ncbi.nlm.nih.gov": {"label": "NCBI E-utilities", "max": 3, "max_with_key": 10, "per_s": 1, "verified": True},
        "www.ebi.ac.uk": {"label": "Europe PMC", "max": 10, "per_s": 1, "verified": False},
        "default": {"label": "other host", "max": 30, "per_s": 60, "verified": False},
    },
}


class Paused(Exception):
    """Raised instead of waiting when a host is in cool-down and the caller prefers to end cleanly."""

    def __init__(self, host, until, reason):
        super().__init__(f"{host} is paused until {time.strftime('%H:%M:%S', time.localtime(until))} ({reason})")
        self.host, self.until, self.reason = host, until, reason


class _Lock:
    """Cross-process lock around the state file."""

    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:                                           # create once, before anyone locks it (two first users must not race)
            with open(self.path, "xb") as first:
                first.write(b"{}")
        except FileExistsError:
            pass
        self.f = open(self.path, "a+b")
        if os.name == "nt":
            import msvcrt
            self.f.seek(0)
            msvcrt.locking(self.f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def read(self):
        self.f.seek(0)
        try:
            d = json.loads(self.f.read().decode("utf-8") or "{}")
            return d if isinstance(d, dict) else {}
        except ValueError:
            return {}

    def write(self, obj):
        data = json.dumps(obj).encode("utf-8")
        self.f.seek(0); self.f.truncate(); self.f.write(data); self.f.flush()

    def __exit__(self, *a):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f, fcntl.LOCK_UN)
        finally:
            self.f.close()


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class Governor:
    def __init__(self, state_path, cfg=None, clock=time.time, sleep=time.sleep, notify=None, has_token=None):
        self.cfg = _merge(DEFAULTS, cfg)
        self.state_path = Path(state_path)
        self.events_path = self.state_path.with_name("events.jsonl")
        self.clock, self.sleep, self.notify = clock, sleep, notify
        self.has_token = has_token or {}            # {host: True} when a token or key is in use (higher published maximum)

    # -- per-host numbers ----------------------------------------------------------------
    def host_cfg(self, host):
        h = self.cfg["hosts"].get(host) or self.cfg["hosts"]["default"]
        mx = h["max"]
        if self.has_token.get(host):
            mx = h.get("max_with_token", h.get("max_with_key", mx))
        margin = h.get("margin", self.cfg["margin"])
        return {"label": h.get("label", host), "max": mx, "window": h["per_s"], "margin": margin, "verified": h.get("verified", False)}

    def cap(self, host, st):
        hc = self.host_cfg(host)
        return max(1, math.floor(hc["max"] * hc["margin"] * st.get("throttle", 1.0)))

    @staticmethod
    def _blank():
        return {"hits": [], "throttle": 1.0, "clean": 0, "pause_until": 0, "hold_until": 0, "cooldown_until": 0, "tier": 0,
                "strikes": [], "today": 0, "day": "", "last_event": None, "last_error_ts": 0, "total_errors": 0}

    def _host_state(self, state, host):
        st = state.setdefault(host, self._blank())
        for k, v in self._blank().items():
            st.setdefault(k, v)
        return st

    # -- events --------------------------------------------------------------------------
    def _event(self, st, host, level, kind, text):
        ev = {"ts": self.clock(), "host": host, "level": level, "kind": kind, "text": text}
        st["last_event"] = ev
        if level in ("warn", "error"):
            st["last_error_ts"] = ev["ts"]
        try:
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev) + "\n")
        except OSError:
            pass
        if self.notify:
            try:
                self.notify(ev)
            except Exception:
                pass

    # -- asking permission to send ---------------------------------------------------------
    def try_acquire(self, host):
        """Reserve a slot. Returns (0, None) when the caller may send now, else (seconds_to_wait, reason)."""
        with _Lock(self.state_path) as lk:
            state = lk.read()
            st = self._host_state(state, host)
            now = self.clock()
            hc = self.host_cfg(host)
            w = hc["window"]
            st["hits"] = [t for t in st["hits"] if t > now - w]
            day = time.strftime("%Y-%m-%d", time.localtime(now))
            if st["day"] != day:
                st["day"], st["today"] = day, 0
            for key, reason in (("cooldown_until", "cool-down after repeated errors"), ("pause_until", "paused after an error"),
                                ("hold_until", "server says the window is nearly used")):
                if st[key] > now:
                    lk.write(state)
                    return st[key] - now + 0.001, ("cooldown" if key == "cooldown_until" else "pause" if key == "pause_until" else "hold")
            cap = self.cap(host, st)
            if len(st["hits"]) >= cap:
                wait = st["hits"][0] + w - now
                lk.write(state)
                return max(wait, 0) + 0.001, "window"
            gap = w / cap                              # spread requests out instead of sending bursts
            if st["hits"] and now - st["hits"][-1] < gap:
                lk.write(state)
                return gap - (now - st["hits"][-1]) + 0.001, "gap"
            st["hits"].append(now)
            st["today"] += 1
            lk.write(state)
            return 0, None

    def acquire(self, host, wait_cooldown=False):
        """Block until a slot is free. In a cool-down this raises Paused unless wait_cooldown is set."""
        while True:
            wait, reason = self.try_acquire(host)
            if wait == 0:
                return
            if reason == "cooldown" and not wait_cooldown:
                raise Paused(host, self.clock() + wait, "cool-down after repeated errors")
            self.sleep(min(wait, 5.0))

    # -- telling it what happened ------------------------------------------------------------
    @staticmethod
    def _signals(headers):
        """(used_fraction, seconds_to_reset) from RateLimit (IETF draft, Hugging Face) or X-RateLimit-* headers, else None."""
        h = {k.lower(): str(v) for k, v in (headers or {}).items()}
        rl, pol = h.get("ratelimit"), h.get("ratelimit-policy")
        if rl and pol:
            r, t, q = re.search(r"r=(\d+)", rl), re.search(r"t=(\d+)", rl), re.search(r"q=(\d+)", pol)
            if r and t and q and int(q.group(1)) > 0:
                return 1 - int(r.group(1)) / int(q.group(1)), int(t.group(1))
        lim, rem, rst = h.get("x-ratelimit-limit"), h.get("x-ratelimit-remaining"), h.get("x-ratelimit-reset")
        if lim and rem and lim.isdigit() and rem.isdigit() and int(lim) > 0:
            reset = int(rst) if rst and rst.isdigit() else 60
            if reset > 10 ** 9:                              # an epoch time, not seconds
                reset = max(0, reset - int(time.time()))
            return 1 - int(rem) / int(lim), reset
        return None

    def record(self, host, status, headers=None, error=None):
        """Report a finished request (status None = no response). Returns the host's status colour afterwards."""
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        with _Lock(self.state_path) as lk:
            state = lk.read()
            st = self._host_state(state, host)
            now = self.clock()
            hc = self.host_cfg(host)
            ok = error is None and status is not None and 200 <= status < 300
            if ok:
                st["clean"] += 1
                sig = self._signals(headers)
                if sig and sig[0] >= 1 - self.cfg["hold_remaining"] and st["hold_until"] <= now:   # the server's own count (us and everyone else on this IP) leaves too little
                    st["hold_until"] = now + sig[1]
                    self._event(st, host, "notice", "hold", f"{hc['label']}: server reports {sig[0]:.0%} of its window used (us plus anyone else on this connection); waiting {sig[1]} s for it to reset")
                if st["clean"] >= self.cfg["recover_after"] and st["throttle"] < 1:
                    st["throttle"] = min(1.0, st["throttle"] * self.cfg["recover_factor"]); st["clean"] = 0
                    if st["throttle"] >= 1:
                        self._event(st, host, "info", "recovered", f"{hc['label']}: back to the normal rate")
                if st["tier"] and st["clean"] >= 100:
                    st["tier"] = 0
            else:
                kind = "net" if status is None else str(status)
                if kind in ("429", "503", "502", "504", "net") or (status is not None and status >= 500):
                    kind = kind if kind in self.cfg["pause_s"] else "503"
                    st["clean"] = 0
                    st["total_errors"] += 1
                    st["throttle"] = max(self.cfg["throttle_floor"], st["throttle"] * (self.cfg["slowdown"] if kind in ("429", "503") else self.cfg["slowdown_502"]))
                    pause = self.cfg["pause_s"][kind]
                    ra = str(headers.get("retry-after", ""))
                    if ra.isdigit():
                        pause = max(pause, min(int(ra), 3600))
                    st["pause_until"] = max(st["pause_until"], now + pause)
                    level = "warn" if kind in ("429", "503") else "notice"
                    what = {"429": "429 Too Many Requests", "503": "503 Service Unavailable", "502": "502 Bad Gateway", "504": "504 Gateway Timeout", "net": "no response"}[kind]
                    self._event(st, host, level, kind, f"{hc['label']}: {what}. Slowing to {st['throttle']:.0%} of the normal rate and pausing {pause:.0f} s")
                    st["strikes"] = [t for t in st["strikes"] if t > now - self.cfg["strike_window_s"]] + [now]
                    if len(st["strikes"]) >= self.cfg["strikes_to_trip"]:
                        cd = self.cfg["cooldown_s"][min(st["tier"], len(self.cfg["cooldown_s"]) - 1)]
                        st["cooldown_until"], st["tier"], st["strikes"] = now + cd, st["tier"] + 1, []
                        self._event(st, host, "error", "cooldown", f"{hc['label']}: {self.cfg['strikes_to_trip']} errors in {self.cfg['strike_window_s'] // 60} min. Stopped using it for {cd // 60} min; the fetch can resume afterwards.")
            colour = self._colour(st, now)
            lk.write(state)
            return colour

    def _colour(self, st, now):
        if st["cooldown_until"] > now or (st["last_event"] and st["last_event"]["level"] == "error" and now - st["last_event"]["ts"] < 600):
            return "red"
        if st["pause_until"] > now or st["hold_until"] > now or st["throttle"] < 1:
            return "yellow"
        return "green"

    # -- what a screen shows -----------------------------------------------------------------------
    def snapshot(self):
        with _Lock(self.state_path) as lk:
            state = lk.read()
            now = self.clock()
            out = []
            for host in sorted({h for h in state if not h.startswith("_")} | set(state.get("_progress") or {})):
                st = self._host_state(state, host)
                hc = self.host_cfg(host)
                hits = [t for t in st["hits"] if t > now - hc["window"]]
                cap = self.cap(host, st)
                out.append({"host": host, "label": hc["label"], "verified": hc["verified"], "window_s": hc["window"],
                            "max": hc["max"], "line": math.floor(hc["max"] * hc["margin"]), "cap_now": cap, "used": len(hits),
                            "colour": self._colour(st, now), "throttle": st["throttle"], "today": st["today"],
                            "pause_left": max(0, round(st["pause_until"] - now)), "hold_left": max(0, round(st["hold_until"] - now)),
                            "cooldown_left": max(0, round(st["cooldown_until"] - now)), "errors_total": st["total_errors"], "progress": (state.get("_progress") or {}).get(host), "margin": hc["margin"],
                            "last_event": st["last_event"]})
            return out

    def estimate(self, host, n, other_use=True):
        """How long n requests will take at the allowed rate, and whether that fits the target."""
        with _Lock(self.state_path) as lk:
            state = lk.read()
            st = self._host_state(state, host)
            now = self.clock()
            hc = self.host_cfg(host)
            cap = self.cap(host, st)
            rate = cap / hc["window"]                                   # requests per second we may use
            wait = max(st["pause_until"], st["hold_until"], st["cooldown_until"]) - now
            secs = n / rate + max(0.0, wait)
            return {"host": host, "label": hc["label"], "requests": n, "per_minute": round(rate * 60, 1), "seconds": round(secs),
                    "minutes": round(secs / 60, 1), "fits": secs <= self.cfg["target_minutes"] * 60, "starts_after_s": max(0, round(wait)),
                    "max": hc["max"], "line": math.floor(hc["max"] * hc["margin"])}

    # -- jobs report progress so the screen can show "142 of 267" -----------------------------
    def progress(self, host, label, done, total, per=1):
        """done and total in items (trials, rows); per = items one request brings, so remaining time can be worked out."""
        with _Lock(self.state_path) as lk:
            state = lk.read()
            state.setdefault("_progress", {})[host] = {"label": label, "done": int(done), "total": int(total), "per": max(1, int(per)), "ts": self.clock()}
            lk.write(state)

    def clear_progress(self, host=None):
        with _Lock(self.state_path) as lk:
            state = lk.read()
            if host:
                state.get("_progress", {}).pop(host, None)
            else:
                state["_progress"] = {}
            lk.write(state)

    # -- the user's "retry now" ---------------------------------------------------------------
    def retry_now(self, host, force=False):
        """Clear a short pause or hold. A cool-down is cleared only with force=True (and then restarts at a quarter of the rate)."""
        with _Lock(self.state_path) as lk:
            state = lk.read()
            st = self._host_state(state, host)
            now = self.clock()
            if st["cooldown_until"] > now and not force:
                lk.write(state)
                return False
            if st["cooldown_until"] > now:
                st["cooldown_until"], st["throttle"] = 0, min(st["throttle"], 0.25)
            st["pause_until"] = st["hold_until"] = 0
            self._event(st, host, "info", "retry", f"{self.host_cfg(host)['label']}: retrying now at your request")
            lk.write(state)
            return True

    def events(self, n=30):
        """The newest n events, newest first (the persistent note kept on disk)."""
        try:
            lines = self.events_path.read_text(encoding="utf-8").splitlines()[-n:]
        except OSError:
            return []
        out = []
        for line in reversed(lines):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    # -- one plain sentence for the top of the screen -------------------------------------------
    def headline(self, snap=None):
        snap = snap if snap is not None else self.snapshot()
        now = self.clock()

        def clock_at(secs):
            return time.strftime("%H:%M", time.localtime(now + secs))

        def mins(secs):
            m = max(1, math.ceil(secs / 60))
            return f"{m} minute" + ("" if m == 1 else "s")
        red = [h for h in snap if h["colour"] == "red"]
        yellow = [h for h in snap if h["colour"] == "yellow"]
        active = [h for h in snap if h.get("progress") and h["progress"]["done"] < h["progress"]["total"]]
        if red:
            h = red[0]
            p = h.get("progress")
            saved = f" {p['done']:,} of {p['total']:,} {p['label']} are saved and the fetch resumes where it stopped." if p else " Nothing is lost; the fetch resumes where it stopped."
            title = f"{h['label']} is stopped for {mins(h['cooldown_left'])}." if h["cooldown_left"] else f"{h['label']} needs attention."
            return {"colour": "red", "host": h["host"], "title": title, "detail": (h["last_event"] or {}).get("text", "Repeated errors.") + saved, "eta_minutes": None}
        if yellow:
            h = yellow[0]
            if h["hold_left"] > h["pause_left"]:
                return {"colour": "yellow", "host": h["host"], "title": f"Waiting {mins(h['hold_left'])} for others on this connection to ease off.",
                        "detail": (h["last_event"] or {}).get("text", f"{h['label']} says its window is nearly used."), "eta_minutes": None}
            if h["pause_left"]:
                return {"colour": "yellow", "host": h["host"], "title": f"Paused for {h['pause_left']} seconds. Back on track by about {clock_at(h['pause_left'])}.",
                        "detail": (h["last_event"] or {}).get("text", f"{h['label']} asked us to slow down."), "eta_minutes": None}
            return {"colour": "yellow", "host": h["host"], "title": f"{h['label']} is running at {h['throttle']:.0%} of its normal rate.",
                    "detail": "It recovers by itself after a stretch of clean requests.", "eta_minutes": None}
        if active:
            secs = 0.0
            for h in active:
                rate = max(h["cap_now"] / h["window_s"], 1e-6)
                secs += ((h["progress"]["total"] - h["progress"]["done"]) / h["progress"].get("per", 1)) / rate
            eta = max(1, math.ceil(secs / 60))
            names = ", ".join(h["label"] for h in active)
            return {"colour": "green", "host": None, "title": f"All clear. Your data will be local in about {eta} minute" + ("" if eta == 1 else "s") + ".",
                    "detail": f"Fetching {names} inside half of each limit. Nothing needs you.", "eta_minutes": eta}
        return {"colour": "green", "host": None, "title": "All clear. Nothing is fetching.", "detail": "Every source is inside its safe budget.", "eta_minutes": None}

    def plan(self, needs):
        """needs = {host: n_requests}. Answers: how long, does it fit the target, what is the margin."""
        items = [self.estimate(h, n) for h, n in needs.items() if n > 0]
        total = sum(i["minutes"] for i in items)
        return {"items": items, "minutes": round(total, 1), "fits": total <= self.cfg["target_minutes"],
                "target_minutes": self.cfg["target_minutes"], "margin": self.cfg["margin"]}
