# RÁN status: a snapshot of development

> This file covers **RÁN** only. For AutoRAN, the main tool, see [`AutoRAN/docs/build-report.md`](../../AutoRAN/docs/build-report.md).


Snapshot of 29 Oct 2026. Tool: RÁN (`aegir_ran`) 0.1.0, part of AEGIR (Amendment Evidence Gathering and Independent Review). Built by David O'Rourke with Claude (Claude Code); written for Claude (Cowork), the design side of the project. This is a status report on what exists and how well it works. It is not a build guide.

Pictures: [how it works](ran-how-it-works.svg), [capabilities, built and to build](ran-capabilities.svg), or both on one page: [ran-overview.html](ran-overview.html).

## 1. State in one paragraph

RÁN fetches public trial and article data, stores it unchanged with provenance, flags registry changes by rules, and
serves a local labelling app. The COPD pool is fully loaded (433 trials, 433 version indexes, 152 trials with 401 version
files) and one labeller has given 31 labels so far. The five Track 2 PubMed searches have also been run (7,361 PMIDs found; 96 articles and 372 licences fetched so far). The change-analysis rules are stress-tested and agree with the labeller on
30 of 31 cases, but were tuned on those cases and have not been reviewed by a clinician or methodologist. The next real
bottleneck is data, not code: there are only 36 clean negatives, and there is no second labeller yet.

## 2. Technical summary

**Shape.** Python 3.10+, standard library only, about 3,700 lines in 19 modules (`aegir_ran/`; since 30 Oct the client, store, context, text cleaning and grades live in `../../shared/aegir_core/`, shared with AutoRAN), plus about 660 lines of
tests. One entry point, `python -m aegir_ran <group> <command>` or `RAN.exe` (PyInstaller one-file, about 8 MB, build files in
`build/`; the exe itself is not in this repository). Every command ends with one JSON summary line. Running `RAN.exe` with no arguments starts the labelling tool.

**Data rules (unchanged from the design).** Append-only: raw files plus `.meta.json` sidecars (url, time, sha256, grade,
how collected); catalogues are JSON Lines, latest line per key wins; no deletes, no SQLite, no git in `data/`. Exploratory
pulls go to `data/scratch/` and cannot enter the gold set; a gold-set pull needs a named query in `config/queries/`.

**Guard rails for model use (section 3.3 of the design), all in code.** Rate limits shared across processes
(`state/rate.json`, file lock); request budget (default 500); NCBI weekday-daytime refusal above 1,000 requests; API key
and email redacted from every URL, log and output (checked: not found in any stored file); retries with back-off (30/60/120 s
for Europe PMC); fetched text printed only inside untrusted-text delimiters; truncated reads are retried.

| Module | Job |
| --- | --- |
| `http.py`, `core.py`, `context.py` | client, limits, budget, redaction; store, sidecars, catalogues |
| `ctgov.py` | search, study, history (blocked live), `import-history` (browser files, folders accepted) |
| `pubmed.py`, `pmc.py`, `epmc.py`, `link.py` | articles, licences and grades, Europe PMC licence, registry-article links |
| `textclean.py` | HTML and markdown to plain text (the source of the "formatting markers" bug) |
| `derive.py` | `label-flags` (T12 rule), `content-flags` (rule v2), `diff` |
| `amend.py` | the change analysis: findings, direction, suggestions, provisional label text |
| `taxonomy.py` | every label option and definition, with the standards behind them |
| `batches.py` | matched batch builder, synthetic cases, `labels audit` |
| `labels.py`, `labels_ui.py` | local server (127.0.0.1, Host-checked) and the single-page app |
| `reports.py` | status, tally (two-human confirmation), efficiency, attribution, snapshot |

**Labelling app.** Keyboard-first. Shows every changed field as before/after word diffs, collapsed to changed parts (F for
full), a field table (age, sex, enrolment), the question, and on the right each option with its definition. Provisional label
is revealed on request (hidden for about 10% of cases by design); notepad is always on screen and autosaved; drafts
autosave; timing is passive (active seconds only). Writes `gold-label/0.1` records plus session events.

## 3. Methodology

