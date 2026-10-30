# AutoRAN

Automatic labelling of clinical-trial recruitment failure at registry scale: the **silver set**. A part of AEGIR, built on RAN
(it reuses RAN's HTTP client, rate limits, store and text tools and changes nothing in RAN).

The question it serves: could a protocol review pick out, in advance, the trials that later **failed to recruit**? AutoRAN
fetches the trials, labels each one from the registry's own stop reason, categorises it, scores it with baseline predictors, and
shows the results in a dashboard where a person can supervise the labels at scale.

Status: first working build (0.1.0), 30 Oct 2026, as a Windows desktop app and a command line. Research software: **read [DISCLAIMERS.md](DISCLAIMERS.md) before using or sharing results.**
This repository holds code only. It contains no registry data and no executable: you fetch the data yourself and build the app (below).

## Requirements

- **Windows 10 or 11** for the desktop window (the command line and the pipeline also run elsewhere; the window needs the Edge WebView2 runtime, which Windows normally has).
- **Python 3.11 or newer.** The core pipeline uses only the standard library. The dashboard window, plots and GPU scoring need `numpy`, `pandas`, `pyarrow`, `matplotlib`, `scipy`, `pywebview` (`pip install -r requirements-app.txt`), and optionally PyTorch for an NVIDIA GPU (`requirements-gpu.txt`).
- **RAN** (`aegir_ran`, from the AEGIR-open repository). AutoRAN reuses its HTTP client, rate limits and store. Put AutoRAN inside the AEGIR-open folder or next to it, or point to RAN's `tool` folder on the Settings page (or the `AEGIR_TOOL` environment variable).
- **Internet access and about 2 GB of disk** for the first fetch: roughly 267 requests to clinicaltrials.gov (214 MB) at 40 a minute, a little under an hour, resumable, plus about 38 requests to the Hugging Face dataset server for the Open Targets stop reasons.
- **No account and no API key is needed to fetch.** A contact email, a Hugging Face token and an NCBI key are optional (Settings page, or `autoran settings`). If a service ever starts requiring a key, enter it there.

## First run

1. Start the app (next section). With no data yet it opens on a **Get started** page.
2. Optional: **Settings** (workspace folder, contact email, tokens).
3. Press **Fetch everything and build (first run)**, or run `autoran run` on the command line. Close and reopen, or press Reload data, when it finishes.

To try it on a small sample first: `autoran fetch --max-pages 2`, `autoran labeller-data`, `autoran normalise --partial`, then `label`, `categorize`, `score`, `metrics` (about 2,000 trials, a few minutes in all).

## Settings (per user, persistent)

The **Settings** page (or `autoran settings --set name=value`) saves, for your Windows user and outside the project folder: the workspace folder for `data/` and `state/`, the RAN folder, an optional RAN history folder, a contact email (added to request User-Agents), and optional Hugging Face and NCBI tokens. Tokens are stored encrypted (Windows DPAPI) and are never shown again or written to project files or logs. File: `%APPDATA%\AutoRAN\settings.json`.

## What it holds in the author's run (30 Oct 2026; not included here)

| | |
|---|---|
| Trials | 266,916 (all phases, interventional, started 2005 or later, completed or terminated) from ClinicalTrials.gov, grade A+ |
| Recruitment failures | 7,486 (labelled from whyStopped); 238,360 completed; 17,021 other stops; 4,049 with no usable reason |
| Stop-reason labeller | exact match, 40 pattern rules, a naive Bayes text model; 93.9% precision (69.5% recall) on the held-out curated test with the "rules AND model agree" mode |
| Baselines (test AUROC) | random 0.51, criteria count 0.63, linear 0.73–0.76, small neural net 0.76 |

## Open the app

From source: `python -m autoran.app`. As an executable: build it with `powershell -ExecutionPolicy Bypass -File build\build.ps1` (needs the packages above plus PyInstaller; the result is large, about 4 GB with PyTorch and CUDA, and unsigned).
Then double-click **`AutoRAN.exe`** in this folder. A native window opens (no browser, no web server, no network port) and runs on this
computer's CPU and GPU. It loads the 266,916-trial index in about half a minute, then shows the dashboard: Overview, Coverage,
Labels and rules, Scorers, Browse, Review, **Plots**, **Run** and About.

- **Run** page: run any pipeline step (normalise, label, categorize, score, metrics, Parquet frame, export, or everything) in the background, on the
  GPU, the CPU, or "auto"; read the log; press "Reload data" when new results are ready.
- **Plots** page: built-in plots plus any plug-in. To add a visualisation, drop one `.py` file in `plugins/` (see `plugins/example_sponsor.py`) and press
  Refresh. Plug-ins get the pandas frame, the metrics and the GPU (`ctx.frame()`, `ctx.metrics`, `ctx.torch`, `ctx.device`).
- A startup problem shows a message box and writes `state/app.log`.

The exe is a self-contained build (about 4.3 GB with PyTorch and CUDA inside), so a broken Python module on this machine cannot stop it. It needs the
Microsoft Edge WebView2 runtime, which Windows 10 and 11 normally have. It is unsigned, so Windows SmartScreen may warn the first time.
Rebuild it after code changes with `powershell -ExecutionPolicy Bypass -File build\build.ps1`.

## Quick start (command line)

AutoRAN needs RAN (`aegir_ran`). It finds it next to itself: put this folder inside AEGIR-open, or beside `AEGIR/`, or set `AEGIR_TOOL`.

```
python -m autoran --help                      # standard-library path, Python 3.10+, no installs
python -m unittest discover -s tests          # offline tests (GPU tests skip without PyTorch)

# the pipeline, in order (each stage writes new dated files)
python -m autoran fetch                       # ~267 requests, resumable; --delta for later updates
python -m autoran labeller-data               # Open Targets curated stop reasons (Apache-2.0, graded B-)
python -m autoran normalise
python -m autoran label
python -m autoran categorize
python -m autoran score
python -m autoran metrics
python -m autoran serve                       # optional: the same dashboard in a browser on 127.0.0.1:8780 (the exe does not need this)
python -m autoran.app                         # the desktop window, from source
```

### GPU

The heavy maths (scorer training and scoring, bootstrap intervals, GPU plots) runs on an NVIDIA GPU through PyTorch. The exe has PyTorch inside.
From source, use `.venv` (or any Python with torch, numpy, pandas, matplotlib and pyarrow; the default `python` on this machine has them too):

```
uv venv .venv --python 3.13
uv pip install --python .venv/Scripts/python.exe --torch-backend=auto torch numpy pandas pyarrow matplotlib plotly
.venv\Scripts\python -m autoran gpu-info
.venv\Scripts\python -m autoran score --device cuda      # adds gpu_logistic, gpu_logistic_text, gpu_mlp
.venv\Scripts\python -m autoran metrics --device cuda    # batched bootstrap on the GPU
```

`--device auto` (the default) uses the GPU when PyTorch and CUDA are present and falls back to the standard-library path otherwise.
On the RTX 4070 the three GPU scorers train on the full 172k-row training split in 2 to 6 seconds each, and the metrics run takes
17 s against 73 s on the CPU. Fetching, normalising and the regex labeller are I/O or string work and stay on the CPU.

### Visualising

```
.venv\Scripts\python -m autoran frame        # one Parquet file: trial, label, categories, split, every score
.venv\Scripts\python viz\plots.py            # four starter plots
```

The Parquet file reads in pandas, plotly, or R (`arrow::read_parquet`); see [viz/README.md](viz/README.md).

## The dashboard (`autoran serve`)

Overview, Coverage (any category, with failure rates), Labels and rules, Scorers (ROC, intervals, calibration, by area and phase), Browse (filters,
search, sort by any scorer), a trial inspector, Review and About. It is square, high-contrast and keyboard-first, like RAN's labelling app.

Supervising thousands of labels without reading each one:
- **Review screens.** A sheet of 12 to 48 cards, every card counted as correct unless you flag it (X wrong, U unsure, J/K move, Enter submit).
  Live precision with a 95% Wilson interval and an "enough / keep going" signal at ±3 points.
- **Canary cards.** About one card in twelve is a real curated stop reason shown with a deliberately wrong class, with a borrowed real title.
  The share you flag is "reviewer attention". Canaries never count toward any precision.
- **Review by rule.** Sample the trials one rule matched and judge them together; one screen speaks for thousands of trials.
- **Targeted samples:** least-certain labels, rules-versus-model disagreements, and completed trials with tiny enrolment (hidden failures?).

## Rules AutoRAN keeps

- RAN's: append-only storage, sidecars with provenance, polite shared rate limits, request budgets, no history-endpoint calls, no personal data
  (contact fields are never even requested), no language-model calls inside the tool.
- Every record carries `source`, `grade` and `licence`; `export` refuses anything below the grade floor (config: B-). Open Targets (Apache-2.0) is graded B-.
- Scorers see input fields only (a pinned allow-list; tests check no outcome field can reach them).
- Splits are frozen by hash of the NCT number (20% test).

## Layout

```
AutoRAN.exe    the desktop app (with _internal/, its libraries); build/ rebuilds it
autoran/        the package (fetch, normalise, labeller, categorize, scorers, metrics, gpu, app, plots, jobs, server, ui, audit, export)
plugins/        your own plots (one .py file each)
config/         autoran.json (scope, fields, splits, labeller floor), sources.json (licences and grades), aegir.json, grades.json
tests/          offline tests; tests/test_gpu.py needs PyTorch
viz/            plots.py and a README for Python and R
docs/           the design (autoran-design.md) and the build report (build-report.md)
data/           fetched pages, derived files, audits (ignored by git; about 1.6 GB)
```

See [docs/build-report.md](docs/build-report.md) for results, deviations from the design, weak points and what is next.

## Licence and attribution

Apache License 2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE) (copyright holder tentatively David J. W. O'Rourke; attribution to be confirmed). Data sources, software licences and the question of redistributing a built executable are in [THIRD_PARTY.md](THIRD_PARTY.md). Registry data: ClinicalTrials.gov, U.S. National Library of Medicine; curated stop reasons: Open Targets (Apache-2.0). Neither provider endorses this project.
