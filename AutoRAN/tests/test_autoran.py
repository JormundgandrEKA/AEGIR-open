"""Offline tests for AutoRAN: statistics, labeller guards, normalising, leakage allow-list, grade floor, canaries."""
import json
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from autoran import core, labeller as L, stats, scorers, categorize, audit  # noqa: E402
from autoran.normalise import normalise_study, age_years  # noqa: E402
from autoran.labelstage import Labeller, outcome_class  # noqa: E402
from autoran.fetch import build_params  # noqa: E402


def study(nct="NCT00000001", status="TERMINATED", why="Slow accrual", start="2015-03", first="2015-01-10", last="2018-05-01",
          enroll=12, contacts=True):
    s = {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": "A test trial"},
        "statusModule": {"overallStatus": status, "whyStopped": why, "startDateStruct": {"date": start},
                         "studyFirstPostDateStruct": {"date": first}, "lastUpdatePostDateStruct": {"date": last},
                         "completionDateStruct": {"date": "2018-04"}},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Acme", "class": "INDUSTRY"}},
        "designModule": {"phases": ["PHASE2"], "designInfo": {"allocation": "RANDOMIZED", "primaryPurpose": "TREATMENT",
                                                              "maskingInfo": {"masking": "DOUBLE"}},
                         "enrollmentInfo": {"count": enroll, "type": "ACTUAL"}},
        "eligibilityModule": {"eligibilityCriteria": "Inclusion Criteria:\n\n* Age 18+\n* Diagnosis of X\n\nExclusion Criteria:\n\n* Pregnant",
                              "minimumAge": "18 Years", "sex": "ALL", "healthyVolunteers": False},
        "armsInterventionsModule": {"armGroups": [{"label": "A"}, {"label": "B"}], "interventions": [{"type": "DRUG"}]},
        "outcomesModule": {"primaryOutcomes": [{"measure": "FEV1"}]},
        "contactsLocationsModule": {"locations": [{"country": "United States"}, {"country": "Canada"}]}},
        "derivedSection": {"conditionBrowseModule": {"meshes": [{"term": "Asthma"}], "ancestors": [{"term": "Respiratory Tract Diseases"}]}}}
    return s


class TestStats(unittest.TestCase):
    def test_known_vectors(self):
        y, s = [0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]
        self.assertEqual(stats.auroc(y, s), 0.75)
        self.assertAlmostEqual(stats.auprc(y, s), 0.8333333, places=5)
        self.assertIsNone(stats.auroc([0, 0], [0.1, 0.2]))

    def test_ties_get_half_credit(self):
        self.assertEqual(stats.auroc([0, 1], [0.5, 0.5]), 0.5)

    def test_wilson(self):
        lo, hi = stats.wilson(10, 200)
        self.assertTrue(0.025 < lo < 0.03 and 0.085 < hi < 0.095)
        self.assertEqual(stats.wilson(0, 0), (0.0, 1.0))

    def test_bootstrap_is_seeded_and_brackets_the_estimate(self):
        rnd = random.Random(1)
        y = [1 if rnd.random() < 0.1 else 0 for _ in range(4000)]
        s = [rnd.random() + 0.4 * v for v in y]
        a = stats.summarize(y, s, resamples=200, seed=5)
        b = stats.summarize(y, s, resamples=200, seed=5)
        self.assertEqual(a["ci"], b["ci"])
        lo, hi = a["ci"]["auroc"]
        self.assertTrue(lo < a["auroc"] < hi)