**Fetching.** Named queries only for gold-set pulls; ClinicalTrials.gov API v2 for current records; version histories only
through the maintainer's browser (the registry's internal history endpoint refuses scripts, and RÁN does not work around that); NCBI E-utilities with key;
PMC licence read from the article record; Europe PMC one PMID per request.

**Flags.** Two layers, kept apart. *Label flags* (T12 rule, from version indexes only) are a cheap pre-screen and reproduce 159
positives and 208 negatives. *Content flags v2* compare the actual text of each in-window version with a baseline (last version
on or before the start date, else the earliest) using `amend.py`.

**Change analysis (`amend.py`).** Normalise (markup, case, symbols, units, plurals, accents, "long form (ACR)" to the acronym), split
eligibility into criteria under Inclusion and Exclusion, match criteria across versions in stages, then classify each
difference: criterion added (narrows) or removed (broadens); threshold changed, with direction read through the section;
boundary changed; qualifier changed; content reworded; moved between sections; age, sex and volunteer limits; enrolment target
(planned replaced by actual is not an amendment); arms and interventions; per primary outcome: added, removed, variable, metric or
cut-off, time point. Spelling, acronym, format and near-identical wording are non-substantive. The standards used:
EU CTR 536/2014 Art. 2(2)(13) for "substantial" and severity, SPIRIT 2025 items 14/16/19/31 and CONSORT 2025 for eligibility
and outcome elements, COMPare categories for outcome changes, Tufts CSDD for the avoidability scale and causes.

**Labelling design.** 50 positives plus matched negatives (phase, sponsor class, start year, relaxing in that order), shuffled so
the labeller cannot tell which is which, about 10% with the provisional label hidden to measure anchoring, one labeller first, nothing
is "confirmed" until two different humans agree. Model labels are always provisional.

## 4. Tests

| Test | What it covers | Result |
| --- | --- | --- |
| Unit tests, 41 (`python -m unittest discover -s RAN/tests`) | licence parsing and grades (4), PubMed parsing and links (2), store rules and redaction (4), history import, diff, label flags (4), client budget/retry/limits (4), tally (1), content flags, Europe PMC, notepad, window, server loopback (9), change analysis (10), drafts and answer schema (1) | all pass |
| Stress test (`python RAN/tests/stress_amend.py <seed>`) | 398 real stored eligibility texts, about 4,500 known edits per seed, seeds 28, 7, 99 | harmless edits 0-2.9% false alarms; real edits detected 97-100% |
| Real labels | analysis vs the labeller's 31 labels, on the field shown | 30 of 31, kappa 0.93 (old provisional 28 of 31, kappa 0.78). Tuned on these cases, so optimistic |
| Batch audit (`labels audit`) | 11 randomised 50/50 batches (seeds 28, 101, 2026 and eight more) | found markup residue, the negatives shortage; both reported below |
| Live checks | ClinicalTrials.gov search, PubMed fetch, PMC licence (372), Europe PMC (2), key check, exe launch | pass |
| Browser check | page rendering, keyboard answers, reveal, notepad, save, quit | pass on synthetic and real cases |

The stress test's first run caught real bugs (99% false alarms on extra whitespace, 18% of swapped words detected). They are
fixed; the lesson is that the rules should be re-run through this test whenever `amend.py` changes.

## 5. Strong points

- Provenance and append-only storage hold everywhere; the key never reaches a file.
- Rules are plain and inspectable: every provisional note lists each finding with before/after text and says what was not examined.
- The labelling form is grounded in named standards and defines every option on screen.
- Reproducible: the T12 counts, the stress test and the batch audit can all be re-run from the command line.
- Portable executable and a no-argument launcher.
- The labeller overrode the old provisional label in 17% of reveals, so the anchoring risk looks modest so far (n is small).

## 6. Weak points

- **The rules are not validated by a professional.** They are my reading of the standards; no published agreement figures exist for
  classifying eligibility changes.
- **Tuned on 31 cases**, and 11 of them positive. The stress test is synthetic edits, not real amendments.
- **Negatives are scarce and fixed**: 36 clean negatives, the same in every batch. Only positives change with the seed.
- Eligibility analysis depends on the registry text being line-structured. Free-prose criteria (no bullets) are weak: items
  become whole paragraphs.
