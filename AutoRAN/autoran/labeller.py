"""Stop-reason labeller for the 17 Open Targets classes. Three tiers, each recorded in `label_source`:

1. exact : the normalised whyStopped text equals a curated Open Targets example;
2. rules : ordered keyword and regex rules per class, with guards ("accrual goal met" is not under-enrolment);
3. nb    : a small multi-label naive Bayes text model (standard library only) trained on the same curated set.

Rules and the model are developed on train and dev only. The frozen test part is read once, by `evaluate`, to report accuracy.
"""
import json
import math
import re
from collections import Counter, defaultdict

from .opentargets import normalise_reason

CLASSES = ["Another_Study", "Business_Administrative", "Covid19", "Endpoint_Met", "Ethical_Reason", "Insufficient_Data",
           "Insufficient_Enrollment", "Interim_Analysis", "Invalid_Reason", "Logistics_Resources", "Negative", "No_Context",
           "Regulatory", "Safety_Sideeffects", "Study_Design", "Study_Staff_Moved", "Success"]

ENR = r"(?:enrol\w*|enroll\w*|recruit\w*|accru\w*|participa\w*|patient (?:accrual|recruitment)|sample size)"
WHO = r"(?:patients?|participants?|subjects?|volunteers?|candidates?|cases?|children|women|men)"
LOWW = r"(?:low|slow|poor|insufficient|inadequate|limited|lagging|lack(?:ing)? of|too (?:few|slow|low)|difficult\w*|problem\w*|challeng\w*|unable|inability|disappointing|sluggish|delay\w*|suboptimal)"
ENRW = r"(?:enrol\w*|enroll\w*|recruit\w*|accru\w*|participa\w*)"