class TestLabeller(unittest.TestCase):
    def ie(self, text):
        return "Insufficient_Enrollment" in L.classify_rules(text)[0]

    def test_recruitment_failures(self):
        for t in ["Slow accrual", "Low enrollment rate", "Unable to recruit enough patients", "Poor recruitment", "only 3 patients enrolled",
                  "Lack of eligible patients", "Difficulty in recruiting", "Recruitment was slow", "acrrual target was not being met",
                  "delayed recruitment"]:
            self.assertTrue(self.ie(t), t)

    def test_guards_not_recruitment_failures(self):
        for t in ["Accrual goal met", "Recruitment completed", "Target enrollment reached", "Sponsor decision", "Lack of efficacy",
                  "The study drug supply was exhausted", "Accrual was completed"]:
            self.assertFalse(self.ie(t), t)

    def test_rule_fixes_from_the_aact_review(self):
        # misses found in the AACT export: "inclusion" for enrolment, "not feasible" with a space, plural goals, "not been able to"
        for t in ["Slow inclusion", "Low inclusion rate.", "Lack of inclusions", "Not feasible to enroll participants", "Enrollment goals were not able to be met",
                  "Recruitment goals could not be met even after amendments", "We have not been able to enroll patients", "Hard to find patient",
                  "Lack of study patients", "Closed due to prolonged enrollment timelines", "Study was recruited slowly", "We exhausted all ability to recruit from our study sites",
                  "Slow recruitment� due to COVID", "The study was prematurely stopped since enrollment was much slower than initially expected", "Recruitment is slower"]:
            self.assertTrue(self.ie(t), t)
        # false hits removed: efficacy "limited", follow-up attrition, staff exhaustion, inclusion criteria, enough patients
        for t in ["The overall clinical benefit of enrolled subjects was limited and further development stopped",
                  "Analysis was not done because only 1 subject was able to come back for the 3 month follow up visit",
                  "exhausted personel after a long recruiting period", "Inclusion criteria were changed", "The number of included patients is sufficient.",
                  "Limited safety and immunological data could be accrued from incomplete regimens"]:
            self.assertFalse(self.ie(t), t)

    def test_disease_words_are_not_harm(self):
        for t in ["Too few acute stroke patients available to meet enrollment requirements.", "high rate of drop-out", "Experimental treatment not feasible due to high rate of drop out"]:
            self.assertNotIn("Safety_Sideeffects", L.classify_rules(t)[0], t)
        for t in ["Recruitment terminated due to higher rate of thrombosis events than expected.", "Due to thrombosis", "Incidence of GI Perforation"]:
            self.assertIn("Safety_Sideeffects", L.classify_rules(t)[0], t)

    def test_model_classes_are_trusted_only_where_they_scored(self):
        man = {"nb": L.NB().train([{"text": "x", "labels": ["No_Context"]}], L.CLASSES, min_count=1).dump(), "rule_table": {}, "choice_ie": "rules",
               "metrics": {"nb": {"dev": {"per_class": {"Business_Administrative": {"f1": 0.79, "precision": 0.75, "support": 72}, "Interim_Analysis": {"f1": 0.05, "precision": 0.02, "support": 4},
                                                                "Safety_Sideeffects": {"f1": 0.57, "precision": 0.56, "support": 17}, "Endpoint_Met": {"f1": 0.9, "precision": 1.0, "support": 6}}}}}}
        self.assertEqual(Labeller(man, []).nb_ok, {"Business_Administrative", "Insufficient_Enrollment"})
        self.assertEqual(Labeller({k: v for k, v in man.items() if k != "metrics"}, []).nb_ok, {"Insufficient_Enrollment"})

    def test_no_enrolment_next_to_another_cause_is_that_cause(self):
        cl, _, _ = L.classify_rules("Funding was never received so no patients were enrolled")
        self.assertIn("Business_Administrative", cl)
        self.assertNotIn("Insufficient_Enrollment", cl)

    def test_covid_and_safety(self):
        self.assertIn("Covid19", L.classify_rules("Halted due to the COVID-19 pandemic")[0])
        cl = L.classify_rules("Stopped early; this was not due to safety concerns")[0]
        self.assertNotIn("Safety_Sideeffects", cl)

    def test_typos_normalised(self):
        self.assertTrue(self.ie("Poor acrual"))

    def test_nb_roundtrip(self):
        rows = [{"text": "slow enrollment of patients", "labels": ["Insufficient_Enrollment"]},
                {"text": "low recruitment rate", "labels": ["Insufficient_Enrollment"]},
                {"text": "sponsor business decision", "labels": ["Business_Administrative"]},
                {"text": "funding ended", "labels": ["Business_Administrative"]}] * 3
        nb = L.NB().train(rows, L.CLASSES, min_count=1)
        again = L.NB.load(json.loads(json.dumps(nb.dump())))
        self.assertEqual(nb.predict("slow enrollment")[0], again.predict("slow enrollment")[0])

    def test_withdrawn_trials_are_recruitment_failures_only_when_nobody_came(self):
        man = {"nb": L.NB().train([{"text": "x", "labels": ["No_Context"]}], L.CLASSES, min_count=1).dump(), "rule_table": {}, "choice_ie": "rules"}
        lab = Labeller(man, [])
        w = lambda t, kind: outcome_class({"status": "WITHDRAWN", "why_stopped": t, "enrollment": {"count": 0}}, lab.label(t), kind)
        self.assertEqual(w("Failed to enroll any patients despite study modifications", "no_takers")[0], "positive_recruitment")
        self.assertEqual(w("Need to obtain IDE prior to commencement of study", "approval_blocked")[0], "other_stop")
        self.assertEqual(w("Study never started", "empty_record")[0], "unlabelled")
        self.assertIn("withdrawn_before_enrollment", w("Funding was not acquired", "resources_pulled")[1])
        self.assertEqual(outcome_class({"status": "WITHDRAWN", "why_stopped": "Slow accrual", "enrollment": {"count": 0}}, lab.label("Slow accrual"))[0], "other_stop")   # no kind given: never counted as a failure

    def test_outcome_classes(self):
        man = {"nb": L.NB().train([{"text": "x", "labels": ["No_Context"]}], L.CLASSES, min_count=1).dump(), "rule_table": {}, "choice_ie": "rules"}
        lab = Labeller(man, [])
        rec = {"status": "TERMINATED", "why_stopped": "Slow accrual", "enrollment": {"count": 5}}
        self.assertEqual(outcome_class(rec, lab.label(rec["why_stopped"]))[0], "positive_recruitment")
        rec2 = {"status": "TERMINATED", "why_stopped": "", "enrollment": {"count": 5}}
        self.assertEqual(outcome_class(rec2, lab.label(""))[0], "unlabelled")
        rec3 = {"status": "COMPLETED", "why_stopped": "", "enrollment": {"count": 40}}
        self.assertEqual(outcome_class(rec3, lab.label(""))[0], "negative_completed")
        rec4 = {"status": "COMPLETED", "why_stopped": "", "enrollment": {"count": 0}}
        self.assertEqual(outcome_class(rec4, lab.label(""))[0], "unlabelled")
        rec5 = {"status": "TERMINATED", "why_stopped": "Slow accrual because of COVID-19", "enrollment": {"count": 5}}
        self.assertEqual(outcome_class(rec5, lab.label(rec5["why_stopped"]))[0], "other_stop")


