"""A tree over the 17 curated classes: super-label > label (class) > sub-label, plus three side axes.

The curated Open Targets classes mix causes ("Negative"), mechanisms ("Interim_Analysis", "Business_Administrative") and states
("Invalid_Reason"). The tree keeps those classes as the middle level (so the curated test set still applies to them) and adds:

* super-labels above, so a weak class can be judged against its neighbours;
* sub-labels below, rule-made and checked only by reading samples and by human review (the curated set has no sub-labels);
* `stage`, from the registry status and enrolment, never from the text: before_start / during_enrolment / after_enrolment / unknown;
* `withdrawn_kind`, for WITHDRAWN trials: a protocol or approval that blocked the start, versus a viable study that nobody joined,
  versus resources pulled, a decision, an outside event, or an empty record;
* `land_mine`, for stops that were not just a failure to show results: harm to participants, misconduct or non-compliance,
  or an order from a regulator or ethics board.

Standard library only; builds on `labeller.classify_rules`.
"""
import re

from . import labeller as L

SUPER = {
    "Participants": ["Insufficient_Enrollment"],
    "Resources": ["Business_Administrative", "Logistics_Resources", "Study_Staff_Moved"],
    "Science": ["Study_Design", "Another_Study", "Insufficient_Data"],
    "Results": ["Negative", "Endpoint_Met", "Success", "Interim_Analysis"],
    "Harm and compliance": ["Safety_Sideeffects", "Regulatory", "Ethical_Reason"],
    "Outside events": ["Covid19"],
    "Uninformative": ["Invalid_Reason", "No_Context"],
}
SUPER_OF = {c: s for s, cs in SUPER.items() for c in cs}

