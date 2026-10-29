# AEGIR / RÁN

**AEGIR** (Amendment Evidence Gathering and Independent Review) is a research prototype for studying how clinical-trial
protocols change after they start, and whether those changes were avoidable. **RÁN** (`aegir_ran`, "Registry and Article Net")
is its data tool: it fetches public trial and article data, stores it unchanged and traceable, flags what changed between registry
versions by plain rules, and runs a local app for a person to label the changes.

This repository is a **snapshot of development** (29 Oct 2026), built by Claude (Claude Code) with David, with design work done in
Claude (Cowork). It holds the working code, tests, settings and diagrams. It does not hold any fetched data, labels, or the
planning documents. It is not a finished product and not a guide for rebuilding the project from scratch.
How far along it is, honestly: [docs/STATUS.md](docs/STATUS.md). Pictures: [docs/ran-overview.html](docs/ran-overview.html)
(or [how it works](docs/ran-how-it-works.svg) and [capabilities](docs/ran-capabilities.svg)).

## What works

| Area | State |
| --- | --- |
| ClinicalTrials.gov search and records (API v2) | works, used on a 433-trial COPD pool |
| Registry version histories | import of files saved in your own browser works; the script path is refused by the site and RÁN does not work around it |
| PubMed search and fetch, PMC licence per article, licence grades | works |
| Europe PMC licence lookup | works on single PMIDs; slow by design (one PMID per request) |
| Label flags and content flags (rule-based change analysis) | works; stress-tested; not reviewed by a clinician |
| Matched batches, batch audit, labelling app, tally, efficiency report | works; one labeller so far |
| Demo with real data and a portable `RAN.exe` | works (Windows exe; source on any system) |
| Not built | second-labeller agreement and adjudication, gold-set export, expert calibration |

No language model is used anywhere in the tool. Every result comes from a logged request or a plain rule.

## Try the labelling app in one minute (real demo data)

`demo/` holds 16 real cases from ClinicalTrials.gov (COPD trials, 138 KB), with their provisional labels and findings, so you can try the
labelling app without fetching anything. Source, date, modifications and terms are in [demo/ATTRIBUTION.md](demo/ATTRIBUTION.md); the app also
shows them in a banner. The data are a dated snapshot, not current.

- **Windows, no Python or build needed:** download `RAN.exe` from the repository's **Releases** page and double-click it. Enter a name; with
  no batches of your own it opens the demo. Your labels and notepad are written to a `data/` folder beside the exe. The exe is unsigned, so
  Windows SmartScreen may warn ("More info", then "Run anyway"); you can check its SHA-256 against the value in the release notes.
- **From source (any system with Python 3.10+):**
  ```bash
  cd tool
  python -m aegir_ran labels serve --labeller yourname --batch demo
  ```

## Quick start

You need Python 3.10 or newer. There are no packages to install: the tool uses only the standard library.

```bash
# from the repository folder
python -m unittest discover -s tool/tests          # 41 offline tests, no network
cd tool
python -m aegir_ran --help                         # all commands
python -m aegir_ran status                         # counts, last fetch, whether a key is configured
python -m aegir_ran ctgov search --query-id copd-p23-2010-2020 --dry-run    # shows the request, sends nothing
```

(Or set `PYTHONPATH=tool` and run from the repository folder.) Every command ends with one JSON line saying what it did:
counts, files written, requests used, errors. Add `--dry-run` to see the requests and an estimate first.

**Or make synthetic cases.** Five invented cases, served on your own machine only (127.0.0.1):

```bash
cd tool
python -m aegir_ran labels build-batch --synthetic 5 --name demo
python -m aegir_ran labels serve --labeller yourname --batch demo
```

Keys are listed behind `?` on the page. Your labels and notes go to `data/labels/yourname/`.

## NCBI API key (optional, recommended for PubMed and PMC)

Without a key NCBI allows 3 requests a second; with one, 10. RÁN reads the key from the environment or a local file, and never prints,
logs or stores it.

1. Sign in at <https://account.ncbi.nlm.nih.gov/settings/> (NCBI account, **Settings**, **API Key Management**). Create a key.
2. Copy `config/ncbi.example.json` to `config/ncbi.local.json` and fill it in:
   ```json
   { "api_key": "your key", "email": "you@example.org" }
   ```
   The email is sent with every request so NCBI can contact you; `.gitignore` already excludes `config/*.local.json`.
   Or set the environment variables `NCBI_API_KEY` and `NCBI_EMAIL` (they win over the file).
3. Check it: `python -m aegir_ran status --check-key`. It reports whether NCBI accepted the key and the rate limit, never the key.

Europe PMC needs no key.

## Rebuilding data (small example)

Nothing fetched is shipped, so build what you need. The COPD pool as an example:

```bash
cd tool
python -m aegir_ran ctgov search --query-id copd-p23-2010-2020          # about 2 requests, 400+ trials
python -m aegir_ran ctgov import-history <folder-of-history-files>      # see "History files" below
python -m aegir_ran derive label-flags   --pool copd-p23-2010-2020      # index-only pre-screen
python -m aegir_ran derive content-flags --pool copd-p23-2010-2020      # reads the real text of stored versions
python -m aegir_ran labels build-batch --from data/derived/<the content_flags file> --positives 50 --negatives 50 --seed 28 --name my-batch
python -m aegir_ran labels serve --labeller yourname --batch my-batch
```