# (rule id, class, regex, weight) -- weight "strong" decides alone; "weak" needs no guard hit and no stronger class elsewhere
RULES = [
    # Insufficient_Enrollment
    ("ie_low_enr", "Insufficient_Enrollment", rf"\b{LOWW}\b[^.;]{{0,40}}\b{ENRW}\b", "strong"),
    ("ie_enr_low", "Insufficient_Enrollment", rf"\b{ENR}\b[^.;]{{0,35}}\b(?:was |were |is |are |has been |had been |being )?(?:too )?(?:low|slow|poor|insufficient|inadequate|difficult\w*|problem\w*|challeng\w*|lagging|below|disappointing|limited|sluggish|not (?:sufficient|enough|feasible|going well)|issues?|failure|failed|behind)\b", "strong"),
    ("ie_unable", "Insufficient_Enrollment", rf"\b(?:unable|inability|not able|could not|couldn'?t|failed|failure|difficult\w*|did not|didn'?t|cannot|can'?t|hard|impossible) (?:to )?(?:\w+ ){{0,2}}(?:recruit|enrol|enroll|accru|attract|include|identify (?:enough|sufficient|eligible)|find (?:enough|sufficient|eligible|any|suitable))\w*", "strong"),
    ("ie_not_enough", "Insufficient_Enrollment", rf"\b(?:not enough|too few|few(?:er)?|insufficient number of|small number of|lack of|shortage of|no) (?:eligible )?{WHO}\b", "strong"),
    ("ie_target_not_met", "Insufficient_Enrollment", rf"\b(?:target|goal|planned|required|projected|expected|necessary) (?:\w+ ){{0,3}}(?:{ENR}|sample size|number of {WHO})[^.;]{{0,30}}(?:not|never|unlikely|could not|couldn'?t|unable|failed)\b", "strong"),
    ("ie_did_not_reach", "Insufficient_Enrollment", rf"\b(?:did not|didn'?t|failed to|unable to|not|never|could not) (?:reach|meet|achieve|attain|obtain|accrue|enrol|enroll|recruit)[^.;]{{0,35}}\b(?:target|goal|number|sample|planned|expected|required|{ENR})\b", "strong"),
    ("ie_none_enrolled", "Insufficient_Enrollment", rf"\b(?:no|zero|0|none|never any|only (?:one|two|three|four|five|\d+)) (?:{WHO} )?(?:was |were |had been |have been )?(?:enrol\w*|enroll\w*|recruit\w*|accru\w*|included|randomi[sz]ed|screened)", "strong"),
    ("ie_refused", "Insufficient_Enrollment", rf"\b{WHO}\b[^.;]{{0,25}}\b(?:refus\w*|declin\w*|reluctan\w*|unwilling|not interested|did not (?:want|agree|consent)|dropped out|withdrew)", "weak"),
    ("ie_only_n", "Insufficient_Enrollment", rf"\bonly \d+ {WHO}\b", "strong"),
    ("ie_under", "Insufficient_Enrollment", r"\bunder-?(?:recruit|enrol|accru|power)\w*|\bunderpower\w*", "strong"),
    ("ie_slow", "Insufficient_Enrollment", r"\b(?:slow|poor|low|inadequate|insufficient|lack of|lagging|disappointing) (?:\w+ ){0,2}(?:accrual|recruitment|recruiting|enrol\w*|enroll\w*|accrued|participation)\b", "strong"),
    ("ie_few_elig", "Insufficient_Enrollment", r"\b(?:few|limited number of|small number of|difficult\w* (?:to )?(?:find|identify)\w*) (?:eligible|qualif\w*|suitable|appropriate)\b", "strong"),
    ("ie_recruit_issue", "Insufficient_Enrollment", rf"\b(?:recruit\w*|enrol\w*|enroll\w*|accru\w*) (?:\w+ ){{0,2}}(?:issues?|problems?|difficult\w*|challeng\w*|failure|barriers?|shortfall)\b", "strong"),
    ("ie_not_feasible", "Insufficient_Enrollment", rf"\b(?:not|un)feasible\b[^.;]{{0,30}}{ENR}|{ENR}[^.;]{{0,30}}\b(?:not|un)feasible\b|\bfeasibility\b[^.;]{{0,30}}(?:recruit|enrol|accru)", "strong"),
    ("ie_low_participation", "Insufficient_Enrollment", r"\blow (?:participation|participant|patient|subject)\b|\b(?:participation|interest|uptake) (?:was |is )?(?:low|poor)\b|\black of (?:interest|participation|volunteers|eligible)", "strong"),
    ("ie_poor_recruit", "Insufficient_Enrollment", r"\bpoor(?:ly)? (?:recruit|enrol|enroll|accru|accrual)\w*|\b(?:recruit|enrol|enroll|accru)\w*(?: rate)? (?:has |have |had )?(?:been )?poor", "strong"),
    ("ie_slow_a", "Insufficient_Enrollment", r"\b(?:enrol|enroll|recruit|accru)\w*(?: rate)? (?:was |is |has been |were )?(?:slow|low)\b", "strong"),
    ("ie_competing", "Insufficient_Enrollment", rf"\b(?:competing|other) (?:studies|trials)\b[^.;]{{0,40}}\b{ENR}\b", "weak"),
    ("ie_delay", "Insufficient_Enrollment", r"\bdelay\w* (?:in |of |to )?(?:the )?(?:recruit|enrol|enroll|accru|start)\w*|\b(?:recruit|enrol|enroll|accru)\w* (?:\w+ ){0,3}(?:delay\w*|suboptimal|not (?:optimi[sz]ed|achievable|being met|met|sufficient|reached|going))", "strong"),
    ("ie_closed_accrual", "Insufficient_Enrollment", r"\bclosed (?:to|for|due to|because of|secondary to) (?:\w+ ){0,2}accrual\b|\baccrual (?:was )?(?:closed|halted|stopped|suspended)\b", "weak"),
    ("ie_difficult_incl", "Insufficient_Enrollment", r"\bdifficult\w* (?:to |in |with |getting |finding |including |obtaining |to get |to find |to include |to obtain )?(?:\w+ ){0,2}(?:patients?|subjects?|participants?|volunteers?|cases?|candidates?)\b", "strong"),
    ("ie_lower_expected", "Insufficient_Enrollment", r"\b(?:lower|smaller|less|fewer|reduced|slower|decreas\w*|declin\w*|fewer) (?:\w+ ){0,3}than (?:expected|anticipated|planned|projected|predicted|hoped|estimated)\b[^.;]{0,40}(?:rate|number|prevalence|incidence|accrual|recruit\w*|enrol\w*|patients?|subjects?|participants?)|(?:rate|number|prevalence|incidence|accrual|recruit\w*|enrol\w*|volume) [^.;]{0,30}(?:lower|smaller|less|fewer|reduced|slower) than (?:expected|anticipated|planned|projected)|\breduced the number of (?:potential )?(?:patients|subjects|participants)", "strong"),
    ("ie_n_of_planned", "Insufficient_Enrollment", r"\b\d+ (?:patients?|subjects?|participants?|cases?|children|women|men)? ?(?:were |was |had been |have been )?(?:included|enrolled|recruited|accrued|randomi[sz]ed|screened)[^.;]{0,40}(?:instead of|rather than|out of|of the|vs\.?|versus|planned|target\w*|anticipated|expected|required)\b|\b\d+ (?:of|out of) (?:the )?\d+ (?:planned |target |expected |required )?(?:patients?|subjects?|participants?|cases?)|\b\d+ ?% (?:of (?:the )?(?:target|goal|planned|expected|required)|enrol\w*|accru\w*|recruit\w*)", "strong"),
    ("ie_absence", "Insufficient_Enrollment", r"\babsence of (?:patients?|subjects?|participants?|cases?)|\b(?:no|few|not many) (?:new |further |eligible |suitable )?(?:patients?|subjects?|participants?|cases?) (?:were |was |could be |can be |to be )?(?:found|identified|available|referred|eligible|enrol\w*|recruit\w*|accru\w*)|\bnot offering the study|\bnot (?:being )?referred\b|\blow referral", "strong"),
    ("ie_enr_target", "Insufficient_Enrollment", r"\b(?:enrol\w*|enroll\w*|recruit\w*|accru\w*|randomi[sz]ation)\b[^.;]{0,25}\b(?:target|goal|number|numbers)\b[^.;]{0,30}\b(?:not|never|unable|could not|couldn'?t|failed|unmet|short)\b|\bunmet (?:accrual|enrol\w*|recruit\w*|goals?)|\bnon-?(?:enrol\w*|recruit\w*|accru\w*)|\bincomplete (?:recruit|enrol|accru)\w*|\binsufficient (?:patient|subject|participant)s? (?:inclusion|enrol\w*|recruit\w*)|\blimited (?:pool|number)|\b(?:could not|couldn'?t|unable to) find (?:the )?(?:subject|patient|participant|study) population|\bdissatisf\w* (?:enrol\w*|recruit\w*|accru\w*)|\bnon-?accrual", "strong"),
    # Covid19
    ("covid", "Covid19", r"\bcovid\w*|\bsars-?\s?cov\w*|\bcorona\s?virus\w*|\bpandemic\b|\bcovid-?19\b", "strong"),
    # Safety
    ("safety", "Safety_Sideeffects", r"\bsafety\b|\badverse\b|\btoxicit\w*|\bside[- ]?effects?\b|\bserious (?:adverse )?(?:events?|reactions?)\b|\bdeaths?\b|\bmortality\b|\bharm\w*\b|\bsaes?\b|\bsusars?\b|\bintoleran\w*|\bhepatotox\w*|\bcardiotox\w*", "strong"),
    # Negative (efficacy)
    ("negative_eff", "Negative", r"\bfutil\w*|\black of (?:clinical )?(?:efficacy|effect|benefit|activity|response)|\bno (?:clinical |significant |meaningful |added )?(?:benefit|efficacy|effect|improvement|difference)\b|\bnot (?:effective|efficacious|beneficial)|\bineffective|\bdid not (?:meet|show|demonstrate|achieve|improve|reach) (?:the |its |any )?(?:primary |clinical )?(?:endpoint|efficacy|benefit|significance|objective)|\bfail\w* to (?:meet|show|demonstrate|improve)|\binsufficient (?:efficacy|effect|benefit|activity)|\b(?:poor|low|disappointing|limited|modest) (?:efficacy|response|activity)|\bunlikely to (?:show|meet|demonstrate|benefit|achieve)|\bnegative (?:results?|outcomes?|findings?|trial)|\bendpoint (?:was )?not (?:met|reached|achieved)|\befficacy (?:was )?(?:not|lacking|insufficient)", "strong"),
    # Business / administrative
    ("business", "Business_Administrative", r"\bbusiness\b|\bsponsor(?:'s|s)?\W{0,3}(?:decision|decided|choice|discretion|request|withdrew|terminated|strategy)|\bstrateg\w*|\bportfolio\b|\bprioriti\w*|\bfunding\b|\bfunds?\b|\bfinancial\w*|\bbudget\w*|\bcommercial\w*|\bcompany\b[^.;]{0,30}(?:decision|decided|discontinu|terminat|stop)|\badministrative\w*|\bcorporate|\bmerger|\bacquisition|\bresource reallocation|\bdevelopment (?:program\w*|project|plan)\b[^.;]{0,30}(?:stopped|terminated|discontinued|cancel\w*|halted|ended)|\bdiscontinu\w* (?:the )?(?:development|program)|\bprogram\w* (?:was )?(?:terminated|discontinued|cancel\w*)|\breorgani[sz]\w*|\bdecision (?:of|by) (?:the )?(?:sponsor|company|management)|\bsponsor decision|\bsponsor\W{0,3}s? (?:business|internal)|\bnot (?:initiated|started|opened)|\bnever (?:started|initiated|opened)|\bno funding|\bgrant\b", "strong"),
    # Logistics / resources
    ("logistics", "Logistics_Resources", r"\bdrug supply|\bsupply (?:issues?|problems?|shortage|of (?:the )?(?:study )?(?:drug|product|medication|vaccine|device))|\bstudy (?:drug|medication|product|vaccine|device) (?:was |is )?(?:un)?(?:available|unavailab\w*|not available|expired|discontinued)|\bmanufactur\w*|\blogistic\w*|\b(?:lack|loss) of (?:staff|personnel|resources|equipment|space|capacity|infrastructure)|\b(?:equipment|facility|site|clinic|unit|laboratory|lab) (?:was |has been )?(?:closed|closure|unavailable|destroyed|shut)|\bshortage|\bunavailab\w*|\bnot available\b|\bstaff(?:ing)? (?:shortage|issues?)|\bpackag\w*|\bshipping|\bsupplies\b|\bresources?\b|\bpharmacy|\bdrug (?:was )?(?:not )?(?:available|expired)|\bproduct (?:was )?(?:recalled|expired|withdrawn)", "strong"),
    # Study staff moved
    ("staff", "Study_Staff_Moved", r"\b(?:PI|principal investigator|investigator|physician|doctor|staff|coordinator|researcher|sponsor-investigator|study team|key personnel)\b[^.;]{0,50}\b(?:left|moved|leaving|relocated|retired|resigned|departure|departed|transferred|no longer (?:at|with|employed)|passed away|died|deceased|ill\b|illness|sick|unavailable|maternity|sabbatical|reassigned|took a (?:new )?position|accepted a position|new position|changed (?:jobs?|institutions?))|\bleft (?:the )?(?:institution|university|hospital|site|centre|center|company|organi[sz]ation)\b|\b(?:change|loss) of (?:PI|principal investigator|investigator|staff)\b|\bPI (?:left|moved|retired)\b|\bno (?:longer )?(?:PI|investigator|staff)\b|\binvestigator\W{0,3}s? (?:decision|choice|request)\b", "strong"),
    # Study design
    ("design", "Study_Design", r"\b(?:protocol|study design|design)\b[^.;]{0,25}\b(?:change\w*|amend\w*|revis\w*|issues?|problems?|flaws?|modif\w*|difficult\w*|inadequate|inappropriate)|\bredesign\w*|\bre-design\w*|\bnew (?:protocol|study design|design)\b|\b(?:replaced|superseded) by (?:a )?(?:new|revised|modified|amended) (?:study|protocol|trial|design)|\binclusion criteria\b|\beligibility criteria\b|\b(?:endpoint|outcome)s? (?:change\w*|modif\w*|revis\w*|not (?:appropriate|valid|measurable))|\bdose (?:change|adjust\w*|selection|finding)|\b(?:inappropriate|invalid|flawed|poor) (?:design|endpoint|methodology|dose)|\bmethodolog\w*|\b(?:study|trial) (?:was )?(?:redesigned|restructured|modified)|\bprotocol (?:violation|deviation)s?\b|\bstudy design\b", "strong"),
    # Another study
    ("another", "Another_Study", r"\b(?:another|other|a|the|an|similar|parent|competing|ongoing|recent|published|new|larger|related) (?:\w+ )?(?:study|trial|studies|trials)\b[^.;]{0,50}\b(?:results?|data|findings?|showed|shows|published|reported|demonstrat\w*|completed|ongoing|started|replac\w*|overlap\w*|available)|\b(?:results?|data|findings?|publication|publications) (?:from|of|in|by) (?:another|other|a |the |an |recent |published |similar )?\w*\W{0,3}(?:study|trial|studies|trials|paper|publication)|\bsuperseded\b|\bmerged (?:with|into)\b|\bcombined (?:with|into) (?:another|a|the)\b|\breplaced by\b|\bnct\d{8}\b|\bstandard of care (?:has )?changed\b|\bapproved\b|\b(?:drug|therapy|treatment|product) (?:was )?(?:approved|licensed|marketed)|\bnew (?:data|evidence|information|guidelines?)\b|\bdue to (?:the )?(?:results?|publication|findings)\b|\bbased on (?:the )?(?:results?|data|findings) (?:of|from)\b", "strong"),
    # Regulatory
    ("regulatory", "Regulatory", r"\bfda\b|\bema\b|\bregulat\w*|\bhealth authorit\w*|\bauthorit\w*|\bclinical hold\b|\bind\b[^.;]{0,25}(?:withdrawn|closed|inactiv\w*|terminated)|\bapproval\b[^.;]{0,20}(?:not|was not|denied|withdrawn|delayed|pending)|\b(?:not|never|no) (?:approved|approval|permission)\b|\bmarketing authori[sz]ation|\bcompetent authority|\bmhra\b|\bpmda\b|\bcta\b|\bpermission\b|\bdenied\b|\blicen[sc]e\w*|\bcompliance\b|\bgcp\b|\bpublic health\b|\bmandate\w*|\bgovernment\b|\bministry\b", "strong"),
    # Ethical
    ("ethical", "Ethical_Reason", r"\bethic\w*|\bethics committee|\bunethical|\bequipoise|\bhelsinki|\bmisconduct|\bfraud|\bpatient (?:rights|welfare|protection)|\bnot (?:ethical|permitted)", "strong"),
    # Endpoint met
    ("endpoint_met", "Endpoint_Met", r"\b(?:primary )?(?:endpoint|objective|goal|aim|outcome)s? (?:was |were |has been |have been )?(?:met|reached|achieved|attained|accomplished|fulfilled)(?! (?:the )?(?:accrual|enrol|recruit))|\b(?:met|reached|achieved|attained|accomplished) (?:its |the |all |our )?(?:primary |main |study |trial )?(?:endpoint|objective|goal|aim)s?|\bstopped early for (?:efficacy|benefit|success)|\boverwhelming (?:efficacy|benefit)|\bsufficient (?:evidence|data|information) (?:was )?(?:obtained|available|collected|reached)|\bdemonstrated (?:efficacy|benefit|superiority)|\bearly (?:success|efficacy)|\bproof of concept\b[^.;]{0,25}(?:achieved|met|shown|demonstrated)", "strong"),
    ("success", "Success", r"\bsuccessful(?:ly)?\b|\bcompleted successfully|\bsuccess\b|\bsuccessfully (?:completed|concluded|finished)|\bachieved (?:its )?(?:goal|aim|success)", "weak"),
    # Interim analysis
    ("interim", "Interim_Analysis", r"\binterim\b|\bfutility analysis\b|\b(?:pre-?planned|planned|scheduled) (?:analysis|review|look)\b|\bindependent (?:data )?monitoring committee", "strong"),
    # Insufficient data
    ("insuff_data", "Insufficient_Data", r"\b(?:insufficient|inadequate|not enough|lack of|poor|limited|incomplete|missing) (?:\w+ )?(?:data|information|evidence|results?|follow-?up)\b|\bdata (?:quality|integrity|collection|not available|issues?|problems?|unavailable)\b|\bunable to (?:collect|obtain|analy[sz]e|evaluate|assess) (?:\w+ )?(?:data|results?|outcomes?)", "strong"),
    # Invalid reasons (not a reason)
    ("invalid_complete", "Invalid_Reason", r"\b(?:accrual|enrol\w*|enroll\w*|recruit\w*|study|trial|follow-?up|data collection|patient accrual)\b[^.;]{0,25}\b(?:was |is |were |has been |have been )?(?:complete\w*|closed|finished|met|reached|achieved|done|ended|concluded)\b|\bgoal (?:was )?(?:met|reached|achieved)\b|\b(?:target|goal) (?:number )?(?:was )?(?:met|reached|achieved|attained)|\bcompleted\b|\badministratively (?:complete|closed|terminated)|\bplaced on (?:inactive|hold)|\binactive status\b|\bno longer (?:active|recruiting|enrolling|open)\b|\b(?:withdrawn|closed|terminated|cancel\w*)\b(?: before| prior)?\W*$|^\W*(?:n/?a|none|unknown|terminated|closed|stopped|see (?:above|below|text))\W*$", "strong"),
]
RULE_INDEX = {r[0]: r for r in RULES}
_COMPILED = [(rid, cls, re.compile(pat, re.I), w) for rid, cls, pat, w in RULES]

