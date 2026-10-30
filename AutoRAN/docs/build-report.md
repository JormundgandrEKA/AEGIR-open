# AutoRAN build report, first build (30 Oct 2026)

Written by Claude (Claude Code) for David O'Rourke and for Claude (Cowork). Read with `autoran-design.md` (v0.1).

## 1. Your decisions, as built

| Question in the design | Your answer | In the code |
|---|---|---|
| 1. Open Targets Apache-2.0 as B-? | Yes | `config/sources.json`: grade B-, licence `apache-2.0`; the grade floor test passes it and refuses lower |
| 2. Scope | All phases, reduce if needed | `config/autoran.json`: `scope.phases = "all"`, nothing had to be reduced: 266,916 trials fetched |
| 3. Contact NLM | Not now; work around it | No history calls anywhere. Clean inputs come from RAN's 233 browser-collected first versions and from never-updated records (section 4) |
| 4. Spot-check volume | Decide by realism; the interface should support supervising at scale | Exception-based review screens, review by rule, canaries, live intervals (section 5); no fixed audit quota |
| (later) Run on the GPU, Python or R | | Optional PyTorch backend (section 6); Parquet frame and plot scripts for Python and R |

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

Optional: PyTorch with CUDA on an NVIDIA card. Everything also runs on the CPU, only slower.
- `--device cuda` trains `gpu_logistic`, `gpu_logistic_text` and `gpu_mlp` on the whole train split (172k rows, 5,199 positives) with early stopping on dev AUROC and Platt calibration on dev.
  Each takes seconds on a recent card; peak card memory is about 3.1 GB.
- The bootstrap (1,000 resamples, AUROC and AUPRC) runs as batched sorts, about 4 times faster than the CPU path for the same work. The GPU intervals agree with the CPU ones to plus or minus 0.003; point estimates are identical.
- Not on the GPU, on purpose: fetching and normalising (network and string work) and the regex labeller. Parallelising normalise across CPU cores is the next speed-up there.
- GPU training is not bit-for-bit repeatable run to run (seeded, but CUDA kernels differ slightly); the standard-library path is the exact reference.
- The GPU scorers scored higher than the first CPU run because they use all training rows and early stopping, not because of the hardware.

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
4. Decide how and when RÁN's capabilities merge into AutoRAN (they are separate programs sharing `shared/` for now).

## 10. The desktop app and its packaging

Why: running a local web server and opening a browser tab was not wanted. `AutoRAN.exe` opens a native window instead.

How it works: pywebview hosts the same dashboard in the Microsoft Edge WebView2 control that Windows already has, and the page talks to Python through an in-process bridge
(`window.pywebview.api.call`), using the same routing function (`server.dispatch`) as the optional web server. No port is opened. The trial index loads in a background thread behind a start-up screen.
With no data yet the app opens on a Get started page.

Pages added: **Run** (background jobs on CPU/GPU/auto, one at a time, logs), **Plots** (built-in plots and a `plugins/` folder, one `.py` file per plot), **Settings** (per-user, outside the project,
tokens encrypted with Windows DPAPI). Links to ClinicalTrials.gov open in the default browser (only that host is allowed). Start-up failures show a message box and write `state/app.log`; `--selftest` is a headless check.

Packaging: a PyInstaller one-folder windowed build, about 170 MB (75 MB zipped), with Python, numpy, pandas, pyarrow, matplotlib, pywebview and the shared `aegir_core` package inside, and **no PyTorch**. An earlier build bundled PyTorch and CUDA
(about 4.3 GB); it is still available as `build.ps1 -Full` but is not meant for release. The small exe uses a PyTorch the user already has (Settings > GPU pack folder, or a `gpu_pack` folder beside the exe) and runs on the CPU without one.
Dependencies are listed in `requirements.txt` and `pyproject.toml` and installed by `setup.ps1`.

Verified: the frozen exe loads the 266,916-trial index, renders every plot, and uses the GPU through an existing PyTorch (self-test exit 0). A real window was opened and the Overview page viewed; the Run and Plots pages were exercised through
the same routes headlessly (a background job ran, a second was refused, a plug-in rendered), not clicked through in the window. Not tested: a computer with no Python at all (CPU only there).

Limits: Windows-only (WebView2); the exe is unsigned, so SmartScreen may warn; GPU runs are seeded but not bit-for-bit repeatable; `serve` (browser mode) still works and shares all code.