# sub-label rules: (id, parent class, regex). A sub-label is only reported when its parent class is.
SUB = [
    ("ie.none_enrolled", "Insufficient_Enrollment", r"\b(?:no|zero|not a single|never any|failed to (?:enrol|enroll|recruit) any|unable to (?:enrol|enroll|recruit) any|none (?:was |were )?(?:enrolled|recruited))\b[^.;]{0,25}(?:patients?|participants?|subjects?|enrol\w*|recruit\w*)|\bno (?:one|eligible)\b|\bnot a single\b"),
    ("ie.slow", "Insufficient_Enrollment", r"\bslow(?:er|ly)?\b|\btaking too long\b|\bprolonged\b|\bstalled\b|\bbelow (?:the )?(?:expected|required|projected)\b|\bdelay\w*"),
    ("ie.target_missed", "Insufficient_Enrollment", r"\b(?:targets?|goals?|planned|projected|expected|required|necessary|sample size)\b[^.;]{0,40}\b(?:not|never|unable|could not|unmet|short|failed)\b|\bonly \d+\b|\b\d+ (?:of|out of) \d+\b|\bunder-?(?:recruit|enrol|power)\w*"),
    ("ie.eligibility", "Insufficient_Enrollment", r"\b(?:eligib\w+|inclusion|exclusion|criteria|strict|narrow|rare|few suitable|suitable|qualif\w+|meeting)\b"),
    ("ie.competition", "Insufficient_Enrollment", r"\b(?:competing|other|alternative|new|standard of care|approved|available)\b[^.;]{0,30}\b(?:studies|trials?|treatments?|therap\w+|drugs?|options?)\b"),
    ("ie.refusal", "Insufficient_Enrollment", r"\b(?:refus\w*|declin\w*|unwilling|not interested|reluctan\w*|did not want|dropped out|drop-?outs?|retention|withdrew consent|lost to follow)"),
    ("ie.sites_referral", "Insufficient_Enrollment", r"\b(?:sites?|centers?|centres?|referrals?|referr\w+|clinic\w*|physicians?|investigators?)\b"),
    ("ie.feasibility", "Insufficient_Enrollment", r"\bfeasib\w+|\bimpractic\w+|\bdifficult\w*|\bchalleng\w*|\bhard\b"),
    ("res.funding", "Business_Administrative", r"\bfund\w*|\bfinanc\w*|\bbudget\w*|\bgrant\b|\bmoney\b|\bcost\w*|\bpayment"),
    ("res.sponsor_strategy", "Business_Administrative", r"\bbusiness\b|\bstrateg\w*|\bportfolio\b|\bprioriti\w*|\bsponsor\W{0,3}s? (?:decision|decided|choice|request)|\bcompany\b|\bcorporate|\bmerger|\bacquisition|\bcommercial\w*|\bdevelopment[^.;]{0,30}(?:stopped|terminated|discontinued|ended|no longer)"),
    ("res.investigator_decision", "Business_Administrative", r"\b(?:pi|investigator|physician)\W{0,3}s? (?:decision|request|choice|decided|no longer|unwilling)|\bpi decision"),
    ("res.contract_admin", "Business_Administrative", r"\badministrative\w*|\bcontract\w*|\bagreement\b|\bpolicy\b|\bbureaucra\w*|\bpaperwork"),
    ("log.drug_supply", "Logistics_Resources", r"\b(?:drug|product|vaccine|medication|study drug|compound|placebo|supply|supplies)\b[^.;]{0,30}\b(?:supply|shortage|unavailab\w*|not available|expired|expiry|recall\w*|manufactur\w*|production)|\bmanufactur\w*|\bdrug supply|\bsupply (?:issues?|problems?|shortage)"),
    ("log.device_equipment", "Logistics_Resources", r"\b(?:device|equipment|instrument|machine|software|app|platform|technology|hardware|system)\b"),
    ("log.staff_capacity", "Logistics_Resources", r"\b(?:staff\w*|personnel|manpower|resources?|capacity|time|workload|human)\b"),
    ("log.site_closed", "Logistics_Resources", r"\b(?:site|clinic|facility|hospital|unit|lab\w*)\b[^.;]{0,25}\b(?:clos\w+|unavailab\w+|destroyed|shut)"),
    ("log.start_up_delay", "Logistics_Resources", r"\bstart-?up\b|\bdelays?\b[^.;]{0,20}\b(?:start|initiat|open)\w*"),
    ("staff.pi_left", "Study_Staff_Moved", r"\b(?:pi|principal investigator|investigator|physician|doctor)\b"),
    ("staff.team_left", "Study_Staff_Moved", r"\b(?:staff|coordinator|team|fellow|researcher|nurse|resident|student|personnel)\b"),
    ("staff.illness_death", "Study_Staff_Moved", r"\b(?:ill\w*|sick|died|death|deceased|passed away|maternity|deployed)\b"),
    ("saf.death_serious", "Safety_Sideeffects", r"\bdeaths?\b|\bfatal\w*|\bdied\b|\bmortality\b|\bserious (?:adverse )?(?:events?|reactions?)\b|\bsaes?\b|\bsusars?\b|\blife-?threatening|\bhospitali[sz]\w*"),
    ("saf.organ_toxicity", "Safety_Sideeffects", r"\bhepat\w+|\bliver\b|\btransaminase\w*|\balt\b|\bast\b|\bcardi\w+|\bkidney|\brenal\b|\bneuro\w*tox\w*|\bseizure\w*|\bbleed\w+|\bhemorrhag\w+|\bstroke\b|\bthrombo\w+|\bperforation\b|\binfection\w*|\btoxicit\w*"),
    ("saf.tolerability", "Safety_Sideeffects", r"\btolerab\w+|\btolerated\b|\bintoleran\w*|\bside[- ]?effects?\b|\bdiscontinuation due to"),
    ("saf.other_study_signal", "Safety_Sideeffects", r"\b(?:sister|similar|related|parallel|other|another|class|recent|publication|separate|different|same drug|elsewhere)\b[^.;]{0,30}\b(?:study|trial|studies|trials|data|reports?|publications?|concerns?|signals?)\b"),
    ("neg.futility", "Negative", r"\bfutil\w*|\bunlikely to (?:show|meet|demonstrate|benefit|achieve)|\bconditional power"),
    ("neg.no_efficacy", "Negative", r"\black of (?:clinical )?(?:efficacy|effect|benefit|activity|response)|\bno (?:clinical |significant |meaningful |added )?(?:benefit|efficacy|effect|improvement|difference)|\bnot (?:effective|efficacious|beneficial)|\bineffective|\binsufficient (?:efficacy|effect)"),
    ("neg.endpoint_not_met", "Negative", r"\bdid not (?:meet|show|demonstrate|achieve|reach)\b|\bendpoint[^.;]{0,15}not\b|\bnegative (?:results?|outcomes?|findings?)"),
    ("neg.at_interim_analysis", "Negative", r"\binterim\b|\bdsmb\b|\bdmc\b|\bidmc\b|\bmonitoring committee|\bplanned analysis|\bfutility analysis"),
    ("neg.benefit_risk", "Negative", r"\brisk[- /]*benefit|\bbenefit[- /]*risk|\brisks? (?:outweigh\w*|exceed\w*)"),
    ("end.at_interim_analysis", "Endpoint_Met", r"\binterim\b|\bdsmb\b|\bdmc\b|\bidmc\b|\bmonitoring committee"),
    ("reg.authority_action", "Regulatory", r"\bclinical hold\b|\bfda\b|\bema\b|\bmhra\b|\bhealth canada\b|\bhealth authorit\w*|\bcompetent authority|\bregulator\w*|\bnci\b|\bordered\b|\bmandate\w*"),
    ("reg.irb_lapse", "Regulatory", r"\birb\b|\breb\b|\bethics committee|\bcontinuing review\b|\bexpired\b|\blapse\w*|\brenew\w*"),
    ("reg.approval_not_obtained", "Regulatory", r"\b(?:not|never|no|without|denied|failed to|unable to)\b[^.;]{0,20}\b(?:approv\w+|permission|authori[sz]\w+|licen[sc]\w+|clearance|ide\b|ind\b)|\bapproval\b[^.;]{0,20}\b(?:not|denied|delayed|pending|required|needed)"),
    ("reg.product_withdrawn", "Regulatory", r"\bmarketing authori[sz]ation|\brecall\w*|\bwithdrawn from (?:the )?market|\bwithdrawal of (?:the )?(?:drug|product)"),
    ("des.protocol_change", "Study_Design", r"\bamend\w*|\brevis\w*|\bmodif\w*|\bprotocol (?:change|chang\w+)|\bre-?writ\w*|\bre-?design\w*|\bnew protocol|\boptimi[sz]\w*|\bto be revised"),
    ("des.population_indication", "Study_Design", r"\b(?:indication|population|disease|cohort|subgroup|inclusion|eligibility|criteria)\b"),
    ("des.endpoint_dose", "Study_Design", r"\b(?:endpoint|outcome|dose|dosing|dosage|regimen|formulation|schedule|comparator|control arm)\b"),
    ("des.methodology", "Study_Design", r"\bmethodolog\w*|\bflaw\w*|\binappropriate|\binvalid|\bunderpower\w*|\bsample size|\bstatistic\w*|\brandomi[sz]ation"),
    ("oth.competing_study", "Another_Study", r"\b(?:competing|identical|similar|parallel|sister|same|overlap\w*)\b[^.;]{0,25}\b(?:study|trial|studies|trials)\b|\bother (?:study|trial|studies|trials)"),
    ("oth.published_evidence", "Another_Study", r"\bpublish\w*|\bpublication\w*|\brecent (?:data|results?|studies|findings|evidence)|\bnew (?:data|evidence|information|guidelines?)|\bresults? (?:from|of) (?:another|other|a|the)\b|\bliterature"),
    ("oth.superseded_merged", "Another_Study", r"\bsupersed\w*|\bmerged\b|\bcombined (?:with|into)\b|\breplaced by\b|\btransfer\w*|\bnct\d{8}\b|\bnow part of\b|\bcontinued (?:in|as)\b"),
    ("oth.standard_changed", "Another_Study", r"\bstandard of care|\bguideline\w*|\balternative (?:treatment|therapy|approach|methodology)|\bapproved\b|\bnow available"),
    ("int.pending_analysis", "Interim_Analysis", r"\bpending\b|\bawaiting?\b|\bhold\b|\bon hold\b|\bsuspend\w*|\bpaused?\b|\bunder review\b|\bto determine\b"),
    ("int.monitoring_committee", "Interim_Analysis", r"\bdsmb\b|\bdmc\b|\bidmc\b|\bdata monitoring\b|\bmonitoring committee|\bsafety board"),
    ("cov.pandemic_halt", "Covid19", r"\bhalt\w*|\bsuspen\w*|\bclos\w+|\blockdown|\brestrict\w*|\bshut\w*|\bpause\w*|\bhold\b|\bpublic health\b"),
    ("cov.pandemic_recruitment", "Covid19", r"\brecruit\w*|\benrol\w*|\baccru\w*|\bparticipants?\b|\bpatients?\b|\bvisits?\b"),
    ("eth.misconduct", "Ethical_Reason", r"\bmisconduct|\bfraud\w*|\bfalsif\w*|\bviolat\w*"),
    ("eth.consent_rights", "Ethical_Reason", r"\bunethical|\bconsent\b|\brights?\b|\bwelfare\b|\bequipoise\b|\bethics committee|\bhelsinki"),
    ("inv.never_started", "Invalid_Reason", r"\bnever\b|\bnot (?:been )?(?:started|initiated|opened|activated)|\b(?:prior to|before) (?:\w+ ){0,2}(?:enrol|recruit|accru|start|open|activation|initiat)\w*|\babandoned"),
    ("inv.generic_stop", "Invalid_Reason", r"^\W*(?:the )?(?:study|trial|program|programme|project|protocol)(?: concept)?(?: was| has been| is)? (?:now )?(?:terminated|stopped|cancell?ed|discontinued|closed|halted)\W*$|^\W*(?:terminated|closed|stopped)\W*$"),
    ("inv.administrative", "Invalid_Reason", r"\badministrative\w*|\bnot an applicable|\bnot reflective|\bgrant summary|\bduplicate|\bentered in error|\bregistered in error"),
    ("inv.completed", "Invalid_Reason", r"\bcompleted\b|\bgoal (?:was )?(?:met|reached|achieved)|\bsufficient (?:data|evidence)"),
]
_SUB = [(i, p, re.compile(rx, re.I)) for i, p, rx in SUB]
_PARENT = {i: p for i, p, rx in SUB}