# guards: a recruitment-completed text is not a recruitment failure
IE_GUARD = re.compile(r"\b(?:accrual|enrol\w*|enroll\w*|recruit\w*)\b[^.;]{0,25}\b(?:was |is |were |has been |have been )?(?:complete\w*|closed|finished|met|reached|achieved|done|ended|concluded|full)\b|\bgoal (?:was )?(?:met|reached|achieved)|\b(?:target|goal) (?:number )?(?:was )?(?:met|reached|achieved|attained)|\bsufficient (?:patients|participants|subjects|enrol\w*)|\bfully (?:enrolled|recruited|accrued)|\bover-?(?:enrol|recruit|accru)\w*", re.I)
IE_NEG = re.compile(r"\b(?:not|no|n'?t|without|never) (?:due to|because of|related to|owing to) [^.;]{0,25}(?:enrol\w*|recruit\w*|accru\w*)", re.I)
NO_CONTEXT_RE = re.compile(r"^\W*(?:(?:the )?(?:study|trial|project|program|programme|development)(?: was)? (?:stopped|terminated|halted|discontinued|cancel\w*|closed)|(?:sponsor|investigator|pi|company|management)(?:'s|s)?(?: decision| choice| request)?|decision|terminated|discontinued|halted|stopped|unknown|n/?a|none|see (?:above|below|protocol)|study halted prematurely|ended early)\W*$", re.I)


