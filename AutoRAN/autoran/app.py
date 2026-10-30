"""AutoRAN desktop app: a native window (WebView2) over the same dashboard. No web server, no port, no browser.

The page talks to Python through pywebview's in-process bridge: `window.pywebview.api.call(method, path, body)` lands in `Api.call`,
which uses the same `server.dispatch` routing table as the optional web server. Heavy work (trial index, GPU scoring, plots) runs in
this process on your CPU and GPU.
"""
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__, core


class Api:
    """Exposed to the page. Names starting with an underscore are private (pywebview does not expose them)."""

    def __init__(self):
        self._state = None
        self._message = "Starting…"
        self._error = None
        self._lock = threading.Lock()
        self._t0 = time.time()
        self._load()

    # -- loading ---------------------------------------------------------------------------------
    def _load(self):
        def work():
            try:
                from . import server
                self._message = "Loading the trial index and scores…"
                ctx = core.make_ctx()
                cfg = core.load_cfg()
                st = server.State(ctx, cfg, "supervisor")
                with self._lock:
                    self._state, self._error, self._message = st, None, f"{len(st.rows):,} trials loaded" if st.rows else "no data yet"
            except BaseException as e:           # surfaced in the window, not lost
                with self._lock:
                    self._state, self._error = None, f"{type(e).__name__}: {e}"
                _log("load failed:\n" + traceback.format_exc())
        threading.Thread(target=work, daemon=True).start()

    def status(self):
        with self._lock:
            return {"ready": self._state is not None, "message": self._message, "error": self._error, "version": __version__,
                    "seconds": round(time.time() - self._t0, 1), "stale": bool(self._state and self._state.stale),
                    "jobs_running": bool(self._state and self._state.jobs.running()),
                    "empty": bool(self._state and self._state.empty)}

    # -- the one call the page makes ---------------------------------------------------------------
    def call(self, method, path, body=None):
        from . import server
        u = urlsplit(path)
        if u.path == "/api/status":
            return {"status": 200, "data": self.status()}
        if u.path == "/api/reload":
            with self._lock:
                if self._state and self._state.jobs.running():
                    return {"status": 400, "data": {"error": "a job is running; reload when it finishes"}}
                self._state = None
                self._t0 = time.time()
            self._load()
            return {"status": 200, "data": {"ok": True}}
        with self._lock:
            st = self._state
        if st is None:
            return {"status": 503, "data": {"error": "still loading"}}
        code, obj = server.dispatch(st, method, u.path, parse_qs(u.query), body or {})
        return {"status": code, "data": obj}


def _log(text):
    try:
        d = core.ROOT / "state"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "app.log", "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')}\n{text}\n")
    except OSError:
        pass


def _message_box(title, text):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        pass


def selftest():
    """Headless check of everything the window depends on. Writes state/selftest.json (a windowed exe has no console)."""
    out = {"version": __version__, "frozen": bool(getattr(sys, "frozen", False)), "root": str(core.ROOT), "python": sys.version.split()[0]}
    try:
        from . import gpu, plots
        from . import server as _srv
        out["gpu"] = _srv.gpu_info()
        t = time.time()
        api = Api()
        while api.status()["ready"] is False and not api.status()["error"] and time.time() - t < 240:
            time.sleep(0.5)
        out["load_seconds"] = round(time.time() - t, 1)
        out["status"] = api.status()
        r = api.call("GET", "/api/metrics")
        out["metrics_ok"] = r["status"] == 200 and "scorers" in r["data"]
        r = api.call("GET", "/api/trials?class=positive_recruitment&page=0")
        out["trials_ok"] = r["status"] == 200 and r["data"]["total"] > 0
        out["positives"] = r["data"].get("total")
        r = api.call("GET", "/api/sheet?source=random&class=positive_recruitment&n=12&seed=1")
        out["sheet_cards"] = len(r["data"].get("cards", []))
        r = api.call("GET", "/api/plots")
        out["plots"] = [p["name"] for p in r["data"]["plots"]]
        out["plugin_errors"] = r["data"]["plugin_errors"]
        r = api.call("GET", "/api/plot?name=" + out["plots"][0].replace(" ", "%20"))
        out["first_plot"] = {k: (len(v) if k == "png" else v) for k, v in r["data"].items() if k in ("png", "seconds", "device", "error")}
        gname = [n for n in out["plots"] if "GPU" in n]
        if gname:
            r = api.call("GET", "/api/plot?name=" + gname[0].replace(" ", "%20") + "&device=auto")
            out["gpu_plot"] = {k: (len(v) if k == "png" else v) for k, v in r["data"].items() if k in ("png", "seconds", "device", "error")}
        out["ok"] = bool(out["metrics_ok"] and out["trials_ok"] and "error" not in out["first_plot"])
    except BaseException as e:
        out["ok"], out["error"] = False, f"{type(e).__name__}: {e}"
        out["trace"] = traceback.format_exc()[-1500:]
    d = core.ROOT / "state"
    d.mkdir(parents=True, exist_ok=True)
    (d / "selftest.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return 0 if out.get("ok") else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        return selftest()
    try:
        import webview
        from .ui import HTML
        api = Api()
        webview.create_window("AutoRAN " + __version__, html=HTML, js_api=api, width=1440, height=920, min_size=(1000, 640),
                              background_color="#ffffff", text_select=True)
        storage = core.ROOT / "state" / "webview"
        storage.mkdir(parents=True, exist_ok=True)
        webview.start(debug="--debug" in argv, private_mode=False, storage_path=str(storage))
        return 0
    except BaseException as e:
        _log("window failed:\n" + traceback.format_exc())
        _message_box("AutoRAN could not start", f"{type(e).__name__}: {e}\n\nDetails are in {core.ROOT / 'state' / 'app.log'}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