# Risk domains for recruitment failure (Briel et al. 2016, Table 3). Value: (domain, judged preventable by a pilot with real consent).
# Our mapping of our sub-labels onto their domains: a prior for a risk model, never a finding about a single trial.
BRIEL = {
    "ie.eligibility": ("design", True),             # overestimated prevalence / overly narrow criteria
    "ie.competition": ("participant", False),       # concurrent competing trials: not preventable, but searchable in advance
    "ie.refusal": ("participant", True),            # motivation, burden, prejudice against the intervention
    "ie.sites_referral": ("recruiter", True),
    "ie.feasibility": ("design", True),
    "ie.slow": ("unspecified", None),
    "ie.target_missed": ("unspecified", None),
    "ie.none_enrolled": ("unspecified", None),
    "res.funding": ("funding", True),
    "log.staff_capacity": ("recruiter", True),
    "log.start_up_delay": ("recruiter", False),     # delay in opening sites (approvals, new regulation)
    "oth.competing_study": ("participant", False),
    "oth.published_evidence": ("recruiter", False), # new outside evidence shifts recruiter views
}


def risk_domains(subs):
    """{domain: [sub-label, ...]} for the recruitment-related sub-labels in `subs`."""
    out = {}
    for sid in subs or ():
        if sid in BRIEL:
            out.setdefault(BRIEL[sid][0], []).append(sid)
    return out