_TYPOS = [(re.compile(r"\bdificult\w*"), "difficult"), (re.compile(r"\bdificulties\b"), "difficulties"), (re.compile(r"\beligble\b"), "eligible"),
          (re.compile(r"\b(?:acrr?ua?l|accur?al|accrul|accrural|accrued?al|acrual|accual)\b"), "accrual"),
          (re.compile(r"\b(?:recruitement|recrutment|recuitment|recruiment|recruting|recriutment|recruitmnt)\b"), "recruitment"),
          (re.compile(r"\b(?:enrolement|enrollement|enrollmnt|enrolmment|enrollmen)\b"), "enrollment"),
          (re.compile(r"\bpatents\b"), "patients"), (re.compile(r"\bpatinets\b"), "patients"), (re.compile(r"\bsubjetcs\b"), "subjects")]


def fix_typos(text):
    for rx, rep_ in _TYPOS:
        text = rx.sub(rep_, text)
    return text


def rule_hits(text):
    """{class: [rule ids]} for one normalised reason text."""
    hits = defaultdict(list)
    for rid, cls, rx, w in _COMPILED:
        if rx.search(text):
            hits[cls].append(rid)
    return hits


def classify_rules(raw_text):
    """-> (classes, hit rule ids, evidence span or None). Guards are applied here."""
    text = fix_typos(normalise_reason(raw_text))
    if not text:
        return [], [], None
    hits = rule_hits(text)
    ie = hits.get("Insufficient_Enrollment")
    if ie:
        strong_only = [r for r in ie if RULE_INDEX[r][3] == "strong" or r in ("ie_refused",)]
        negated_goal = re.search(r"\b(?:not|never|unable|could not|couldn'?t|failed|unmet)\b[^.;]{0,15}\b(?:met|reached|achieved|attained|complete\w*)\b", text)
        # "no patients enrolled" or "unable to ..." next to another named cause is that cause, not under-enrolment
        if set(ie) <= {"ie_none_enrolled", "ie_only_n", "ie_not_enough", "ie_unable", "ie_absence"} and (
                set(hits) & {"Business_Administrative", "Regulatory", "Logistics_Resources", "Another_Study", "Negative", "Study_Design"}):
            hits.pop("Insufficient_Enrollment", None)
        elif IE_NEG.search(text) or (IE_GUARD.search(text) and not negated_goal and not re.search(r"\b(?:slow|poor|low|difficult\w*|insufficient|inadequate|unable|failed|lack)\b", text)):
            hits.pop("Insufficient_Enrollment", None)
        elif not strong_only:
            hits.pop("Insufficient_Enrollment", None)
        # weak-only refusal rules stand only when nothing else explains the stop
        elif ie == ["ie_refused"] and len(hits) > 1:
            hits.pop("Insufficient_Enrollment", None)
    if "Covid19" in hits and "Insufficient_Enrollment" in hits:
        # COVID-driven recruitment suspension: keep both labels but flag via Covid19 (decided downstream)
        pass
    if "Invalid_Reason" in hits and re.search(r"\b(?:not|never|unable|could not|couldn'?t|fail\w*|unmet|insufficient|lack\w*)\b", text) \
            and not re.search(r"\bnot (?:started|initiated|opened|open)\b", text):
        hits.pop("Invalid_Reason", None)
    if "Safety_Sideeffects" in hits and re.search(r"\b(?:no|not|without|nor|neither)\b[^.;]{0,20}\b(?:safety|adverse|toxicit\w*|side effects?|concerns? (?:about|for|of) safety)|\bnot (?:due to|related to|because of|based on|driven by|for)[^.;]{0,30}(?:safety|adverse|toxic)", text):
        hits.pop("Safety_Sideeffects", None)
    substantive = [c for c in hits if c not in ("Invalid_Reason", "Success")]
    if substantive:
        if "Success" in hits and "Endpoint_Met" not in hits:
            hits.pop("Success", None)
        hits.pop("Invalid_Reason", None)
    elif "Invalid_Reason" in hits:
        hits.pop("Success", None)
    if not hits:
        if NO_CONTEXT_RE.match(text):
            hits["No_Context"].append("no_context_short")
    classes = sorted(hits)
    rids = sorted({r for v in hits.values() for r in v})
    span = None
    for rid, cls, rx, w in _COMPILED:
        if rid in rids:
            m = rx.search(text)
            if m:
                span = [m.start(), m.end()]
                break
    return classes, rids, span