class TestNormalise(unittest.TestCase):
    def test_fields_and_no_personal_data(self):
        r = normalise_study(study(), "p", 0, {})
        text = json.dumps(r)
        self.assertEqual((r["nct_id"], r["n_sites"], r["countries"], r["eligibility"]["n_incl"], r["eligibility"]["n_excl"]),
                         ("NCT00000001", 2, ["Canada", "United States"], 2, 1))
        self.assertNotIn("@", text)
        self.assertEqual(r["start"], "2015-03-01")

    def test_input_states(self):
        self.assertEqual(normalise_study(study(), "p", 0, {})["input_state"], "current")
        self.assertEqual(normalise_study(study(last="2015-01-10"), "p", 0, {})["input_state"], "never_updated")
        self.assertEqual(normalise_study(study(first="2015-02-01", last="2015-02-20", start="2015-03-01"), "p", 0, {})["input_state"], "current_unchanged")
        self.assertEqual(normalise_study(study(), "p", 0, {"NCT00000001": "2015-02-01"})["input_state"], "first_version")
        r = normalise_study(study(), "p", 0, {"NCT00000001": "2016-02-01"})
        self.assertTrue(r["baseline_post_start"])

    def test_registration_timing(self):
        self.assertEqual(normalise_study(study(first="2015-01-10", start="2015-03"), "p", 0, {})["registration"], "prospective")
        self.assertEqual(normalise_study(study(first="2016-01-10", start="2015-03"), "p", 0, {})["registration"], "retrospective")

    def test_age(self):
        self.assertEqual(age_years("18 Years"), 18.0)
        self.assertAlmostEqual(age_years("6 Months"), 0.5)


