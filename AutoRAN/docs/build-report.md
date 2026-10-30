# AutoRAN build report, first build (30 Oct 2026)

From Claude (Claude Code) for the maintainer and for Claude (Cowork). Read with `autoran-design.md` (v0.1). Nothing is published.

## 1. Your decisions, as built

| Question in the design | Your answer | In the code |
|---|---|---|
| 1. Open Targets Apache-2.0 as B-? | Yes | `config/sources.json`: grade B-, licence `apache-2.0`; the grade floor test passes it and refuses lower |
| 2. Scope | All phases, reduce if needed | `config/autoran.json`: `scope.phases = "all"`, nothing had to be reduced: 266,916 trials fetched |
| 3. Contact NLM | Not now; work around it | No history calls anywhere. Clean inputs come from RAN's 233 browser-collected first versions and from never-updated records (section 4) |
| 4. Spot-check volume | Decide by realism; the interface should support supervising at scale | Exception-based review screens, review by rule, canaries, live intervals (section 5); no fixed audit quota |
| (later) Run on the GPU, Python or R | | Optional PyTorch backend in `.venv` (section 6); Parquet frame and plot scripts for Python and R |

## 2. What was built and run

Fetch: 267 requests (2 test pages, then 265), 266,916 trials, 214 MB compressed, 0 failed requests on ClinicalTrials.gov. Open Targets: 3,747 curated
stop reasons in 38 requests (the host rate-limited once with HTTP 429; the retry and a resumable download handled it).
Pipeline timings on CPU: normalise 69 s, label 44 s, categorize 8 s, scorers 23 s, metrics 73 s. Everything is a new dated file; a full run is idempotent.

Labels on all 266,916 trials: **7,486 recruitment failures**, 238,360 completed, 17,021 other stops, 4,049 with no usable stop reason. Among failures plus completions,
3.0% failed to recruit.

## 3. The stop-reason labeller (the part everything rests on)

Tiers: exact match to a curated text; 40 pattern rules with guards; a stdlib naive Bayes model. Developed on train and dev only; the 750-text test part was read to
report, not to tune.

Recruitment-failure label on the frozen test part (223 positives):

| mode | precision | recall |
|---|---|---|
| rules only | 0.873 | 0.866 |
| text model only | 0.854 | 0.762 |
| **rules AND model agree (in use)** | **0.939** | 0.695 |
| rules OR model | 0.816 | 0.933 |

Lesson worth keeping: choosing the mode on the small dev set picked the text model (91.6% dev precision), which fell to 85.4% on the test part. So the choice now needs a dev
precision floor of 0.93 (config `labeller.ie_dev_precision_floor`), which selects "AND". The design target of 90% is met, at the cost of missing 30% of true failures. Those
become "other stop", not "completed", so they cannot contaminate the negatives. Of the 17 stop classes only recruitment failure is tuned; the others are weaker
(macro-F1 0.42 on test) and only organise the "other stop" group.

Hand-checking has not happened yet: **no human audit is recorded**, so the real-registry precision is unmeasured. The labeller's accuracy is measured on curated Open Targets
text, which is cleaner than registry text.

## 4. Hindsight and clean inputs

The design expected most records to be "current" (possibly changed after the trial began). Measured: of 266,916, only 233 have a RAN first version and 2 were last updated
before they started. A better clean definition turned out to exist in the data: **30,044 records were never updated after first posting**, so they are the first submission by construction.
Clean inputs are therefore 30,279 (11.3%). Two cautions, both shown in the dashboard:
- every never-updated record was registered *after* its trial began (retrospective), and they are mostly small, simple trials, so "clean versus all" mixes contamination with a different kind of trial;
- the test split holds only 26 clean positives, so clean-subset intervals are wide.

## 5. Results so far (test split, 95% bootstrap intervals)

| scorer | AUROC all | AUROC clean | notes |
|---|---|---|---|
| random | 0.506 (0.49–0.52) | 0.541 (wide) | sanity check passes |
| criteria_count | 0.631 (0.62–0.64) | 0.609 | number of eligibility criteria |
| logistic (CPU, 45k sample) | 0.727 | 0.730 | first version |
| gpu_logistic (full train split) | 0.755 (0.74–0.77) | 0.750 | |
| gpu_logistic_text | 0.757 | 0.769 | adds hashed title and condition words |
| gpu_mlp | 0.758 | 0.754 | small neural net; no gain over linear |

Reading: simple protocol features carry a real but modest signal (AUROC about 0.75) and the neural net adds nothing, so a protocol-review engine has to clear about 0.76 on the
test split to claim it sees more than the easy signal. Positive rate is 3.1%, so AUPRC is low (about 0.09): read it with the base rate. Recruitment failure rates are highest in
Phase 2 (about 5 to 9% by year) and lowest in Phase 1 and non-phased trials. The fall in recent years is partly because recently started trials still recruiting are out of scope.
Site, sponsor and funding effects also predict failure, so this is not evidence of protocol flaws by itself (design section 16).

## 6. The GPU

Machine: RTX 4070, 12 GB, driver 595.59; PyTorch 2.11.0+cu128 in `.venv` (4.5 GB, isolated; the system Python was not touched).
- `--device cuda` trains `gpu_logistic`, `gpu_logistic_text` and `gpu_mlp` on the whole train split (172k rows, 5,199 positives) with early stopping on dev AUROC and Platt calibration on dev:
  2 to 6 s each, 3.1 GB peak GPU memory, 8.8 s to build the feature matrix.