# land mines: what makes a stop worse than a failure to show results
MISCONDUCT = re.compile(r"\bmisconduct|\bfraud\w*|\bfalsif\w*|\bdata integrity|\bgcp\b|\bgood clinical practice|\bprotocol (?:non-?compliance|violations?|deviations?)|\bnon-?compliance (?:with|of) (?:the )?(?:protocol|gcp|regulations?|requirements?)|\b(?:site|investigator|sponsor) non-?complian\w+|\bfailure to comply|\bconsent (?:violation|problem|issue)s?|\bunblind\w+|\bfabricat\w+", re.I)
ORDERED = re.compile(r"\bclinical hold\b|\b(?:fda|ema|mhra|health canada|nci|irb|reb|regulatory authorit\w+|health authorit\w+|regulator\w*|ethics committee)\b[^.;]{0,30}\b(?:ordered|required|imposed|issued|placed|terminated|suspended|revoked|rescinded|stopped|halted)|\b(?:terminated|suspended|stopped|halted) (?:by|at the request of) (?:the )?(?:\w+ ){0,2}(?:fda|ema|mhra|nci|irb|reb|regulator\w*|ethics committee|regulatory authorit\w+|health authorit\w+)", re.I)
NEGATED = re.compile(r"\b(?:no|not|without|nor|unrelated to|non|not related to|not due to|not because of)\b[^.;]{0,20}\b(?:safety|adverse|harm|toxic\w*|deaths?|misconduct|violations?)\b", re.I)