# -- tier 3: multi-label naive Bayes (stdlib) ---------------------------------------------

TOKEN = re.compile(r"[a-z0-9]+")


def features(text):
    toks = TOKEN.findall(normalise_reason(text))
    f = set(toks)
    f.update(a + "_" + b for a, b in zip(toks, toks[1:]))
    return f


class NB:
    """One binary Bernoulli-style naive Bayes per class over unigram and bigram presence; thresholds tuned on dev."""

    def __init__(self):
        self.classes, self.logodds, self.prior, self.default, self.thresh = [], {}, {}, {}, {}

    def train(self, rows, classes, alpha=0.5, min_count=2):
        self.classes = list(classes)
        feats = [features(r["text"]) for r in rows]
        df = Counter(w for f in feats for w in f)
        vocab = {w for w, c in df.items() if c >= min_count}
        n = len(rows)
        for c in self.classes:
            pos = [i for i, r in enumerate(rows) if c in r["labels"]]
            npos, nneg = len(pos), n - len(pos)
            if npos == 0 or nneg == 0:
                self.prior[c], self.logodds[c], self.default[c], self.thresh[c] = -20.0, {}, 0.0, 0.0
                continue
            cp = Counter(w for i in pos for w in feats[i] if w in vocab)
            cn = Counter({w: df[w] - cp.get(w, 0) for w in vocab})
            lo, d0 = {}, 0.0
            for w in vocab:
                p1 = (cp.get(w, 0) + alpha) / (npos + 2 * alpha)
                p0 = (cn.get(w, 0) + alpha) / (nneg + 2 * alpha)
                lo[w] = (math.log(p1 / p0), math.log((1 - p1) / (1 - p0)))
            # keep only informative features
            self.logodds[c] = {w: v for w, v in lo.items() if abs(v[0] - v[1]) > 0.35}
            self.default[c] = 0.0
            self.prior[c] = math.log(npos / nneg)
            self.thresh[c] = 0.0
        return self

    def score(self, text):
        f = features(text)
        out = {}
        for c in self.classes:
            lo = self.logodds[c]
            s = self.prior[c]
            for w, (a, b) in lo.items():
                s += a if w in f else b
            out[c] = s
        return out

    def predict(self, text):
        sc = self.score(text)
        return [c for c in self.classes if sc[c] > self.thresh[c]], sc

    def tune(self, rows, classes):
        """Per-class threshold that maximises F1 on dev."""
        scores = [self.score(r["text"]) for r in rows]
        for c in classes:
            best, bt = -1, 0.0
            cand = sorted({round(s[c], 1) for s in scores})
            step = max(1, len(cand) // 60)
            for t in cand[::step]:
                tp = sum(1 for s, r in zip(scores, rows) if s[c] > t and c in r["labels"])
                fp = sum(1 for s, r in zip(scores, rows) if s[c] > t and c not in r["labels"])
                fn = sum(1 for s, r in zip(scores, rows) if s[c] <= t and c in r["labels"])
                f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0
                if f1 > best:
                    best, bt = f1, t
            self.thresh[c] = bt

    def dump(self):
        return {"classes": self.classes, "prior": self.prior, "thresh": self.thresh,
                "logodds": {c: {w: [round(a, 4), round(b, 4)] for w, (a, b) in v.items()} for c, v in self.logodds.items()}}

    @classmethod
    def load(cls, d):
        m = cls()
        m.classes, m.prior, m.thresh = d["classes"], d["prior"], d["thresh"]
        m.logodds = {c: {w: tuple(v) for w, v in lo.items()} for c, lo in d["logodds"].items()}
        m.default = {c: 0.0 for c in m.classes}
        return m


# -- evaluation ------------------------------------------------------------------------------

def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def evaluate(rows, predict, classes=CLASSES):
    """Multi-label per-class precision, recall, F1, plus subset accuracy. predict(text) -> list of classes."""
    st = {c: [0, 0, 0] for c in classes}
    exact = 0
    confusion = defaultdict(Counter)
    for r in rows:
        pred = set(predict(r["text"]))
        gold = set(r["labels"])
        exact += pred == gold
        for c in classes:
            if c in pred and c in gold:
                st[c][0] += 1
            elif c in pred:
                st[c][1] += 1
            elif c in gold:
                st[c][2] += 1
        g1 = r["labels"][0] if r["labels"] else "none"
        p1 = sorted(pred)[0] if pred else "none"
        confusion[g1][p1] += 1
    per = {}
    for c in classes:
        p, rc, f = prf(*st[c])
        per[c] = {"precision": round(p, 4), "recall": round(rc, 4), "f1": round(f, 4), "support": st[c][0] + st[c][2],
                  "tp": st[c][0], "fp": st[c][1], "fn": st[c][2]}
    present = [c for c in classes if per[c]["support"]]
    macro = sum(per[c]["f1"] for c in present) / len(present) if present else 0.0
    return {"n": len(rows), "subset_accuracy": round(exact / len(rows), 4) if rows else 0, "macro_f1": round(macro, 4), "per_class": per,
            "confusion_first_label": {g: dict(v) for g, v in confusion.items()}}


def rule_table(rows, classes=CLASSES):
    """Per rule: how often it fires on the curated rows, and how often the class is right when it does (rule precision)."""
    out = {}
    for rid, cls, rx, w in _COMPILED:
        fired = tp = 0
        for r in rows:
            text = normalise_reason(r["text"])
            if rx.search(text):
                fired += 1
                tp += cls in r["labels"]
        out[rid] = {"class": cls, "weight": w, "fired": fired, "precision": round(tp / fired, 4) if fired else None}
    return out
