"""Background jobs for the desktop app: run a pipeline stage on CPU or GPU without blocking the window."""
import argparse
import json
import threading
import time
import traceback

from . import core

# stage -> (label, what it does, whether it needs the network)
STAGES = {
    "fetch-delta": ("Fetch updates", "Pull trials changed since the last finished fetch from ClinicalTrials.gov (about 1 to 20 requests).", True),
    "fetch-full": ("Fetch all trials", "First download from ClinicalTrials.gov: about 267 requests, 214 MB, a little under an hour at the polite rate limit. Safe to stop and resume. No key needed.", True),
    "labeller-data": ("Fetch stop-reason data", "Download the Open Targets curated stop reasons (about 38 requests, a couple of minutes). The labeller needs it.", True),
    "normalise": ("Normalise", "Stored pages to one compact record per trial (CPU, about 70 s).", False),
    "label": ("Label", "Stop-reason labeller and outcome classes for every trial (CPU, about 45 s).", False),
    "categorize": ("Categorize", "Areas, phase, region, input state and the frozen split (CPU, about 10 s).", False),
    "score": ("Score", "Train and run the scorers. GPU adds gpu_logistic, gpu_logistic_text and gpu_mlp trained on the full train split.", False),
    "metrics": ("Metrics", "Recompute every number on screen. The bootstrap intervals run as one batched job on the GPU.", False),
    "frame": ("Parquet frame", "Write one Parquet table of every trial, label, category and score, for pandas, plots or R.", False),
    "export": ("Export silver set", "Write the silver set with its licence manifest (refuses anything below the grade floor).", False),
    "run-all": ("Run everything", "Delta fetch, then normalise, label, categorize, score and metrics, in order.", True),
}


class Jobs:
    def __init__(self, on_done=None):
        self.items = []
        self.lock = threading.Lock()
        self.on_done = on_done

    def running(self):
        with self.lock:
            return any(j["state"] == "running" for j in self.items)

    def status(self):
        with self.lock:
            return {"running": any(j["state"] == "running" for j in self.items), "stages": {k: {"label": v[0], "about": v[1], "network": v[2]} for k, v in STAGES.items()},
                    "items": [dict(j, log=list(j["log"][-60:])) for j in self.items[-12:]]}

    def start(self, stage, device="auto"):
        if stage not in STAGES:
            raise ValueError(f"unknown stage: {stage}")
        if self.running():
            raise ValueError("a job is already running; wait for it to finish")
        job = {"id": len(self.items) + 1, "stage": stage, "device": device, "state": "running", "started": time.strftime("%H:%M:%S"),
               "finished": None, "seconds": None, "log": [f"started {STAGES[stage][0]} (device {device})"], "summary": None}
        with self.lock:
            self.items.append(job)
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return {"id": job["id"]}

    def _run(self, job):
        t0 = time.time()
        stage, device = job["stage"], job["device"]
        try:
            from . import commands
            ctx = core.make_ctx()
            cfg = core.load_cfg()
            cmd = {"fetch-delta": "fetch", "fetch-full": "fetch", "run-all": "run"}.get(stage, stage)
            args = argparse.Namespace(device=device, delta=stage == "fetch-delta", new=False, max_pages=None, scorer=None, grade_floor=None,
                                      n=200, klass="positive_recruitment", seed=28, port=0, labeller="supervisor", no_browser=True)
            res = commands.run(cmd, ctx, cfg, args)
            s = ctx.summary(f"autoran {cmd}")
            job["summary"] = {"counts": s["counts"], "errors": s["errors"], "notes": s.get("notes", {}), "result": _short(res)}
            job["log"].append("finished: " + json.dumps(job["summary"], default=str)[:1500])
            job["state"] = "failed" if s["errors"] else "done"
        except SystemExit as e:
            job["state"], job["log"] = "failed", job["log"] + ["stopped: " + str(e)]
        except Exception as e:                      # keep the app alive; show the reason
            job["state"] = "failed"
            job["log"] += ["error: " + str(e), traceback.format_exc()[-800:]]
        job["seconds"] = round(time.time() - t0, 1)
        job["finished"] = time.strftime("%H:%M:%S")
        if self.on_done:
            try:
                self.on_done(job)
            except Exception:
                pass


def _short(res):
    try:
        return json.loads(json.dumps(res, default=str))
    except (TypeError, ValueError):
        return str(res)[:500]
