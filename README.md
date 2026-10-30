# AEGIR

**AEGIR** (Amendment Evidence Gathering and Independent Review) is a research prototype for testing whether a protocol review can catch
avoidable clinical-trial problems in advance. To test that, it needs labelled outcomes at two scales: a large **silver set** made by machine
across the whole ClinicalTrials.gov registry, and a small **gold set** labelled by humans. This repository holds the two programs that build them. The
review engine itself is not here yet.

| Program | Folder | What it does | Use it for |
| --- | --- | --- | --- |
| **AutoRAN** (main) | [`AutoRAN/`](AutoRAN/) | Downloads the registry, labels each trial's outcome (completed, or stopped for failing to recruit) from its stop reason, scores predictors against those labels, and lets a person supervise at scale. Windows desktop app plus command line | the silver set |
| **RÁN** | [`RAN/`](RAN/) | Fetches trial and article data, flags how protocols changed between registry versions by plain rules, and runs a local labelling app for humans. Standard library only | the gold set (kept separate for now) |
| shared | [`shared/`](shared/) | The code and settings both use: polite HTTP client, append-only store, text cleaning, licence grades | |

## Start here

- **AutoRAN:** download `AutoRAN-lite-win64.zip` from the [latest release](https://github.com/JormundgandrEKA/AEGIR-open/releases/latest), unzip, double-click `AutoRAN\AutoRAN.exe`.
  Read [AutoRAN/README.md](AutoRAN/README.md) and [AutoRAN/DISCLAIMERS.md](AutoRAN/DISCLAIMERS.md) first.
- **RÁN:** download `RAN.exe` from the [RÁN snapshot release](https://github.com/JormundgandrEKA/AEGIR-open/releases/tag/v0.1.0-snapshot), or see [RAN/README.md](RAN/README.md). It opens on 16 real demo cases.
- **Either from source:** clone the whole repository (the programs need `shared/`), then follow that program's README.

## Where it stands (30 Oct 2026)

- AutoRAN: 266,916 trials fetched and labelled; 7,486 recruitment failures. The stop-reason labeller reaches 93.9% precision and 69.5% recall on a held-out curated test.
  **No human has checked its labels on real registry text yet.** The best baseline predictor reaches an AUROC of about 0.75. Details: [AutoRAN/docs/build-report.md](AutoRAN/docs/build-report.md).
- RÁN: 31 labels from one labeller on a 433-trial COPD pool; its change-analysis rules have not been reviewed by a clinician or methodologist. Details: [RAN/docs/STATUS.md](RAN/docs/STATUS.md).
- This is a **snapshot of development**, not a finished product. Built by David O'Rourke with Claude (Claude Code); design work by Claude (Cowork).

## Rules both programs keep

- **Append-only.** Fetched files are never overwritten or deleted; each has a sidecar with url, time, checksum, grade and how it was collected.
- **Polite.** Shared rate limits (in [`shared/config/aegir.json`](shared/config/aegir.json)), request budgets, back-off, and no workarounds for sources that refuse scripts.
- **Graded sources.** Every source has a licence grade; nothing below the floor is redistributed.
- **No personal data.** Contact names, emails and phone numbers are never kept.
- **No language model inside either tool.** Every result comes from a logged request or a plain rule or statistical model.
- **Human labels stay human.** Machine labels are always provisional or "silver"; only people confirm gold labels.

## Layout

```
AutoRAN/   the main program: its own README, config, tests, docs, build files
RAN/       the answer-key program: its own README, config, tests, docs, demo, build files
shared/    aegir_core (code) and config/ (rate limits, grades) used by both
LICENSE    Apache License 2.0
```

Each program keeps its own `data/` and `state/` (ignored by git); this repository contains no ClinicalTrials.gov, PubMed, PMC, Europe PMC or Open Targets data.

## Licence and data terms

Code, tests, settings and diagrams: [Apache License 2.0](LICENSE). Data you fetch stays under its source's own terms (ClinicalTrials.gov asks for attribution,
the processing date and a note of modifications; follow NCBI, PMC and Europe PMC policies). Neither NLM nor any data provider endorses this project.
Software and data attributions: [AutoRAN/THIRD_PARTY.md](AutoRAN/THIRD_PARTY.md).
