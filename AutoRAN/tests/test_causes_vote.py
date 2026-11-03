"""The cause-and-effect reader and the six-reader vote. Small synthetic training rows; nothing is downloaded."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import autoran  # noqa: E402,F401
from autoran import causes, labeller as L, vote  # noqa: E402

IE, BIZ, SD, SAFE = "Insufficient_Enrollment", "Business_Administrative", "Study_Design", "Safety_Sideeffects"


class TestCauses(unittest.TestCase):
    def test_two_causes_are_both_kept_in_order(self):
        r = causes.analyse("We were not able to enroll adequate number of participants that met the inclusion/exclusion criteria, and we run out of funding.")
        self.assertEqual(r["labels"], [IE, BIZ])                                   # neither deletes the other
        self.assertEqual(r["edges"], [])                                            # "and" lists side by side: no cause and effect is claimed

    def test_design_as_a_cause_of_low_enrollment(self):
        r = causes.analyse("Lack of subject interest due to study design")
        self.assertEqual(r["edges"], [{"cause": SD, "effect": IE, "via": "due to"}])
        self.assertEqual(r["primary"], [SD])                                        # the root cause, not the symptom

    def test_effect_connective_runs_the_other_way(self):
        r = causes.analyse("Funding ended, resulting in too few patients being recruited")
        self.assertIn({"cause": BIZ, "effect": IE, "via": "resulting in"}, r["edges"])

    def test_a_clause_that_says_what_it_was_not_removes_the_label(self):
        r = causes.analyse("The primary reason for the decision to discontinue the study is lack of enrolment; this decision is not related to any tolerability concerns with Givinostat.")
        self.assertEqual(r["labels"], [IE])
        self.assertEqual(r["not_about"], [SAFE])
        self.assertEqual(r["primary"], [IE])                                        # "primary reason" is stated

    def test_context_clause_is_not_a_cause(self):
        r = causes.analyse("Despite an extension of the inclusion period, enrollment was lower than planned")
        roles = {f["clause"]: f["role"] for f in r["facets"]}
        self.assertIn("outcome_despite", roles.values())
        self.assertFalse(r["edges"])

    def test_empty_and_plain_text(self):
        self.assertEqual(causes.analyse("")["labels"], [])
        self.assertEqual(causes.analyse("Slow accrual")["labels"], [IE])


ROWS = ([{"text": t, "labels": [IE]} for t in ["slow accrual", "poor recruitment", "low enrollment rate", "unable to recruit enough patients", "recruitment was slow", "not enough patients enrolled"]] * 4
        + [{"text": t, "labels": [BIZ]} for t in ["lack of funding", "sponsor business decision", "funding ended", "company strategy change", "budget cuts", "portfolio prioritisation"]] * 4
        + [{"text": t, "labels": ["Covid19"]} for t in ["covid-19 pandemic", "halted due to the pandemic", "covid restrictions"]] * 4
        + [{"text": t, "labels": [IE, BIZ]} for t in ["slow accrual and loss of funding", "low enrollment and funding ended"]] * 4)


class TestVote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = vote.Voter().fit(ROWS[:60], ROWS[60:], folds=3)

    def test_vote_reads_the_obvious_cases_and_shows_each_reader(self):
        res = self.v.predict(["slow accrual", "lack of funding", "halted due to the covid pandemic"], return_votes=True)
        self.assertTrue(res[0][IE]["include"] and not res[0][BIZ]["include"])
        self.assertTrue(res[1][BIZ]["include"])
        self.assertTrue(res[2]["Covid19"]["include"])
        self.assertEqual(set(res[0][IE]["votes"]), set(vote.DETECTORS))             # the six readers are all reported
        self.assertGreaterEqual(res[0][IE]["agree"], 3)

    def test_two_causes_can_both_be_included(self):
        r = self.v.predict("we could not enroll enough patients and the funding ran out")[0]
        self.assertIn(IE, r)
        self.assertIn(BIZ, r)

    def test_save_and_load_give_the_same_answers(self):
        f = Path(tempfile.mkdtemp()) / "voter.npz"
        self.v.save(f, {"x": 1})
        w = vote.Voter.load(f)
        texts = ["slow accrual", "sponsor business decision", "something else entirely"]
        self.assertEqual(self.v.predict(texts), w.predict(texts))
        self.assertEqual(w.meta, {"x": 1, "min_agree": 2})
        self.assertEqual(w.min_agree, 2)

    def test_contested_flag(self):
        res = self.v.predict("slow accrual", return_votes=True)[0]
        for c, v in res.items():
            self.assertEqual(v["contested"], abs(v["p"] - self.v.thresh[c]) < 0.12)


if __name__ == "__main__":
    unittest.main()
