"""Categories from registry fields only (no inference), and the frozen hash split."""
from . import __version__
from .core import Paths, iso_now, stable_hash, utc_stamp, write_jsonl, year_of
from .labelstage import load_labels
from .normalise import load_trials

TOP_AREAS = ["Infections", "Neoplasms", "Musculoskeletal Diseases", "Digestive System Diseases", "Stomatognathic Diseases",
             "Respiratory Tract Diseases", "Otorhinolaryngologic Diseases", "Nervous System Diseases", "Eye Diseases",
             "Urogenital Diseases", "Female Urogenital Diseases and Pregnancy Complications", "Male Urogenital Diseases",
             "Cardiovascular Diseases", "Hemic and Lymphatic Diseases", "Congenital, Hereditary, and Neonatal Diseases and Abnormalities",
             "Skin and Connective Tissue Diseases", "Nutritional and Metabolic Diseases", "Endocrine System Diseases",
             "Immune System Diseases", "Mental Disorders", "Wounds and Injuries", "Chemically-Induced Disorders",
             "Substance-Related Disorders", "Occupational Diseases"]
TOP = set(TOP_AREAS)
SHORT = {"Congenital, Hereditary, and Neonatal Diseases and Abnormalities": "Congenital and neonatal",
         "Female Urogenital Diseases and Pregnancy Complications": "Female urogenital and pregnancy",
         "Skin and Connective Tissue Diseases": "Skin and connective tissue", "Hemic and Lymphatic Diseases": "Blood and lymphatic",
         "Otorhinolaryngologic Diseases": "Ear, nose and throat"}

REGIONS = {
    "North America": {"United States", "Canada", "Puerto Rico", "Bermuda", "Greenland"},
    "Latin America": {"Mexico", "Brazil", "Argentina", "Chile", "Colombia", "Peru", "Venezuela", "Ecuador", "Uruguay", "Paraguay", "Bolivia",
                      "Costa Rica", "Panama", "Guatemala", "Cuba", "Dominican Republic", "Honduras", "El Salvador", "Nicaragua", "Jamaica",
                      "Trinidad and Tobago", "Haiti", "Bahamas", "Barbados", "Belize", "Guyana", "Suriname"},
    "Europe": {"United Kingdom", "Germany", "France", "Italy", "Spain", "Netherlands", "Belgium", "Switzerland", "Austria", "Sweden",
               "Denmark", "Norway", "Finland", "Poland", "Czechia", "Czech Republic", "Hungary", "Romania", "Bulgaria", "Greece", "Portugal",
               "Ireland", "Ukraine", "Russia", "Russian Federation", "Serbia", "Croatia", "Slovakia", "Slovenia", "Lithuania", "Latvia",
               "Estonia", "Belarus", "Bosnia and Herzegovina", "North Macedonia", "Albania", "Iceland", "Luxembourg", "Malta", "Cyprus",
               "Moldova", "Montenegro", "Kosovo", "Georgia", "Armenia", "Azerbaijan", "Turkey", "Türkiye"},
    "Asia": {"China", "Japan", "Korea, Republic of", "South Korea", "India", "Taiwan", "Hong Kong", "Singapore", "Thailand", "Malaysia",
             "Vietnam", "Philippines", "Indonesia", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Mongolia", "Kazakhstan", "Uzbekistan",
             "Cambodia", "Myanmar", "Laos", "Macau", "Brunei", "Afghanistan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Korea, Democratic People's Republic of"},
    "Middle East": {"Israel", "Egypt", "Iran", "Iran, Islamic Republic of", "Saudi Arabia", "Lebanon", "Jordan", "Iraq", "United Arab Emirates",
                    "Qatar", "Kuwait", "Oman", "Bahrain", "Syria", "Syrian Arab Republic", "Yemen", "Palestinian Territory, occupied", "Palestine"},
    "Africa": {"South Africa", "Nigeria", "Kenya", "Uganda", "Tanzania", "Tanzania, United Republic of", "Ghana", "Ethiopia", "Malawi",
               "Zambia", "Zimbabwe", "Mozambique", "Senegal", "Mali", "Burkina Faso", "Cameroon", "Congo, The Democratic Republic of the",
               "Rwanda", "Sudan", "Morocco", "Tunisia", "Algeria", "Botswana", "Gambia", "Guinea", "Sierra Leone", "Liberia", "Gabon", "Benin",
               "Côte D'Ivoire", "Cote D'Ivoire", "Niger", "Madagascar", "Namibia", "Libya", "Mauritius", "Togo", "Angola", "Lesotho", "Swaziland"},
    "Oceania": {"Australia", "New Zealand", "Papua New Guinea", "Fiji", "Samoa", "New Caledonia"},
}
REGION_OF = {c: r for r, cs in REGIONS.items() for c in cs}
STOP_PRIORITY = ["Insufficient_Enrollment", "Covid19", "Safety_Sideeffects", "Negative", "Endpoint_Met", "Success", "Interim_Analysis",
                 "Business_Administrative", "Logistics_Resources", "Regulatory", "Study_Design", "Another_Study", "Study_Staff_Moved",
                 "Ethical_Reason", "Insufficient_Data", "Invalid_Reason", "No_Context"]


