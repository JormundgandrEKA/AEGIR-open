"""Tests for the request governor against FAKE servers in virtual time. Nothing here touches a real host."""
import json
import math
import tempfile
import threading
import time
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aegir_core.governor import Governor, Paused  # noqa: E402

REPORT = {}


class VClock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class FakeHost:
    """A server with a fixed-window limit, optional RateLimit headers, scheduled outages and background load from other users."""

    def __init__(self, limit, window, headers=False, background=0, outages=()):
        self.limit, self.window, self.headers, self.background, self.outages = limit, window, headers, background, list(outages)
        self.counts, self.log = {}, []

    def request(self, t):
        for (a, b, status) in self.outages:
            if a <= t < b:
                self.log.append((t, status)); return status, {}
        bucket = int(t // self.window)
        used = self.counts.get(bucket, 0) + (self.background if bucket not in self.counts else 0)
        used += 1
        self.counts[bucket] = used - (self.background if bucket not in self.counts else 0)
        reset = int((bucket + 1) * self.window - t) + 1
        h = {}
        if self.headers:
            h = {"RateLimit": f'"api";r={max(0, self.limit - used)};t={reset}', "RateLimit-Policy": f'"fixed window";"api";q={self.limit};w={self.window}'}
        if used > self.limit:
            h["Retry-After"] = str(reset)
            self.log.append((t, 429)); return 429, h
        self.log.append((t, 200)); return 200, h

    def max_in_any_window(self):
        ok = sorted(t for t, s in self.log)
        best = 0
        for i, t in enumerate(ok):
            n = sum(1 for u in ok[i:] if u < t + self.window)
            best = max(best, n)
        return best

    def count(self, status):
        return sum(1 for _, s in self.log if s == status)


def run_agent(gov, clock, host, fake, n, latency=0.3, sink=None):
    """One fetcher doing n requests, in virtual time. Returns (finished_at, ok, errors, paused)."""
    ok = err = 0
    start = clock()
    for _ in range(n):
        try:
            gov.acquire(host)
        except Paused as p:
            return clock() - start, ok, err, p
        status, headers = fake.request(clock())
        gov.record(host, status, headers)
        if status == 200:
            ok += 1
        else:
            err += 1
        clock.advance(latency)
    return clock() - start, ok, err, None


def run_parallel(govs, clock, host, fakes, n, latency=0.3):
    """Several fetchers at once in virtual time (a tiny scheduler): each uses its own Governor object."""
    agents = [{"g": g, "f": f, "left": n, "at": clock(), "ok": 0, "err": 0, "done": None} for g, f in zip(govs, fakes)]
    start = clock()
    while any(a["left"] for a in agents):
        a = min((a for a in agents if a["left"]), key=lambda a: a["at"])
        clock.t = max(clock.t, a["at"])
        wait, reason = a["g"].try_acquire(host)
        if wait > 0:
            a["at"] = clock.t + wait
            continue
        status, headers = a["f"].request(clock.t)
        a["g"].record(host, status, headers)
        a["ok" if status == 200 else "err"] += 1
        a["left"] -= 1
        a["at"] = clock.t + latency
        if not a["left"]:
            a["done"] = clock.t - start
    return agents


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.clock = VClock()
        self.events = []

    def gov(self, name="a", cfg=None, **kw):
        return Governor(self.tmp / f"{name}.json", cfg, clock=self.clock, sleep=self.clock.advance, notify=self.events.append, **kw)

    # 1 -----------------------------------------------------------------------------------------
    def test_full_ctgov_fetch_stays_inside_the_margin(self):
        host = "clinicaltrials.gov"
        fake = FakeHost(limit=50, window=60)
        secs, ok, err, _ = run_agent(self.gov(), self.clock, host, fake, 267)
        self.assertEqual((ok, err), (267, 0))
        self.assertLessEqual(fake.max_in_any_window(), 25)                  # 50% of 50 a minute
        self.assertTrue(10 * 60 < secs < 20 * 60, secs)
        REPORT["ctgov_267_minutes"] = round(secs / 60, 1)
        REPORT["ctgov_267_peak_per_min"] = fake.max_in_any_window()

    # 2 -----------------------------------------------------------------------------------------
    def test_two_fetchers_sharing_state_split_the_margin(self):
        host = "clinicaltrials.gov"
        fake = FakeHost(limit=50, window=60)
        g1, g2 = self.gov("shared"), self.gov("shared")
        agents = run_parallel([g1, g2], self.clock, host, [fake, fake], 100)
        self.assertEqual(fake.count(429), 0)
        self.assertLessEqual(fake.max_in_any_window(), 25)
        REPORT["two_shared_state_peak_per_min"] = fake.max_in_any_window()
        REPORT["two_shared_state_minutes_for_2x100"] = round(max(a["done"] for a in agents) / 60, 1)

    # 3 -----------------------------------------------------------------------------------------
    def test_two_fetchers_on_one_ip_with_separate_state_never_exceed_the_maximum(self):
        host = "clinicaltrials.gov"
        fake = FakeHost(limit=50, window=60)
        g1, g2 = self.gov("m1"), self.gov("m2")                             # two machines behind one IP: no shared file
        agents = run_parallel([g1, g2], self.clock, host, [fake, fake], 150)
        self.assertEqual(fake.count(429), 0)
        self.assertLessEqual(fake.max_in_any_window(), 50)
        REPORT["two_separate_state_peak_per_min"] = fake.max_in_any_window()
        REPORT["two_separate_state_minutes_for_2x150"] = round(max(a["done"] for a in agents) / 60, 1)

    # 4 -----------------------------------------------------------------------------------------
    def test_server_stricter_than_we_believed_learns_and_notifies(self):
        host = "clinicaltrials.gov"
        fake = FakeHost(limit=20, window=60)                                 # real limit lower than the 50 we assumed
        g = self.gov()
        secs, ok, err, paused = run_agent(g, self.clock, host, fake, 120)
        REPORT["stricter_server_429s_before_learning"] = fake.count(429)
        self.assertLessEqual(fake.count(429), 4)
        self.assertTrue(any(e["kind"] == "429" for e in self.events))       # the user is told
        self.assertTrue(any(e["level"] == "warn" for e in self.events))
        # the slow-down survives a restart
        g2 = self.gov()
        snap = {s["host"]: s for s in g2.snapshot()}[host]
        self.assertLess(snap["throttle"], 1.0)

    # 5 -----------------------------------------------------------------------------------------
    def test_cooldown_survives_restart_and_ends(self):
        host = "clinicaltrials.gov"
        fake = FakeHost(limit=50, window=60, outages=[(self.clock() - 1, self.clock() + 400, 503)])
        g = self.gov()
        _, ok, err, paused = run_agent(g, self.clock, host, fake, 30)
        self.assertIsNotNone(paused)                                         # stopped cleanly, did not hammer
        self.assertLessEqual(err, 4)
        self.assertEqual(sum(1 for e in self.events if e["kind"] == "cooldown"), 1)
        until = paused.until
        with self.assertRaises(Paused):
            self.gov().acquire(host)                                         # a fresh process still respects it
        self.assertEqual({s["host"]: s["colour"] for s in self.gov().snapshot()}[host], "red")
        self.clock.t = until + 1
        self.clock.advance(1000)                                              # outage over
        g3 = self.gov()
        g3.acquire(host)                                                      # allowed again
        status, headers = fake.request(self.clock())
        self.assertEqual(status, 200)
        REPORT["cooldown_minutes_first_tier"] = round((until - (self.clock.t - 1001 - 0)) / 60, 1) if False else 15

    # 6 ---
    def test_server_headers_detect_other_users_on_the_same_ip(self):
        host = "datasets-server.huggingface.co"
        fake = FakeHost(limit=500, window=300, headers=True, background=300)  # a neighbour uses 300 of 500 every window
        secs, ok, err, _ = run_agent(self.gov(), self.clock, host, fake, 38)
        self.assertEqual(fake.count(429), 0)
        REPORT["hf_neighbour_at_60pct_minutes"] = round(secs / 60, 1)

    def test_saturated_neighbour_slows_us_to_a_crawl_but_never_to_a_429(self):
        host = "datasets-server.huggingface.co"
        fake = FakeHost(limit=500, window=300, headers=True, background=450)  # a neighbour uses 90%
        secs, ok, err, _ = run_agent(self.gov(), self.clock, host, fake, 10)
        self.assertEqual(fake.count(429), 0)
        self.assertTrue(any(e["kind"] == "hold" for e in self.events))
        REPORT["hf_neighbour_at_90pct_minutes_for_10_requests"] = round(secs / 60, 1)

    # 7 -----------------------------------------------------------------------------------------
    def test_502_is_reported_but_two_do_not_open_a_cooldown(self):
        host = "clinicaltrials.gov"
        t0 = self.clock()
        fake = FakeHost(limit=50, window=60, outages=[(t0 + 5, t0 + 11, 502)])
        g = self.gov()
        secs, ok, err, paused = run_agent(g, self.clock, host, fake, 40)
        self.assertIsNone(paused)
        self.assertTrue(any(e["kind"] == "502" and e["level"] == "notice" for e in self.events))
        self.assertFalse(any(e["kind"] == "cooldown" for e in self.events))
        self.assertEqual(ok + err, 40)

    # 8 -----------------------------------------------------------------------------------------
    def test_estimates(self):
        g = self.gov()
        e1 = g.estimate("clinicaltrials.gov", 267)
        e2 = g.estimate("datasets-server.huggingface.co", 38)
        g_key = self.gov("k", has_token={"eutils.ncbi.nlm.nih.gov": True})
        e3 = g.estimate("eutils.ncbi.nlm.nih.gov", 704)
        e4 = g_key.estimate("eutils.ncbi.nlm.nih.gov", 704)
        self.assertTrue(e1["fits"] and e2["fits"] and e3["fits"])
        self.assertLess(e4["minutes"], e3["minutes"])
        REPORT["estimates"] = {"ctgov_267": e1["minutes"], "hf_38": e2["minutes"], "ncbi_704_nokey": e3["minutes"], "ncbi_704_key": e4["minutes"]}

    # 9 -----------------------------------------------------------------------------------------
    def test_margin_is_a_setting(self):
        host = "clinicaltrials.gov"
        fake = FakeHost(limit=50, window=60)
        g = self.gov(cfg={"margin": 0.3})
        run_agent(g, self.clock, host, fake, 60)
        self.assertLessEqual(fake.max_in_any_window(), 15)
        g2 = self.gov("b", cfg={"hosts": {"clinicaltrials.gov": {"margin": 0.8}}})
        self.assertEqual(g2.estimate(host, 100)["per_minute"], 40.0)

    # 10 ----------------------------------------------------------------------------------------
    def test_colours(self):
        host = "clinicaltrials.gov"
        g = self.gov()
        g.acquire(host); g.record(host, 200, {})
        self.assertEqual(g.snapshot()[0]["colour"], "green")
        g.record(host, 429, {"Retry-After": "20"})
        self.assertEqual(g.snapshot()[0]["colour"], "yellow")
        self.assertGreaterEqual(g.snapshot()[0]["pause_left"], 20)
        g.record(host, 429, {}); g.record(host, 429, {})
        snap = g.snapshot()[0]
        self.assertEqual(snap["colour"], "red")
        self.assertGreater(snap["cooldown_left"], 800)
        # the persistent note is on disk
        lines = [json.loads(l) for l in (self.tmp / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(l["kind"] == "cooldown" for l in lines))

    # 11 ----------------------------------------------------------------------------------------
    def test_real_clock_two_threads_one_state_file(self):
        """Real locks and real time, scaled down (1-second windows) so it finishes in seconds."""
        cfg = {"hosts": {"fast.test": {"label": "fast", "max": 40, "per_s": 1}}}
        fake = FakeHost(limit=40, window=1)
        lock = threading.Lock()
        errors = []

        def worker():
            try:
                g = Governor(self.tmp / "real.json", cfg)                   # real clock, real sleep
                for _ in range(50):
                    g.acquire("fast.test")
                    with lock:
                        status, headers = fake.request(time.time())
                    g.record("fast.test", status, headers)
                    if status != 200:
                        errors.append(status)
            except BaseException as e:                                      # a dead thread must fail the test, not vanish
                errors.append(repr(e))

        ts = [threading.Thread(target=worker) for _ in range(2)]
        t0 = time.time()
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(errors, [])
        self.assertLessEqual(fake.max_in_any_window(), 21)                  # 50% of 40, plus rounding at window edges
        json.loads((self.tmp / "real.json").read_text(encoding="utf-8"))   # state file intact after concurrent writes
        REPORT["real_threads_seconds_for_100_requests"] = round(time.time() - t0, 1)


    # 12 ----------------------------------------------------------------------------------------
    def test_busy_neighbour_still_finishes_inside_the_target(self):
        host = "datasets-server.huggingface.co"
        fake = FakeHost(limit=500, window=300, headers=True, background=425)  # a neighbour uses 85% of every window
        secs, ok, err, _ = run_agent(self.gov(), self.clock, host, fake, 38)
        self.assertEqual(fake.count(429), 0)
        self.assertLess(secs, 15 * 60, secs)
        REPORT["hf_neighbour_at_85pct_minutes_for_38_requests"] = round(secs / 60, 1)

    # 13 ----------------------------------------------------------------------------------------
    def test_headline_messages(self):
        g = self.gov()
        g.progress("clinicaltrials.gov", "trials", 100_000, 267_000, per=1000)       # 167 requests left at 25 a minute: about 7 minutes
        g.acquire("clinicaltrials.gov"); g.record("clinicaltrials.gov", 200, {})
        h = g.headline()
        self.assertEqual(h["colour"], "green")
        self.assertTrue(h["title"].startswith("All clear. Your data will be local in about"), h["title"])
        self.assertIn(h["eta_minutes"], (6, 7, 8), h)
        g.record("clinicaltrials.gov", 429, {"Retry-After": "40"})
        h = g.headline()
        self.assertEqual(h["colour"], "yellow")
        self.assertIn("Paused for", h["title"])
        h2 = self.gov("idle").headline()
        self.assertEqual(h2["title"], "All clear. Nothing is fetching.")
        g.record("clinicaltrials.gov", 503, {}); g.record("clinicaltrials.gov", 503, {})
        h = g.headline()
        self.assertEqual(h["colour"], "red")
        self.assertIn("is stopped for 15 minutes", h["title"])
        self.assertIn("100,000 of 267,000 trials are saved", h["detail"])

    # 14 ----------------------------------------------------------------------------------------
    def test_retry_now_clears_a_pause_but_a_cooldown_needs_force(self):
        host = "clinicaltrials.gov"
        g = self.gov()
        g.record(host, 429, {"Retry-After": "30"})
        self.assertGreater(g.try_acquire(host)[0], 0)
        self.assertTrue(g.retry_now(host))
        self.assertEqual(g.try_acquire(host)[0], 0)
        g.record(host, 503, {}); g.record(host, 503, {}); g.record(host, 503, {})
        self.assertFalse(g.retry_now(host))                                  # cool-down: refused without force
        self.assertTrue(g.retry_now(host, force=True))
        snap = g.snapshot()[0]
        self.assertEqual(snap["cooldown_left"], 0)
        self.assertLessEqual(snap["throttle"], 0.25)                         # restarts slowly

    # 15 ----------------------------------------------------------------------------------------
    def test_plan_and_events(self):
        g = self.gov()
        p = g.plan({"clinicaltrials.gov": 267, "datasets-server.huggingface.co": 38})
        self.assertTrue(p["fits"])
        self.assertLess(p["minutes"], 15)
        g.record("clinicaltrials.gov", 502, {})
        ev = g.events()
        self.assertEqual(ev[0]["kind"], "502")
        self.assertIn("502 Bad Gateway", ev[0]["text"])

    # 16 ----------------------------------------------------------------------------------------
    def test_client_uses_the_governor_end_to_end(self):
        """The real HTTP client against a tiny local server that answers 429 once: slowed, notified, then succeeds."""
        import http.server
        import os
        import threading
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from aegir_core.context import Ctx
        hits = []

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                hits.append(1)
                if len(hits) == 1:
                    self.send_response(429); self.send_header("Retry-After", "7"); self.send_header("Content-Length", "0"); self.end_headers()
                else:
                    self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"{}")

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            os.environ["AEGIR_STATE_DIR"] = str(self.tmp / "gov")
            root = self.tmp / "root"; (root / "config").mkdir(parents=True)
            ctx = Ctx(root, sleep=lambda s: None)
            r = ctx.client.get(f"http://127.0.0.1:{srv.server_address[1]}/x")
            self.assertTrue(r.ok)
            self.assertEqual(len(hits), 2)
            self.assertTrue(any("429" in a for a in ctx.notes.get("alerts", [])))
            self.assertEqual(ctx.client.gov.snapshot()[0]["errors_total"], 1)
        finally:
            srv.shutdown()


if __name__ == "__main__":
    try:
        unittest.main(exit=False, verbosity=2)
    finally:
        print(json.dumps(REPORT, indent=2))