class TestLeakage(unittest.TestCase):
    def test_allow_list_excludes_every_forbidden_field(self):
        self.assertEqual(set(scorers.ALLOWED) & set(scorers.FORBIDDEN), set())
        rec = normalise_study(study(), "p", 0, {})
        rec["class"] = "positive_recruitment"
        view = scorers.input_view(rec)
        for k in scorers.FORBIDDEN:
            self.assertNotIn(k, view)
        self.assertNotIn("why_stopped", view)
        self.assertNotIn("enrollment", view)

    def test_scorers_run_on_the_filtered_view_only(self):
        view = scorers.input_view(normalise_study(study(), "p", 0, {}))
        for name, make in scorers.REGISTRY.items():
            sc = make()
            if sc.trained:
                sc.fit([(view, 1), (view, 0)] * 3)
            self.assertIsInstance(sc.score(view), float, name)

    def test_random_scorer_is_deterministic(self):
        view = scorers.input_view(normalise_study(study(), "p", 0, {}))
        self.assertEqual(scorers.RandomScorer().score(view), scorers.RandomScorer().score(view))


class TestCategories(unittest.TestCase):
    def test_areas_regions_splits(self):
        r = normalise_study(study(), "p", 0, {})
        self.assertEqual(categorize.areas_of(r), ["Respiratory Tract"])
        self.assertEqual(categorize.region_of(["United States", "Canada"]), "North America")
        self.assertEqual(categorize.region_of(["United States", "France"]), "Multi-region")
        self.assertEqual(categorize.phase_name(["PHASE2", "PHASE3"]), "Phase 2/3")
        sp = {"seed": "s", "test": 0.2, "dev": 0.1}
        self.assertEqual(categorize.split_of("NCT00000001", sp), categorize.split_of("NCT00000001", sp))
        share = sum(categorize.split_of(f"NCT{i:08d}", sp) == "test" for i in range(5000)) / 5000
        self.assertTrue(0.17 < share < 0.23)


class TestFetchParams(unittest.TestCase):
    def test_scope_and_delta(self):
        cfg = {"scope": {"phases": "all", "start_from": "2005-01-01", "statuses": ["COMPLETED", "TERMINATED"]}, "page_size": 1000, "fields": ["NCTId"]}
        p = build_params(cfg)
        self.assertNotIn("PHASE", p["filter.advanced"])
        cfg["scope"]["phases"] = ["PHASE2", "PHASE3"]
        self.assertIn("AREA[Phase]PHASE2 OR AREA[Phase]PHASE3", build_params(cfg)["filter.advanced"])
        self.assertIn("LastUpdatePostDate", build_params(cfg, since="2026-10-01")["filter.advanced"])
        self.assertIn("StartDate", build_params(cfg)["filter.advanced"])                    # the default scope keeps its 2005 start
        cfg["scope"].update(start_from=None, statuses=["COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED"])
        wide = build_params(cfg)
        self.assertNotIn("StartDate", wide["filter.advanced"])                              # no start limit: pre-2005 and withdrawn trials without a start date come in
        self.assertIn("WITHDRAWN", wide["filter.overallStatus"])


class TestExportAndCanaries(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(HERE.parent / "config", self.tmp / "config")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_grade_floor_refuses_below_floor(self):
        from aegir_core import grades as pmc
        ctx = core.make_ctx(self.tmp)
        self.assertTrue(pmc.grade_at_least(ctx.grades, "B-", "B-"))
        self.assertFalse(pmc.grade_at_least(ctx.grades, "D-", "B-"))
        self.assertTrue(pmc.grade_at_least(ctx.grades, "A+", "B-"))
        cfg = core.load_cfg(self.tmp)
        self.assertEqual(cfg["sources"]["sources"]["opentargets_reasons"]["grade"], "B-")
        self.assertEqual(cfg["sources"]["sources"]["opentargets_reasons"]["licence"], "apache-2.0")

    def test_canaries_carry_a_wrong_class(self):
        paths = core.Paths(self.tmp).ensure()
        f = paths.derived / "ot_reasons_20260101T000000Z.jsonl"
        core.write_jsonl(f, [{"i": i, "text": f"reason {i}", "labels": ["Business_Administrative" if i % 2 else "Regulatory"], "split": "dev"} for i in range(40)])
        can = audit.canaries(paths, 3, 7)
        self.assertEqual(len(can), 3)
        for c in can:
            self.assertNotIn(c["stop_class"], c["true_labels"])
            self.assertTrue(c["nct"].startswith("NCT0") and len(c["nct"]) == 11)
        self.assertEqual([c["nct"] for c in can], [c["nct"] for c in audit.canaries(paths, 3, 7)])


if __name__ == "__main__":
    unittest.main()