BEFORE_START_TEXT = re.compile(r"\b(?:before|prior to) (?:\w+ ){0,3}(?:enrol|recruit|accru|first (?:patient|participant|subject)|start|opening|activation|initiat)\w*|\bnever (?:started|opened|initiated|activated|enrolled)\b|\bnot (?:been )?(?:started|initiated|opened|activated)\b|\bno (?:patients?|participants?|subjects?) (?:were |was )?(?:ever )?(?:enrolled|recruited)\b", re.I)

# the "why" of a withdrawn trial: did something block a start, or did a viable study find nobody
RESOURCE = {"Business_Administrative", "Logistics_Resources", "Study_Staff_Moved"}


def stage_of(status, enrollment):
    """From registry fields only (never from the text)."""
    st = (status or "").upper()
    try:
        n = int(float(enrollment)) if enrollment not in (None, "") else None
    except (TypeError, ValueError):
        n = None
    if st == "WITHDRAWN":
        return "before_start"
    if st in ("TERMINATED", "SUSPENDED"):
        if n is None:
            return "unknown"
        return "before_start" if n == 0 else "during_enrolment"
    if st == "COMPLETED":
        return "after_enrolment"
    return "unknown"


def withdrawn_kind(classes, subs, rids, text):
    """Why a trial that never enrolled anyone was withdrawn. A stated block outranks a resource, a resource outranks 'no takers';
    when a block and a recruitment failure are both stated the kind is 'mixed' (a human should look)."""
    cs = set(classes)
    if not cs:
        return "unclassified_reason" if len(text.split()) >= 4 else "empty_record"
    if cs <= {"No_Context", "Invalid_Reason"}:
        return "empty_record"
    blocked = bool(cs & {"Regulatory", "Ethical_Reason"})
    flawed = bool(cs & {"Study_Design", "Insufficient_Data"})
    if (blocked or flawed) and "Insufficient_Enrollment" in cs and not (flawed and not blocked and not {"des.protocol_change", "des.methodology"} & set(subs)):
        return "mixed_block_and_no_takers"
    if blocked:
        return "approval_blocked"
    if flawed and "Insufficient_Enrollment" not in cs:
        return "protocol_flawed"
    if "Another_Study" in cs:
        return "overtaken_by_evidence"
    if cs & {"Safety_Sideeffects", "Negative"}:
        return "evidence_against"
    if "Covid19" in cs:
        return "outside_event"
    if cs & RESOURCE:
        return "resources_pulled"
    if "Insufficient_Enrollment" in cs:
        # every withdrawn trial enrolled nobody, so "no participants were enrolled" alone only restates the status
        if set(rids) & {"ie_low_enr", "ie_slow", "ie_unable", "ie_enr_low", "ie_not_enough", "ie_poor_recruit", "ie_difficult_incl", "ie_recruit_issue", "ie_did_not_reach",
                        "ie_enr_target", "ie_target_not_met", "ie_few_elig", "ie_low_participation", "ie_lower_expected", "ie_delay", "ie_inclusion", "ie_timeline", "ie_slow_a", "ie_not_feasible", "ie_refused"}:
            return "no_takers"
        return "none_enrolled_unexplained"
    return "other"


def classify_tree(text, status=None, enrollment=None):
    classes, rids, span = L.classify_rules(text)
    norm = L.fix_typos(L.normalise_reason(text))
    subs = [i for i, p, rx in _SUB if p in classes and rx.search(norm)]
    for c in classes:
        if not any(_PARENT.get(i) == c for i in subs):
            subs.append(c + ".unspecified")
    supers = sorted({SUPER_OF[c] for c in classes if c in SUPER_OF})
    stage = stage_of(status, enrollment)
    mine = None
    if not NEGATED.search(norm):
        if MISCONDUCT.search(norm):
            mine = "misconduct_or_noncompliance"
        elif {"safety_term", "safety_harm"} & set(rids):
            # harm seen in this trial's participants; harm reported from elsewhere, or before anyone was enrolled, is a signal only
            mine = "harm_signal_elsewhere" if ("saf.other_study_signal" in subs or stage == "before_start") else "harm_to_participants"
    if mine is None and ORDERED.search(norm):
        mine = "ordered_by_authority"
    if mine is None and "Ethical_Reason" in classes:
        mine = "ethical_concern"
    out = {"classes": classes, "supers": supers, "sublabels": subs, "stage": stage, "land_mine": mine, "rule_ids": rids}
    if (status or "").upper() == "WITHDRAWN":
        out["withdrawn_kind"] = withdrawn_kind(classes, subs, rids, norm)
    return out
