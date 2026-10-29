"""Label definitions shown beside the options on screen. Single source for the page, the server and the docs.

Standards behind the wording
- Substantial vs non-substantial: EU Clinical Trials Regulation 536/2014, Art. 2(2)(13): a change likely to have a
  substantial impact on participants' safety or rights, or on the reliability and robustness of the data.
- Eligibility, outcomes, sample size, amendments: SPIRIT 2025 items 14, 16, 19 and 31; CONSORT 2025 (changes to trial
  outcomes after commencement are reported with reasons). Outcomes are judged element by element: variable measured,
  analysis metric, method of aggregation (cut-off), time point.
- Outcome switching categories: the COMPare project (outcomes added, outcomes removed or not reported).
- Avoidability: the Tufts CSDD four-level scale (completely avoidable ... completely unavoidable) with their cause
  examples (design flaws, inconsistencies and errors versus safety data, regulatory requests and external events).
"""

REAL_CHANGE = [
    ("yes", "yes", "Substantive: likely to change who is enrolled, what is measured and when, how many, or which arms, "
                   "so participants' safety or rights, or the reliability of the data, could be affected."),
    ("no", "no", "Non-substantive: spelling, grammar, acronyms, formatting, numbering, order, units or reworded "
                 "text with the same meaning. Same people, same measures, same design."),
    ("unsure", "unsure", "The text shown is not enough to decide. Say why in the case note."),
]

# group id, heading, options (id, label, schema enum, definition)
CHANGE_GROUPS = [
    ("elig", "2a. Eligibility (who can enter)", [
        ("elig_broadened", "Broadened", "eligibility", "More patients can now enter: a criterion removed, a threshold loosened, a wider range."),
        ("elig_narrowed", "Narrowed", "eligibility", "Fewer patients can now enter: a criterion added, a threshold tightened, a narrower range."),
        ("elig_clarified", "Clarified (meaning shifts)", "eligibility", "Made more precise or detailed (a definition, a test, an example) and the eligible group may shift a little."),
        ("age_sex", "Age / sex / volunteers", "eligibility", "The age limits, sex, or healthy-volunteer setting changed."),
    ]),
    ("outcome", "2b. Primary outcome (SPIRIT item 16 elements)", [
        ("outcome_added_removed", "Added / removed / re-ranked", "primary_outcome", "A primary outcome was added, dropped, or moved between primary and secondary."),
        ("outcome_variable", "Variable measured", "primary_outcome", "A different thing is measured: the domain, instrument or specific measurement changed."),
        ("outcome_metric", "Metric / aggregation / cut-off", "primary_outcome", "How each value is analysed or summarised changed (change from baseline vs responder rate, a new threshold)."),
        ("outcome_timepoint", "Time point", "primary_outcome", "When the outcome is assessed changed."),
    ]),
    ("design", "2c. Design and other", [
        ("sample_size", "Sample size target", "enrolment", "The planned enrolment target changed. (A planned figure replaced by the actual count is not an amendment.)"),
        ("design_arms", "Arms / interventions / dosing", "design", "Arms, interventions, dose, comparator, randomisation or blinding changed."),
        ("accrual", "Accrual-driven change", "stopped_low_accrual", "Changed or stopped because recruitment was slow or the target could not be reached."),
        ("other", "Other (describe in the case note)", "other", "Anything else relevant."),
    ]),
    ("wording", "2d. Wording only (not substantive)", [
        ("wording_spelling", "Spelling / grammar", "wording_only", "Spelling, grammar, punctuation or capitalisation corrected."),
        ("wording_acronym", "Acronym", "wording_only", "An acronym or abbreviation introduced, expanded, or swapped for its full name."),
        ("wording_format", "Format / units / symbols", "wording_only", "Numbering, order, layout, symbols (>= to ≥) or unit spelling standardised; same content."),
        ("wording_rephrase", "Reworded, same meaning", "wording_only", "Rewritten for style or clarity without changing who is eligible or what is measured."),
    ]),
]
CHANGE_TYPES = [(o[0], o[1], o[2], o[3]) for g in CHANGE_GROUPS for o in g[2]]
CHANGE_ENUM = {t[0]: t[2] for t in CHANGE_TYPES}

AVOIDABLE = [  # id, label, definition, schema value
    ("completely_avoidable", "completely avoidable", "A design flaw, inconsistency or error that careful planning or review would have caught.", "yes"),
    ("somewhat_avoidable", "somewhat avoidable", "Partly foreseeable at design time, for example an ambiguous criterion or a hopeful target.", "yes"),
    ("somewhat_unavoidable", "somewhat unavoidable", "Mostly driven by events, though earlier design choices made it more likely.", "no"),
    ("completely_unavoidable", "completely unavoidable", "Not foreseeable: new safety information, a regulator or ethics request, new outside evidence.", "no"),
    ("unsure", "unsure", "Cannot tell from the registry text.", "unknown"),
]
CAUSES = [
    ("design_flaw_error", "Design flaw, inconsistency or error", "The earlier text was wrong, unclear or internally inconsistent."),
    ("recruitment", "Recruitment difficulty", "Eligibility, target or timeline changed to make enrolment feasible."),
    ("safety", "New safety information", "Changed to protect participants after new safety data."),
    ("regulatory", "Regulator or ethics request", "Changed at the request of a regulator, ethics committee or data monitoring board."),
    ("evidence", "New outside evidence or standard of care", "Other trials, guidelines or practice changed."),
    ("strategy", "Sponsor strategy or operations", "Business, supply, site or operational reasons."),
    ("not_stated", "Cannot tell", "The record gives no reason."),
]
SEVERITY = [
    ("major", "major (substantial)", "Likely to affect safety or rights, or the reliability or interpretation of the results: population, primary endpoint, sample size, arms."),
    ("minor", "minor (non-substantial)", "A real but small change: a secondary detail, a narrowly scoped clarification."),
    ("none", "none", "Wording only; nothing of substance changed."),
]
AGREE = [
    ("yes", "yes", "I agree with the provisional label shown."),
    ("no", "no", "I disagree with it. Say why in the case note."),
]
LABEL = {"yes": "positive", "no": "negative", "unsure": "unclear"}
AVOID_VALUE = {a[0]: a[3] for a in AVOIDABLE}

# row definitions the page draws: id, heading, options [(id, name, definition)]
def page_defs():
    return {
        "real_change": [[o[0], o[1], o[2]] for o in REAL_CHANGE],
        "change_groups": [{"id": g[0], "label": g[1], "options": [[o[0], o[1], o[3]] for o in g[2]]} for g in CHANGE_GROUPS],
        "avoidable": [[a[0], a[1], a[2]] for a in AVOIDABLE],
        "cause": [[c[0], c[1], c[2]] for c in CAUSES],
        "severity": [[s[0], s[1], s[2]] for s in SEVERITY],
        "agree": [[a[0], a[1], a[2]] for a in AGREE],
    }
