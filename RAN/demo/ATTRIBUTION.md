# Demo data: attribution and terms

`ran-demo-batch.json` holds 16 labelling cases built from real ClinicalTrials.gov records, so the labelling app can be tried
without fetching anything.

**Source.** ClinicalTrials.gov, U.S. National Library of Medicine (https://clinicaltrials.gov). Current records and version histories of
16 COPD trials (phase 2 or 3, start 2010 to 2020, completed or terminated), taken from a 433-trial pool.

**Date.** Registry data timestamp 2026-10-28T09:00:04 (the date the registry processed the data). Version histories were saved from a
browser session on 28 Oct 2026 (18:20 to 20:44 UTC). This is a historical snapshot, **not current data**: the registry is updated daily, so
check the linked live record for the current version.

**Modifications (all made by RAN, none by hand).**
- 16 trials selected out of 433, one case per trial, chosen to show a spread of change types and a few unchanged or wording-only cases.
- Names and contact details of investigators, officials and site contacts were removed. A check found no email addresses or phone numbers.
- Eligibility text and outcome text were converted from HTML or markdown to plain text with list structure (HTML entities decoded,
  markup removed); the wording itself was not edited.
- Two versions of each record were compared, and the differences were highlighted. The provisional label and its findings were written by
  RAN's rule-based analysis (`amend.py`), not by the registry.

**Terms.** ClinicalTrials.gov asks that data be attributed to ClinicalTrials.gov, that the processing date be shown, and that
modifications be described (done above). It states that some data may be subject to third-party copyright and that the data carry
international copyright outside the United States, so check the original record and its sponsor before reusing text from it.
This does not imply endorsement by the registry or NLM. Full terms: https://clinicaltrials.gov/about-site/terms-conditions

**Where your labels go.** Labels, notes and drafts from demo sessions are written to `data/demo/<name>/`, separate from real labels in `data/labels/`.

**Cases.**

| Case | Trial | Compared |
| --- | --- | --- |
| c01 | [NCT01610037](https://clinicaltrials.gov/study/NCT01610037) | versions 2 to 3 (2012-08-15 to 2012-11-30) |
| c02 | [NCT02109406](https://clinicaltrials.gov/study/NCT02109406) | versions 0 to 3 (2014-04-04 to 2014-07-16) |
| c03 | [NCT01697696](https://clinicaltrials.gov/study/NCT01697696) | versions 0 to 1 (2012-09-28 to 2012-12-06) |
| c04 | [NCT02594722](https://clinicaltrials.gov/study/NCT02594722) | versions 1 to 3 (2015-11-02 to 2016-09-23) |
| c05 | [NCT04069312](https://clinicaltrials.gov/study/NCT04069312) | versions 2 to 15 (2020-02-07 to 2025-12-10) |
| c06 | [NCT03085485](https://clinicaltrials.gov/study/NCT03085485) | versions 0 to 4 (2017-03-14 to 2018-08-20) |
| c07 | [NCT03457103](https://clinicaltrials.gov/study/NCT03457103) | versions 0 to 1 (2018-03-01 to 2019-04-03) |
| c08 | [NCT02205242](https://clinicaltrials.gov/study/NCT02205242) | versions 0 to 3 (2014-07-30 to 2017-03-28) |
| c09 | [NCT01376245](https://clinicaltrials.gov/study/NCT01376245) | versions 0 to 1 (2011-06-16 to 2011-06-23) |
| c10 | [NCT01842360](https://clinicaltrials.gov/study/NCT01842360) | versions 0 to 6 (2013-04-24 to 2018-03-21) |
| c11 | [NCT01040793](https://clinicaltrials.gov/study/NCT01040793) | versions 0 to 11 (2009-12-29 to 2010-12-15) |
| c12 | [NCT01613326](https://clinicaltrials.gov/study/NCT01613326) | versions 0 to 2 (2012-06-06 to 2012-11-29) |
| c13 | [NCT02097992](https://clinicaltrials.gov/study/NCT02097992) | versions 0 to 2 (2014-03-26 to 2014-12-02) |
| c14 | [NCT01085045](https://clinicaltrials.gov/study/NCT01085045) | versions 0 to 6 (2010-03-09 to 2010-09-01) |
| c15 | [NCT04087590](https://clinicaltrials.gov/study/NCT04087590) | versions 1 to 3 (2019-12-02 to 2021-04-21) |
| c16 | [NCT01490125](https://clinicaltrials.gov/study/NCT01490125) | versions 0 to 1 (2011-12-08 to 2011-12-12) |