def areas_of(rec):
    names = [a for a in rec["ancestors"] + rec["mesh"] if a in TOP]
    seen = []
    for n in names:
        s = SHORT.get(n, n.replace(" Diseases", "").replace(" System", ""))
        if s not in seen:
            seen.append(s)
    return seen[:4] or ["Unclassified"]


def region_of(countries):
    rs = {REGION_OF.get(c, "Other") for c in countries}
    if not countries:
        return "Unknown"
    return rs.pop() if len(rs) == 1 else "Multi-region"


def band(n, edges, labels):
    for e, lab in zip(edges, labels):
        if n <= e:
            return lab
    return labels[-1]


def year_band(y):
    if y is None:
        return "Unknown"
    return "2005-2009" if y < 2010 else "2010-2014" if y < 2015 else "2015-2019" if y < 2020 else "2020 or later"


def phase_name(ph):
    if not ph:
        return "Not applicable"
    mp = {"EARLY_PHASE1": "Early Phase 1", "PHASE1": "Phase 1", "PHASE2": "Phase 2", "PHASE3": "Phase 3", "PHASE4": "Phase 4", "NA": "Not applicable"}
    return "/".join(mp.get(p, p) for p in ph).replace("Phase 1/Phase 2", "Phase 1/2").replace("Phase 2/Phase 3", "Phase 2/3")


def main_stop(classes):
    for c in STOP_PRIORITY:
        if c in classes:
            return c
    return "Unclassified" if classes == [] else classes[0]


def split_of(nct, sp):
    h = stable_hash(nct, sp["seed"])
    return "test" if h < sp["test"] else ("dev" if h < sp["test"] + sp["dev"] else "train")


def categorize(ctx, cfg):
    paths = Paths(ctx.root).ensure()
    trials, labels = load_trials(paths), load_labels(paths)
    sp = cfg["split"]
    stamp = utc_stamp()
    out = paths.derived / f"cats_{stamp}.jsonl"

    def rows():
        for nct, r in trials.items():
            lb = labels.get(nct)
            y = year_of(r["start"])
            yield {"nct_id": nct, "areas": areas_of(r), "phase": phase_name(r["phases"]), "sponsor_class": r["sponsor_class"] or "UNKNOWN",
                   "year": y, "year_band": year_band(y), "region": region_of(r["countries"]),
                   "site_band": band(r["n_sites"], [0, 1, 5, 20], ["No sites listed", "Single site", "2-5 sites", "6-20 sites", "21+ sites"]),
                   "allocation": r["allocation"] or "UNKNOWN", "masking": r["masking"] or "UNKNOWN", "purpose": r["purpose"] or "UNKNOWN",
                   "intervention_types": r["intervention_types"], "stop_class": main_stop(lb["stop_classes"]) if lb and r["status"] == "TERMINATED" else "",
                   "class": lb["class"] if lb else "unlabelled", "input_state": r["input_state"], "registration": r.get("registration", "unknown"), "grade": r["grade"],
                   "split": split_of(nct, sp)}
    n = write_jsonl(out, rows())
    ctx.store.append("autoran_stages.jsonl", {"stage": "categorize", "file": ctx.store.rel(out), "n": n, "ts": iso_now()})
    ctx.count("categorized", n)
    return {"file": str(out), "n": n}


def load_cats(paths):
    from .core import iter_jsonl
    f = paths.latest("cats_*.jsonl")
    if not f:
        raise FileNotFoundError("no categories yet; run `autoran categorize`")
    return {r["nct_id"]: r for r in iter_jsonl(f)}