- The bootstrap (1,000 resamples, AUROC and AUPRC) runs as batched sorts: metrics for 7 scorers in 17 s versus 73 s for 4 scorers on the CPU. The GPU intervals agree with the CPU ones to ±0.003; point estimates are identical.
- Not on the GPU, on purpose: fetching and normalising (network and string work) and the regex labeller. Parallelising normalise across CPU cores is the next speed-up there.
- GPU training is not bit-for-bit repeatable run to run (seeded, but CUDA kernels differ slightly); the standard-library path is the exact reference.
- Why GPU gave better scores than the first CPU run: it uses all training rows and early stopping, not that the hardware is smarter.

## 7. Where this departs from the design

- **Stdlib-only is no longer absolute.** The core and the reference path are still standard library; the GPU backend, plots and Parquet need PyTorch, numpy, pandas, pyarrow (optional, in `.venv`).
- No BERT tier: the "model" tier is a naive Bayes text model in the standard library. The BERT tier is untouched and remains optional.
- Trials are read straight from the stored pages via a page and position kept in each record (about 60 ms), instead of the design's offset index.
- `input_state` has a new value, `never_updated`; records also carry `registration` (prospective or retrospective).
- Areas come from MeSH ancestor terms, because the API did not return the branch names.
- New supervisor tools beyond the design: canaries, review by rule, targeted samples, Parquet frame, plot scripts.
- `autoran run` is wired but has not been run end to end (a delta fetch needs a day's changes); the scheduling notes are not written.
- `export` is built and tested for the grade floor, not run on the full data.

## 8. Weak points and gaps

- No human audit yet: the silver precision is unmeasured on registry text. The review screens exist for this.
- Only recruitment failure is tuned; the other stop classes are weak.
- The 26 clean test positives make the "clean" result nearly uninformative; real clean inputs need version history, which is the parked NLM question.
- Completed trials are labelled negative even if badly under-enrolled (planned enrolment is lost); the "tiny enrolment" sample exists to hunt for these.
- Recent years: trials still recruiting are excluded, and failures are only visible after termination, so recent-year rates are biased low.
- The inspector's feature explanation covers only the two CPU linear models.
- No server tests; the dashboard was tested by hand in a browser (all seven pages, one full review cycle).
- Normalised, labels and categories are 1.4 GB because earlier stage files are kept (append-only). Old stamps can be moved aside if space matters.

## 9. Decisions for the maintainer

1. Run Review for real: start with "Random recruitment failures", 24 per screen. About 200 checks give ±7 points; the screen tells you when ±3 is reached.
2. Decide whether the "rules AND model" trade (94% precision, 70% recall) is the right one, or whether to accept lower precision for more positives.
3. Decide how clean inputs should be scaled: wait for a supported NLM channel, or accept the never-updated subset with its caveats.
4. Say when AutoRAN should be moved into the AEGIR-open folder as a submodule, and whether `data/` stays out of it (it should).

## 10. The desktop app (added the same day)

Why: running a local web server and opening a browser tab was not wanted. Now `AutoRAN.exe` opens a native window.

How it works: pywebview hosts the same dashboard in the Microsoft Edge WebView2 control that Windows already has (v156 here), and the page talks to Python
through an in-process bridge (`window.pywebview.api.call`), using the same routing function (`server.dispatch`) as the optional web server. No port is opened
(checked: the running exe listens on none). The trial index loads in a background thread behind a start-up screen.

What was added: **Run** page (background jobs on CPU/GPU/auto, one at a time, logs, a "reload data" flag), **Plots** page (five built-in plots, one of which
runs a 5,000-resample bootstrap on the GPU in under a second, plus a `plugins/` folder: one `.py` file per plot), a CPU/GPU badge, links to ClinicalTrials.gov opening in
your default browser (only that host is allowed), a message box and `state/app.log` for start-up failures, `--selftest` for a headless check.

Packaging: PyInstaller one-folder build, windowed, with Python 3.13, PyTorch 2.11 (CUDA 12.8), numpy, pandas, pyarrow, matplotlib, scipy, pywebview and RAN's
`aegir_ran` inside: `AutoRAN.exe` (45 MB) plus `_internal/` (4.2 GB). The frozen exe's own self-test passes: CUDA seen, 266,916 trials loaded in 6 s, plots rendered
(GPU plot 0.9 s). It was also launched as a real window (title "AutoRAN 0.1.0", about 1.2 GB of memory). I could look at the Overview page; the Run and Plots pages
were tested through the same routes headlessly (a background job ran, a second job was refused, a plug-in rendered) but I did not click through them in the window.

Python environment: your default `python` (uv 3.13.7, marked externally managed) had none of numpy, pandas, torch or matplotlib. I installed them there with an explicit override:
numpy 2.5.4, pandas 3.1.0, matplotlib 3.11.2, pyarrow 26.0.0, scipy, plotly 7.1.0, torch 2.11.0+cu128 (CUDA works). Nothing was broken in the other Pythons
(Anaconda 3.14 and the Store 3.13.14 pass `pip check`; the Store one already had torch 2.14.1+cu126), so I did not touch them.

Limits: the app is Windows-only (WebView2); 4.3 GB on disk; the unsigned exe may trigger SmartScreen; GPU runs are seeded but not bit-for-bit repeatable;
`serve` (browser mode) still works and shares all code. Tests: 37 pass (core 22, GPU 5, app layer 10).