Articles and licences (the "Track 2" side):

```bash
python -m aegir_ran pubmed search --query-id trials-updates             # queries live in config/queries/
python -m aegir_ran pubmed fetch <PMID> ...                             # batched, 200 per request
python -m aegir_ran pmc licence <PMCID> ...                             # licence from the article record, graded
python -m aegir_ran epmc licence --from-query trials-updates            # optional second source, one PMID per request
```

A query is a small JSON file in `config/queries/`: for ClinicalTrials.gov `{"id", "source": "ctgov", "params": {...}}`,
for PubMed `{"id", "source": "pubmed", "term": "..."}`. Changing a query means a new `id`.

**History files.** The registry's internal history endpoint answers scripts with HTTP 403, so version histories have to be saved from
your own browser session (small volumes) and imported. `ctgov import-history` accepts files or a folder of: an index named
`NCT########_history.json` (`{"nct_id", "changes": [{"version", "date", "moduleLabels", ...}], "provenance": {...}}`) and versions named
`NCT########_v<N>.json` (`{"studyVersion": N, "study": {"protocolSection": ...}, "provenance": {...}}`), or one bundle
(`{"nct_id", "index", "versions": {...}}`). Each import records `"collected_via": "user browser"`. For bulk access, ask NLM
(ClinicalTrials.gov support) about a supported channel.

## Rules the tool keeps

- **Append-only.** Nothing is deleted or overwritten under `data/`: every fetch is a new dated file with a `.meta.json` sidecar (url, time,
  sha256, grade, how collected). Catalogues are JSON Lines and the latest line per key wins. No SQLite, no git inside `data/`.
- **Polite.** Limits are shared across processes (`state/rate.json`): ClinicalTrials.gov 40 requests a minute, NCBI 3 a second (10 with a key),
  Europe PMC 50 a minute with 30/60/120 s back-off. Each command has a request budget (default 500; `--max-requests`). A job estimated at
  over 1,000 NCBI requests is refused on weekday daytime (US Eastern) unless you pass `--daytime-ok`; run big jobs at night or at weekends.
- **Cache first.** Anything already catalogued is not fetched again unless you pass `--refresh`.
- **Named queries only for the gold set.** Exploratory pulls (`--param`, `--term`, `--scratch`) go to `data/scratch/` and are never
  eligible for a gold set or a snapshot.
- **Secrets stay out.** The API key and email are removed from every URL, log line, sidecar and printed output.
- **Fetched text is data, not instructions.** Anything printed from fetched text is wrapped in clear delimiters.
- **Registry limits are respected.** No browser impersonation or workarounds for the history endpoint.
- **Licences are graded per article** (CC BY is B, CC BY-NC-ND is D-, custom or all-rights-reserved is F). Anything below B- is marked
  `do_not_redistribute`; full text is stored only at or above the configured grade.
- **Terms.** ClinicalTrials.gov asks for attribution, the processing date and a note of modifications; stored registry files are dated snapshots
  and say so in their sidecars. Contact names, emails and phone numbers are removed from derived outputs. Follow NCBI, PMC and Europe PMC
  usage policies, and do not publish fetched article text you have no licence to share.
- **Labels.** One labeller's labels are never overwritten or merged with another's; a case counts as confirmed only when two different
  humans agree. Provisional (rule-made) labels never count as confirmed.

## Layout

```
tool/aegir_ran/     the package (fetchers, change analysis, batch builder, labelling app)
tool/tests/         unit tests, fixtures (synthetic), stress_amend.py (needs fetched data)
config/             settings, licence grades, named queries, ncbi.example.json
demo/               16 real ClinicalTrials.gov cases for trying the labelling app, with ATTRIBUTION.md
build/              build.ps1, ran.spec: builds a portable RAN.exe (Windows, needs PyInstaller via requirements-build.txt)
docs/               STATUS.md and the diagrams
data/  state/       created when you run things; ignored by git
```

To build the portable executable on Windows: `powershell -ExecutionPolicy Bypass -File build\build.ps1`. It places `RAN.exe` in the
repository folder; running it with no arguments starts the labelling tool. It is unsigned, so Windows SmartScreen may warn.

## Limits to know about

The change-analysis rules are Claude's reading of published standards (EU Clinical Trials Regulation, SPIRIT and CONSORT 2025, COMPare, Tufts CSDD),
tuned on a small set of labels, and **have not been reviewed by a clinician or methodologist**. Treat their output as provisional.
Details and the test results are in [docs/STATUS.md](docs/STATUS.md).

## License

The code, tests, settings and diagrams in this repository are licensed under the [Apache License 2.0](LICENSE).

**Copyright holder: not filled in yet.** The name and year are to be added later; there is no `NOTICE` file or per-file copyright header
for now, and the `LICENSE` file is the unmodified Apache-2.0 text.

This repository contains no ClinicalTrials.gov, PubMed, PMC or Europe PMC data. Anything you fetch with it stays under the source's own
terms and licences, which the Apache licence does not change.
