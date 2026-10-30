# RÁN

**RÁN** (`aegir_ran`, "Registry and Article Net") is the AEGIR answer-key tool: it fetches public trial and article data, stores it unchanged and
traceable, flags what changed between registry versions by plain rules, and runs a local app where a person labels the changes. It is the
human-labelled (gold) side of the project; the large machine-labelled (silver) side is [AutoRAN](../AutoRAN/). The two are kept separate for now.

Status, tests and limits: [docs/STATUS.md](docs/STATUS.md). Pictures: [docs/ran-overview.html](docs/ran-overview.html).
The change-analysis rules are Claude's reading of published standards (EU CTR, SPIRIT and CONSORT 2025, COMPare, Tufts CSDD), tuned on a small set of
labels, and **have not been reviewed by a clinician or methodologist**: treat their output as provisional.

## Try the labelling app (real demo data, no fetching)

`demo/` holds 16 real ClinicalTrials.gov cases (COPD trials, a dated snapshot) with provisional labels. Source, date and modifications: [demo/ATTRIBUTION.md](demo/ATTRIBUTION.md).

- **Windows, nothing to install:** download `RAN.exe` from the [RÁN snapshot release](https://github.com/JormundgandrEKA/AEGIR-open/releases/tag/v0.1.0-snapshot)
  and double-click it. Enter a name; with no batches of your own it opens the demo. Your labels go to `data/demo/<name>/` beside the exe.
  The exe is unsigned, so SmartScreen may warn ("More info", then "Run anyway"); check its SHA-256 against the release.
- **From source:** needs Python 3.10+ and the full repository (RÁN imports `../shared`). No packages to install.
  ```
  cd RAN
  python -m aegir_ran labels serve --labeller yourname --batch demo
  ```
  Keys are listed behind `?` on the page. The app runs on 127.0.0.1 only.

## Commands

```
python -m unittest discover -s RAN/tests            # 41 offline tests, no network (from the repository folder)
cd RAN
python -m aegir_ran --help                          # all commands
python -m aegir_ran status                          # counts, last fetch, whether an NCBI key is set
python -m aegir_ran ctgov search --query-id copd-p23-2010-2020 --dry-run     # shows the request, sends nothing
python -m aegir_ran labels build-batch --synthetic 5 --name demo             # five invented cases
```

Every command ends with one JSON line (counts, files written, requests used, errors). Add `--dry-run` to see requests and an estimate first.
A query is a small JSON file in `config/queries/`: `{"id", "source": "ctgov", "params": {...}}` or `{"id", "source": "pubmed", "term": "..."}`. A changed query needs a new `id`.

**Build a real batch** (the COPD pool as an example; about 2 requests for 400+ trials):

```
python -m aegir_ran ctgov search --query-id copd-p23-2010-2020
python -m aegir_ran ctgov import-history <folder-of-history-files>
python -m aegir_ran derive label-flags   --pool copd-p23-2010-2020         # index-only pre-screen
python -m aegir_ran derive content-flags --pool copd-p23-2010-2020         # reads the stored version text
python -m aegir_ran labels build-batch --from data/derived/<content_flags file> --positives 50 --negatives 50 --seed 28 --name my-batch
python -m aegir_ran labels serve --labeller yourname --batch my-batch
```

**Articles and licences:** `pubmed search --query-id trials-updates`, `pubmed fetch <PMID> ...`, `pmc licence <PMCID> ...`, `epmc licence --from-query trials-updates`.

**History files.** The registry's history endpoint refuses scripts (HTTP 403) and RÁN does not work around that, so version histories are saved from your own
browser session and imported (`ctgov import-history`): an index `NCT########_history.json` and versions `NCT########_v<N>.json`, or one bundle. Each import records
`"collected_via": "user browser"`. For bulk access, ask NLM about a supported channel.

**NCBI key (optional).** Without one NCBI allows 3 requests a second, with one 10. Copy `config/ncbi.example.json` to `config/ncbi.local.json` (git-ignored) and fill in
`api_key` and `email`, or set `NCBI_API_KEY` and `NCBI_EMAIL`. Check with `python -m aegir_ran status --check-key`. Europe PMC needs no key.

## Rules

- **Append-only.** Nothing under `data/` is deleted or overwritten; each fetch is a new dated file with a `.meta.json` sidecar. See [data/README.md](data/README.md).
- **Polite.** Limits are shared across processes (`state/rate.json`; per-host values in `../shared/config/aegir.json`): ClinicalTrials.gov 40 requests a minute, NCBI 3 a second
  (10 with a key), Europe PMC 50 a minute. Each command has a request budget (default 500, `--max-requests`). Jobs over 1,000 NCBI requests are refused on US weekday daytime unless `--daytime-ok`.
- **Cache first.** Anything already catalogued is not fetched again unless you pass `--refresh`.
- **Named queries only for the gold set.** Exploratory pulls (`--param`, `--term`, `--scratch`) go to `data/scratch/` and never enter a gold set.
- **Secrets stay out.** The NCBI key and email are removed from every URL, log line and output. Fetched text is printed inside clear delimiters, as data and not instructions.
- **Licences graded per article** (CC BY is B, CC BY-NC-ND is D-, custom or all rights reserved is F). Below B- is marked `do_not_redistribute`.
- **Labels.** One labeller's labels are never overwritten or merged with another's; a case counts as confirmed only when two different humans agree. Rule-made labels never count as confirmed.
- **Terms.** ClinicalTrials.gov asks for attribution, the processing date and a note of modifications; stored files are dated snapshots. Contact names, emails and phones are removed from derived outputs.

## Layout

```
aegir_ran/   the package: fetchers, change analysis, batch builder, labelling app (uses ../shared/aegir_core)
tests/       unit tests and synthetic fixtures; stress_amend.py needs fetched data
config/      named queries and ncbi.example.json (rate limits and grades are in ../shared/config)
demo/        16 real cases and their attribution
data/        what RÁN fetches and records (ignored by git, except data/README.md)
docs/        STATUS.md and the diagrams
build/       build.ps1 and ran.spec: builds a portable RAN.exe (Windows; needs PyInstaller, see requirements-build.txt)
```

Build the exe: `powershell -ExecutionPolicy Bypass -File build\build.ps1` (puts `RAN.exe` in this folder; double-clicking it starts the labelling tool).

Licence: Apache-2.0, see the repository [LICENSE](../LICENSE). This folder contains no ClinicalTrials.gov, PubMed, PMC or Europe PMC data beyond the attributed demo.
