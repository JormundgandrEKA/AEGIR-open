# AutoRAN: design v0.1

> **Historical:** design v0.1 as handed to the build. Departures (no longer standard-library only, a desktop app instead of a local server, naive Bayes instead of BERT, the `never_updated` input state) are in `build-report.md`, section 7 ("Where this departs from the design") and section 10.

Date: 30 Oct 2026. Author: design (Claude, Cowork) for the user; build by Claude Code.
Read with `fetcher-design.md` (RÁN, whose rules still apply) and `CLAUDE.md`.
Tags: [U] user decision or request, [C] design proposal, [Code] to verify or decide during the build.

---

## 0. Name

**AutoRAN**: Rán's net cast on the tide, so it hauls in by itself. Its output is the **silver set**
(Ægir's silver): weakly labelled, machine-made, large. The **gold set** stays the small, human-confirmed
answer key built with RÁN. Silver is for volume and testing; gold is for claims.

## 1. Purpose

[U, 30 Oct] Build an automated RÁN-type system for testing that:
1. **fetches** as many trials as can be found from sources graded **B− or better**;
2. **labels** each trial automatically;
3. **categorizes** each trial (therapeutic area, phase, sponsor, stop reason and so on);
4. **displays metrics** and lets a person **inspect findings** inside the tool.

Use: the first **causal prototype**. Does a protocol review (later, the AEGIR review engine; for now,
baseline scorers) pick out, in advance, trials that went on to **fail to recruit**? Recruitment failure
is the most common avoidable failure (over a third of stopped trials) and can be labelled without a
human.

Not in scope: judging amendments as substantive or avoidable (that stays RÁN plus human labellers),
predicting efficacy or safety, and any language-model call inside the tool (CLAUDE.md rule kept; the
reviewer is a separate plug-in, section 9).

## 2. Size of the job (measured 30 Oct 2026, ClinicalTrials.gov API v2, `countTotal`)

| Slice | Trials |
|---|---|
| All interventional | 465,123 |
| Interventional, start 2005+, completed or terminated | 266,916 |
| ... of which Phase 2 or 3 (**default scope**) | **71,901** |
| Terminated, Phase 2/3, start 2005+ | 12,284 |
| ... with a recruitment-family word in `whyStopped` | about 3,890 (32%) |

So the default scope gives about **3,900 positives against about 59,600 completed trials**, enough for
tight metrics (±1–2 points). At 1,000 studies per page that is about 72 pages; the full download is
minutes, not hours, at the existing 40 requests/min limit.

## 3. Sources and grades (B− floor enforced in code)

| Source | Use | Licence | Grade | Notes |
|---|---|---|---|---|
| ClinicalTrials.gov API v2 (current records) | trials, fields, whyStopped, MeSH | public, NLM terms | A+ | attribution plus processing date, as RÁN does now |
| ClinicalTrials.gov references in records | linked PMIDs | public | A | |
| Open Targets curated stop reasons (`opentargets/clinical_trial_reason_to_stop`, about 5,000 texts, 17 classes) | train and **measure** the stop-reason labeller | Apache 2.0 | **B−** [C; U to confirm] | Apache is permissive with attribution and notice, equivalent in effect to CC BY |
| Open Targets stop-reason model (BERT) | optional labeller, section 6.2 | Apache 2.0 | B− [same] | needs a non-stdlib extra |
| Europe PMC / PMC licence per paper | only for papers linked to positives | per paper | B (CC BY) | one request per paper |
| RÁN version histories (browser-collected) | clean *first-version* inputs | public | A− | pilot volume only; section 5 |

Refused at ingest (below B−): TrialBench (NC), Anamnesis sample (CC BY-NC), CTO is MIT but measures
efficacy (out of scope; may be added later as a control only), anything without a licence.

**Rule:** every stored record carries `source`, `grade` and `licence`. `export` refuses any record
below the configured floor (`config/autoran.json: "grade_floor": "B-"`). Grades live in `config/grades.json`
(extend it, don't fork it).

## 4. Pipeline

```
 fetch ──> normalise ──> label ──> categorize ──> split ──> metrics ──> serve (dashboard + inspector)
   │                       │                                   ▲
   │                  stop-reason labeller              scorers (plug-ins: baselines now,
   │                  (rules / exact match / model)      AEGIR review later)
   └─ delta updates nightly (LastUpdatePostDate)
```

Commands (new group `autoran` in the same CLI, `python -m aegir_ran autoran <cmd>` and `RAN.exe autoran <cmd>`):

| Command | Does |
|---|---|
| `autoran fetch [--full \| --delta] [--scope default]` | page the API with `fields=` limited to the modules in section 4.1; store gzip pages plus sidecars |
| `autoran label` | apply the stop-reason labeller and the outcome rules (section 6) |
| `autoran categorize` | attach categories (section 7) |
| `autoran split` | deterministic train/dev/test by NCT hash (test 20%, frozen, R7) |
| `autoran score --scorer <name>` | run a scorer plug-in over a split |
| `autoran metrics` | recompute every metric (section 8) into `data/derived/autoran_metrics_<stamp>.json` |
| `autoran serve` | local dashboard and inspector, 127.0.0.1 only (section 10) |
| `autoran audit-sample --n 200 --class positive` | draw a seeded sample for human spot-checks in the inspector |
| `autoran export --grade-floor B-` | silver-set file with licence manifest and ClinicalTrials.gov attribution |
| `autoran run` | fetch delta, then label, categorize, metrics; for the scheduler; one JSON summary line |

### 4.1 Fetch details
- Query: `filter.advanced = AREA[StudyType]INTERVENTIONAL AND AREA[StartDate]RANGE[2005-01-01,MAX]`, `filter.overallStatus = COMPLETED|TERMINATED`; phase filter from `config/autoran.json` (default Phase 2 and 3; "all" allowed).
- `fields=` limited to: identification, status (including whyStopped and dates), sponsor/collaborators, conditions plus `derivedSection.conditionBrowseModule` (MeSH tree), design (phases, allocation, masking, enrollmentInfo), arms/interventions, outcomes, eligibility, contactsLocations **counts only** (strip names, keep `locations` country and count), references. [Code: confirm the field names and the size per study; target < 10 KB.]
- Storage: `data/raw/ctgov/autoran/<stamp>/page_NNNN.json.gz` plus `.meta.json` (url, params, time, sha256, grade A+, terms URL, API `dataTimestamp` from `/api/v2/version`).
- Delta: `AREA[LastUpdatePostDate]RANGE[<last run>,MAX]`; later lines win in the catalogue (append-only, as RÁN).
- Politeness: existing shared limiter, 40/min, `--max-requests` budget, back-off. No history endpoint calls, ever.
- Personal data: drop `centralContacts`, `overallOfficials` and location contacts at normalise time (spec section 10); never stored in derived files.

### 4.2 Normalised record (`data/derived/autoran/trials_<stamp>.jsonl`, one line per trial, about 1–2 KB)
`nct_id, status, why_stopped, start, primary_completion, completion, first_posted, last_update, phases, sponsor_class, n_sites, countries, enrollment {type, count}, eligibility {text_hash, n_inclusion, n_exclusion, min_age, max_age, sex, healthy_volunteers}, n_primary_outcomes, n_arms, allocation, masking, conditions, mesh_ancestors, pmids, input_state, source, grade, data_timestamp`.
The full text stays in the gz page; an offset index (`trials_<stamp>.idx.json`) lets the inspector read one study on demand. Store no SQLite (append-only rule kept; JSONL is loaded into memory at serve time, which is fine at about 100 MB).

## 5. Hindsight contamination (the main accuracy risk)

The causal test needs the protocol **as written before trouble**. A current record already includes later
fixes (in the COPD pilot about 40% of trials changed eligibility or outcomes mid-enrolment). ClinicalTrials.gov
refuses scripted history access and AutoRAN will not work around that.

Design:
- Every record gets `input_state`:
  - `first_version`: a RÁN browser-collected baseline exists (clean);
  - `current_unchanged`: the last update was submitted before the start date (clean by construction; [Code] measure how many);
  - `current`: possibly contaminated.
- Metrics are reported **three ways**: all; clean only (`first_version` + `current_unchanged`); and the difference. A large difference means contamination is driving results.
- [Code: check whether API v2 exposes original-versus-current outcome measures; the old site showed "Original Primary Outcome Measures". If yes, add `outcome_changed` as a free contamination flag.]
- Scaling clean inputs beyond pilot volume needs a supported channel: [U decision] contact NLM (design can draft the message). Until then, the browser route stays at pilot volume (for example 100–200 first versions per session, positives first).

## 6. Labels

### 6.1 Outcome classes (per trial)
| Class | Rule |
|---|---|
| `positive_recruitment` | status TERMINATED and stop reason labelled Insufficient_Enrollment |
| `negative_completed` | status COMPLETED; actual enrollment ≥ 1 |
| `other_stop` | TERMINATED for any other reason (kept and categorized; excluded from the binary task by default) |
| `unlabelled` | TERMINATED with empty or uninformative whyStopped (`No_Context`, `Invalid_Reason`) |

Known limitation (shown in the UI): the original *planned* enrollment is lost once the actual is posted, so
"completed but badly under-enrolled" cannot be detected from current records. It is labelled negative;
the clean subset (first versions) can recover the planned number. Record this as `label_caveats`.

### 6.2 Stop-reason labeller (17 Open Targets classes), in three tiers, each recorded in `label_source`
1. **exact**: whyStopped text matches a curated Open Targets example (after normalising case and space) → that label, confidence 1.0.
2. **rules** (stdlib, default): ordered keyword and regex rules per class, with negation handling ("not due to safety"). Built and tuned on the curated set's *train* part, measured on its held-out part; per-class precision and recall are shown in the dashboard. Starting rule for Insufficient_Enrollment: recruit/enrol/enroll/accru/accrual/"slow"/"poor"/"low" + participant words. In the COPD pilot the simple regex was a usable pre-screen.
3. **model** (optional extra `autoran[model]`, not stdlib): the Open Targets BERT classifier. It runs only if `transformers` and `torch` are installed in the build venv; it never becomes a hard dependency of `RAN.exe`. Where rules and model disagree, the record is flagged `labeller_disagree` and surfaced in the inspector.

Every label line: `{nct_id, class, stop_class, label_source, confidence, rule_id|model_version, evidence_span, labelled_at, autoran_version}`.

### 6.3 Human spot-checks (measured silver accuracy)
`audit-sample` draws seeded samples (default 200 positives, 200 negatives, 100 other_stop). The user judges each in the inspector (agree / disagree / unsure plus note; keyboard; 10–20 s each). The dashboard shows **estimated precision per class with a 95% Wilson interval** (200 checks ≈ ±7 points). Audits are written to `data/labels/<labeller>/autoran_audit.jsonl`; this is the only human step and it is optional for running, required for any claim.

## 7. Categories (all from registry fields, no inference)
Therapeutic area (top-level MeSH tree from `conditionBrowseModule`; multiple allowed), phase, sponsor class
(industry / NIH / other / network), start-year band, region (from site countries), single versus multi-site,
allocation and masking, intervention type, stop-reason class, input_state, grade. Each is a filter in the
dashboard and a breakdown in metrics.

## 8. Metrics (computed by `autoran metrics`, shown by `serve`)

**Pipeline health:** studies fetched, pages, requests, retries, errors, last run, delta size, runtime,
API data timestamp, disk used.

**Coverage:** trials by status, phase, area, year, sponsor; share with whyStopped; class counts; grade counts; input_state counts.

**Label quality:**
- stop-reason labeller versus the curated held-out set: accuracy, macro-F1, per-class precision and recall, confusion matrix;
- rules versus model agreement (if the model is installed);
- human audit precision per class with Wilson CI;
- share of `unlabelled`.

**Prediction (per scorer, per split, all versus clean):** AUROC and AUPRC with bootstrap 95% CI (1,000
resamples, seeded); precision at top 5% and 10%; calibration table (10 bins); the same broken down by
area and phase. Positive rate is shown beside AUPRC, since the base rate is low (about 6%).

All metrics are stored with the input file hashes, so every number on screen is reproducible.

## 9. Scorers (plug-ins)
Interface: `score(record: dict) -> float` in `tool/aegir_ran/autoran/scorers/<name>.py`, registered by name.
Scorers see **only input fields** (never status, whyStopped, dates after start, actual enrollment, results);
the loader passes a filtered view to prevent leakage. [Code: unit-test that forbidden fields are absent.]

Ship with:
1. `random` (sanity: AUROC ≈ 0.5);
2. `criteria_count` (number of eligibility criteria);
3. `logistic_baseline`: stdlib logistic regression on simple features (criteria counts, age span, healthy volunteers, n_sites, n_countries, planned enrollment if clean, phase, sponsor class, masking, n_primary_outcomes), trained on train, tuned on dev, reported on test.

Later: `aegir_review`, the Phase 1 engine, run **outside** the tool (language-model calls are not
allowed inside it). It writes scores to `data/derived/scores/<scorer>/<split>.jsonl`, which AutoRAN reads
like any other scorer. That keeps the CLAUDE.md rule and makes AEGIR's lift over the baselines the headline metric.

## 10. Dashboard and inspector (`autoran serve`)
Same server pattern as the labelling app (127.0.0.1, Host-checked, stdlib, no CDN, inline SVG charts).
Style as the user asked for RÁN: **kiki over bouba**: square corners, 1 px rules, high contrast, monospaced record text, colour only where it carries meaning.

Pages:
1. **Overview:** metric tiles (trials, positives, negatives, labeller accuracy, audit precision, best scorer AUROC test-clean), last-run status, and warnings (contamination gap, labeller disagreements, errors).
2. **Coverage:** bar charts by area, phase, year, sponsor; class balance; input_state.
3. **Labels:** confusion matrix against the curated set, per-class precision and recall, rules-vs-model disagreements list.
4. **Scorers:** ROC and PR curves, CIs, top-k precision, calibration, breakdowns; all versus clean toggle.
5. **Findings browser:** a table of trials with filters (every category plus class, label_source, confidence, disagreement, audit state) and free-text search over title and whyStopped; sortable by any scorer.
6. **Trial inspector:** header (NCT, title, phase, sponsor, dates), the label with its evidence span highlighted in whyStopped, `label_source`, rule id or model version, confidence, categories, input_state and caveats, the scorer outputs with the top contributing features (logistic baseline), the eligibility text (collapsible), provenance (page file, sha256, API timestamp, grade), and links to the ClinicalTrials.gov record and history (open in the browser; never fetched). Audit buttons (A agree, D disagree, U unsure, N note) when the trial is in an audit sample.
7. **About:** sources, licences, grades, attribution text, version, and the caveats in plain words.

## 11. Scheduling
`autoran run` is idempotent and resumable. The user can schedule it nightly (Windows Task Scheduler
calling `RAN.exe autoran run`, or a scheduled task from Cowork that requires the computer). Large NCBI
jobs keep the existing night-time rule; ClinicalTrials.gov deltas are small.

## 12. Storage and size estimates [Code: measure and report]
Raw pages, gzip: about 150–250 MB for 72k studies at 2–3 KB compressed each (estimate). Normalised JSONL: about 100–150 MB.
Labels and metrics: small. All append-only; a new run writes a new stamp; the newest wins.

## 13. Tests and acceptance
- Unit: page parsing; field stripping (no personal data); input-state rules; each labeller tier; leakage guard; metrics (AUROC on known vectors; Wilson CI; bootstrap seeded); grade floor at export.
- Fixture run on 500 trials offline; full run on the default scope live (expect about 72 requests).
- Labeller: report held-out curated accuracy; **target ≥ 90% for Insufficient_Enrollment precision** before the silver set is used for scorer claims. If rules fall short, try the model tier.
- UI: overview renders with real data; inspector opens any NCT in < 1 s; keyboard audit works; no request leaves 127.0.0.1.
- Acceptance: one `autoran run` from a clean folder produces metrics, a dashboard, and an export with a licence manifest, and baselines show AUROC well above 0.5 on test-clean (or the report says why not).

## 14. Build order
1. fetch + normalise + input_state (default scope), with sidecars.
2. Curated Open Targets set download (needs `huggingface.co` in the allowlist, see `domains.txt`) + rules labeller + its held-out metrics.
3. categorize + split.
4. metrics + overview/coverage/labels pages.
5. findings browser + trial inspector + audit flow.
6. scorers (random, criteria_count, logistic) + scorer pages.
7. `run` + export + scheduling notes.
8. Optional model tier.

## 15. Decisions for the user
1. Grade Apache 2.0 (Open Targets) as B−? (design: yes; it is permissive, attribution plus notice).
2. Default scope Phase 2–3 only, or all phases (about 267k trials; Phase 1 recruitment failures behave differently)?
3. Contact NLM now for supported history access, since volume is now needed? (Design: yes; this is the main limit on clean inputs.)
4. Audit time: about 500 spot-checks at 10–20 s is about 2 hours, spread over sessions.

## 16. What AutoRAN cannot tell us (state in the UI About page)
- Whether a change was avoidable or substantive (RÁN plus humans).
- Under-enrolment in trials that completed (planned figure lost without history).
- Anything about efficacy or safety.
- Causation: a scorer that predicts recruitment failure is consistent with spotting real protocol problems,
  but site, sponsor and funding effects also predict it. The baselines exist to show how much of the signal
  is "easy"; AEGIR must beat them on the clean subset to claim more.