- Word-swap and removal detection (97-98%) misses cases where the dropped or swapped text also appears elsewhere.
- The batch audit counts all finding kinds under "positive kinds" (substantive and not); minor.
- About a third of cases have a baseline registered after the start date, so "before" is not a pre-enrolment protocol.
- Single labeller: no agreement statistics are possible yet. Only Windows was exercised.

## 7. Gaps (built but unproven, or missing)

- Europe PMC lookup run through RÁN on 2 PMIDs only (a separate 283-PMID sample was run with interim scripts that are not part of this repository); at one PMID per request a 5,665-PMID sweep takes about two hours.
- `link from-registry` / `from-pubmed` (0 links stored), `pmc fulltext` and `attribution`: tests only.
- `snapshot` copies the search file and histories, not individual study files.
- No second-labeller flow: tally reports "one human label" per case; there is no adjudication screen.
- No expert calibration set; no anchoring report (provisional shown vs hidden); no gold-set export with the licence gate.
- Track 2: the five PubMed queries are defined in `config/queries/` and have been searched, but only 96 of the 7,361 articles have been fetched and 372 licences checked. The `note` fields mention task codes (T12, T18) from a planning document that is not included here.
- Existing labels in `v0-shallow` and `v0-shallow-b` use the earlier, simpler form and do not map one-to-one to the new one.

## 8. Potential improvements (suggested order)

1. Collect version files for about 50 label-negative trials (last pre-start and last in-window version, same format as the 401).
   This gives 100 clean negatives and varied draws.
2. Second labeller, then `tally` with Cohen's kappa and a disagreement list; a small adjudication screen for split labels.
3. A calibration set: about 30 provisional notes reviewed by a clinician or trial methodologist; revise `amend.py` from their comments.
4. Anchoring analysis from the existing logs (provisional shown vs hidden: agreement, time per case).
5. Fetch the articles and licences for the two small Track 2 sets (`trials-updates`, `trials-protocols-copd`; 97 PMIDs) and review them; run the large sets overnight or at a weekend.
6. Better handling of prose criteria (sentence splitting) and of structured age text; outcome description fields (not yet compared).
7. Snapshot with study files and the licence gate; signed exe or an installer; Mac and Linux checks.

## 9. Feature completeness against the design

AutoRAN, the main tool, is not part of this table: see [`AutoRAN/docs/build-report.md`](../../AutoRAN/docs/build-report.md).

| Design item | Status |
| --- | --- |
| `ctgov search`, `study`, `import-history` | built, used on real data |
| `ctgov history` | built; the endpoint refuses scripts (by design, import path used) |
| `pubmed search`; `pubmed fetch`; `pmc licence`; `grade` | built, used on real data (5 searches, 96 articles, 372 licences) |
| `link *`; `pmc fulltext`; `attribution` | built, tests only |
| `epmc licence` | built, 2 PMIDs live |
| `derive flags` (T12), `derive content-flags`, `derive diff` | built, used on real data |
| `labels build-batch`, `serve`, `audit` | built, used on real data |
| `report efficiency`, `tally`, `status` | built, used |
| `snapshot` | built, incomplete (no study files) |
| Second labeller, adjudication, kappa | not built |
| Track 2 articles and licences at scale | searches done; fetching mostly not done |

My rough completeness by area, as a judgement (not a measurement): fetch and store 92%, derive and flags 85%, labelling tool 80%,
reports and QA 70%, gold-set export 30%, second-labeller flow 15%.

## 10. Open decisions

1. Two rule choices: planned-to-actual enrolment (now not an amendment) and post-start baselines (now kept, marked in the batch `_design`).
2. A reviewer for the rule findings (item 3 above), and a second labeller.
3. Whether to fetch and review the two small Track 2 sets now.
4. About 100 extra version files for clean negatives would have to be collected by the maintainer in their own browser.
5. Licence: Apache-2.0 is in place, but the **copyright holder (name and year) is not filled in**; add it later, with a `NOTICE` file or file headers if wanted.

## 11. Where things are in this repository

- Code `aegir_ran/`; tests `tests/` (unit tests, `stress_amend.py`); build `build/build.ps1`.
- Settings `config/`; named queries `config/queries/`.
- Not included: `data/` (fetched and derived data, labels, notepads), `state/`, `config/ncbi.local.json`, the built exe, and the planning and hand-off documents. See the README for how to rebuild the data.
