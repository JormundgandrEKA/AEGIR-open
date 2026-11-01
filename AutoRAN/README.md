# AutoRAN

The main AEGIR program: **automatic labelling of clinical-trial recruitment failure at registry scale** (the "silver set"). It downloads the
ClinicalTrials.gov registry, labels each trial's outcome from its own stop reason, categorises and scores the trials with baseline predictors, and shows the
results in a desktop app where a person supervises the labels at scale instead of reading them one by one.

The question it serves: could a protocol review pick out, in advance, the trials that later **failed to recruit**? Machine labels are not gold labels; the
human-checked side is [RÁN](../RAN/). **Read [DISCLAIMERS.md](DISCLAIMERS.md) before using or sharing results.**

## Run it

- **Easiest (Windows):** download `AutoRAN-lite-win64.zip` from the [latest release](https://github.com/JormundgandrEKA/AEGIR-open/releases/latest), unzip, double-click `AutoRAN\AutoRAN.exe`.
  It is about 170 MB, unsigned (SmartScreen may warn: "More info", then "Run anyway"), and contains no data and no PyTorch.
- **From source:** clone the whole repository (AutoRAN needs `../shared`), then `python -m autoran.app`.
- **Build the exe yourself:** `powershell -ExecutionPolicy Bypass -File build\build.ps1` (after `setup.ps1 -Build`).

On first run, with no data yet, the app opens on **Get started**: it downloads the registry to your computer (about 270 requests to clinicaltrials.gov and 40 to
the Hugging Face dataset server, about 12 minutes inside half of each limit, no account or key needed, resumable), then labels, categorises, scores and measures. A small sample for a quick try:
`autoran fetch --max-pages 2`, `labeller-data`, `normalise --partial`, `label`, `categorize`, `score`, `metrics` (about 2,000 trials, a few minutes).

## What you need

| | |
| --- | --- |
| Operating system | Windows 10 or 11 for the app (it needs the Edge WebView2 runtime, normally already installed). The command line runs anywhere Python does |
| Python (source only) | 3.11 or newer; `setup.ps1` installs the few packages in [requirements.txt](requirements.txt) that are missing (numpy, pandas, pyarrow, matplotlib, pywebview) |
| Disk | about 2 GB for the downloaded and derived data, plus about 170 MB for the app |
| Memory | 8 GB of RAM recommended (the full index takes about 1.2 GB in the window) |
| Graphics card (optional) | any recent NVIDIA card with CUDA support. It makes scoring and bootstrap intervals several times faster than the CPU; more card memory allows larger batches. About 3 GB of card memory is the peak when training on the full set. **Without one, everything still runs on the CPU**, just slower |
| PyTorch (optional) | only for the GPU, and AutoRAN looks after it: it finds a usable one already on your computer or installs one for itself (see below). About 3 GB if installed |

**GPU check.** AutoRAN checks your computer by itself: it reads the graphics card and driver (`nvidia-smi`), looks through every Python on the PC for a PyTorch that can see the GPU, and uses a compatible one with no setting. The result is saved for a week and shown in **Settings > Graphics card (GPU)**; the "GPU" badge in the top bar opens it.
If none is usable, **Install PyTorch for AutoRAN** downloads the CUDA build your driver supports (about 3 GB, with a confirmation) into `%LOCALAPPDATA%\AEGIR\gpu_pack` using pip from any Python on the PC. It changes nothing else. PyTorch comes from pip (download.pytorch.org), not git. Only the NVIDIA driver is needed: CUDA itself comes inside the PyTorch package.
The one limit: this AutoRAN runs on Python 3.13, so it can borrow only a PyTorch built for 3.13 (the check tells you if yours is for another version). On the command line: `autoran gpu-check [--fresh]`, `autoran gpu-install --dry-run`, `autoran gpu-install --yes`. `--device auto` (default) uses the GPU when it is ready and the CPU otherwise.

## The app

Pages: **Overview**, **Coverage**, **Labels and rules**, **Scorers**, **Browse** (filters, search, sort by any scorer, a trial inspector), **Review**, **Plots**, **Run**, **Settings**, **About**.

- **Run:** any pipeline step in the background on the CPU or GPU, with a log; Reload data when it finishes.
- **Plots:** built-in plots plus your own: drop one `.py` file in `plugins/` (see `plugins/example_sponsor.py`) and press Refresh. A plug-in gets `ctx.frame()` (a pandas table of every trial, label, category and score), `ctx.metrics`, `ctx.torch` and `ctx.device`.
- **Settings** (also the Graphics card section above; saved per user in `%APPDATA%\AutoRAN\settings.json`, outside the project; also `autoran settings --set name=value`): workspace folder for `data/` and `state/`, RÁN history folder, contact email
  (added to request User-Agents), optional Hugging Face token and NCBI key. Tokens are stored encrypted (Windows DPAPI) and never shown again or written to project files or logs. All optional.
- **Review** supervises thousands of labels without reading each: sheets of 12 to 48 cards, every card correct unless flagged (X wrong, U unsure, J/K move, Enter submit), live precision with a 95% interval and an "enough" signal at plus or minus 3 points;
  **canary** cards (about one in twelve, deliberately wrong) measure how closely screens are read and never count toward precision; **review by rule** samples what one rule matched; **targeted samples** surface the least certain labels, rule-versus-model disagreements and completed trials with tiny enrolment.
- A start-up problem shows a message box and writes `state/app.log`; `AutoRAN.exe --selftest` writes `state/selftest.json`.

## Fetching safely (the Fetch panel)

A **Fetch** panel sits at the top of every page, open by default and collapsing to a one-line strip when nothing is happening. It shows, for each source, the requests used in the
current window against the limit (a dashed line marks the auto-stop at 50%), job progress, and a colour: green is fine, yellow is paused, red is stopped after repeated errors.
A plain sentence says where things stand ("All clear. Your data will be local in about 6 minutes." or "Hugging Face is stopped for 12 minutes."). Layouts: bars, columns, gauges.

- Starting a download shows an estimate first and asks you to confirm.
- Any 429, 502 or 503 raises a notice in the panel (the panel opens if it was collapsed) and is kept as a note on disk. There is no sound.
- A source in trouble gets **Retry now** and **Schedule retry** (in 15 minutes or 1 hour; this works while AutoRAN stays open).
- The safety margin is a setting: `governor.margin` in `shared/config/aegir.json` (default 0.5, also per host). How it works and the figures used: [../shared/README.md](../shared/README.md).

## The pipeline (command line)

```
python -m autoran fetch            # ClinicalTrials.gov API v2, resumable; --delta later for updates
python -m autoran labeller-data    # Open Targets curated stop reasons (Apache-2.0, graded B-)
python -m autoran normalise        # one compact record per trial, with input_state
python -m autoran label            # stop-reason labeller: exact match, 40 pattern rules, a naive Bayes model
python -m autoran categorize       # areas, phase, region, frozen 70/10/20 split by NCT hash
python -m autoran score            # baselines (and GPU scorers when available); --device auto|cpu|cuda
python -m autoran metrics          # AUROC/AUPRC with bootstrap intervals, calibration, audits
python -m autoran run              # the whole chain, idempotent
python -m autoran frame            # one Parquet file of every trial, label, category and score
python -m autoran serve            # optional: the dashboard in a browser on 127.0.0.1:8780 (the app does not need it)
python -m unittest discover -s tests
```

Visualising: `autoran frame` writes `data/derived/autoran/frame_<stamp>.parquet`, readable from Python (`pandas.read_parquet`) and R (`arrow::read_parquet`);
`python viz/plots.py` draws four starter plots. In R: `df <- arrow::read_parquet(f); df |> dplyr::filter(class %in% c("positive_recruitment", "negative_completed"))`.
The `score_*` columns exist only for trials in the binary task (completed, or failed to recruit).

## What it found (author's run, 30 Oct 2026; data not included)

266,916 trials (all phases, interventional, started 2005 or later, completed or terminated): 7,486 recruitment failures, 238,360 completed, 17,021 other stops, 4,049 with no usable reason.
The labeller reaches 93.9% precision and 69.5% recall on a held-out curated test ("rules AND model agree" mode). Baseline AUROC on the test split: random 0.51, criteria count 0.63, linear 0.73 to 0.76, small neural net 0.76.
**No human has yet checked labels on real registry text**, so precision there is unmeasured. Full results, deviations from the design and weak points: [docs/build-report.md](docs/build-report.md).

## Rules AutoRAN keeps

- Append-only storage with provenance sidecars, polite shared rate limits and request budgets, no calls to history endpoints that refuse scripts, no personal data (contact fields are never requested), no language model inside the tool.
- Every record carries `source`, `grade` and `licence`; `export` refuses anything below the grade floor (config: B-).
- Scorers see input fields only (a pinned allow-list; tests check no outcome field can reach them). Splits are frozen by hash of the NCT number (20% test).

## Layout

```
autoran/    the package (fetch, normalise, labeller, categorize, scorers, metrics, gpu, app, plots, jobs, server, ui, audit, export, settings)
plugins/    your own plots, one .py file each
config/     autoran.json (scope, fields, splits), sources.json (licences and grades); rate limits and grade scale come from ../shared/config
tests/      offline tests (the GPU tests skip without PyTorch)
viz/        starter plots
docs/       build-report.md (results and gaps) and autoran-design.md (the original design, historical)
build/      build.ps1 and autoran.spec: the exe
data/       downloaded and derived files (ignored by git)
```

Licence: Apache-2.0, see the repository [LICENSE](../LICENSE) and [NOTICE](NOTICE). Data and software attributions: [THIRD_PARTY.md](THIRD_PARTY.md). No ClinicalTrials.gov or Open Targets data is included; neither provider endorses this project.
