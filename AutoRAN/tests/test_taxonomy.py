"""The label tree: super-label > class > sub-label, plus stage, withdrawn kind and land-mine flags."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import autoran  # noqa: E402,F401
from autoran import labeller as L, taxonomy as T  # noqa: E402

TEXTS = ["Slow accrual", "Funding was not acquired", "Stopped by DSMB due to increased wound infection rate", "FDA placed the study on clinical hold after two deaths",
         "Need to obtain IDE prior to commencement of study", "Study never started", "PI left the institution", "Futility at interim analysis", "Covid-19 pandemic halted enrolment",
         "unrelated to safety, sponsor decision", "", "See detailed description"]


class TestTree(unittest.TestCase):
    def test_structure(self):
        flat = [c for cs in T.SUPER.values() for c in cs]
        self.assertEqual(sorted(flat), sorted(L.CLASSES))                           # every class sits under exactly one super-label
        self.assertEqual(len(flat), len(set(flat)))
        self.assertTrue(all(p in L.CLASSES for _, p, _ in T.SUB))
        self.assertEqual(len({i for i, _, _ in T.SUB}), len(T.SUB))                  # unique sub-label ids

    def test_sublabels_always_sit_under_a_class_that_was_called(self):
        for t in TEXTS:
            r = T.classify_tree(t)
            for sid in r["sublabels"]:
                parent = T._PARENT.get(sid) or sid.rsplit(".", 1)[0]
                self.assertTrue(parent in r["classes"] or sid.endswith(".unspecified"), (t, sid))
            for c in r["classes"]:
                self.assertTrue(any(T._PARENT.get(i) == c or i == c + ".unspecified" for i in r["sublabels"]), (t, c))   # every class hit has a sub-label
            self.assertEqual(r["classes"], L.classify_rules(t)[0])                    # the tree never changes the class call

    def test_stage_uses_registry_fields_only(self):
        self.assertEqual(T.stage_of("WITHDRAWN", None), "before_start")
        self.assertEqual(T.stage_of("TERMINATED", "0"), "before_start")
        self.assertEqual(T.stage_of("TERMINATED", "40"), "during_enrolment")
        self.assertEqual(T.stage_of("TERMINATED", None), "unknown")
        self.assertEqual(T.stage_of("COMPLETED", "100"), "after_enrolment")

    def test_withdrawn_kinds(self):
        k = lambda t: T.classify_tree(t, "WITHDRAWN", "0")["withdrawn_kind"]
        self.assertEqual(k("Failed to enroll any patients despite study modifications"), "no_takers")
        self.assertEqual(k("Low recruitment"), "no_takers")
        self.assertEqual(k("No participants enrolled"), "none_enrolled_unexplained")      # restates the status, explains nothing
        self.assertEqual(k("Need to obtain IDE prior to commencement of study"), "approval_blocked")
        self.assertEqual(k("Protocol changes"), "protocol_flawed")
        self.assertEqual(k("Funding was not acquired"), "resources_pulled")
        self.assertEqual(k("Study never started"), "empty_record")
        self.assertEqual(k("The PI is no longer work at Hadassah"), "resources_pulled")
        self.assertNotIn("withdrawn_kind", T.classify_tree("Slow accrual", "TERMINATED", "5"))

    def test_land_mines(self):
        m = lambda t, st="TERMINATED", n="30": T.classify_tree(t, st, n)["land_mine"]
        self.assertEqual(m("Stopped by DSMB due to increased wound infection rate"), "harm_to_participants")
        self.assertEqual(m("IRB terminated the study for noncompliance with the protocol"), "misconduct_or_noncompliance")
        self.assertEqual(m("FDA clinical hold"), "ordered_by_authority")
        self.assertEqual(m("Liver injury in a separate study of the same drug"), "harm_signal_elsewhere")
        self.assertEqual(m("Concern of toxicity", "WITHDRAWN", "0"), "harm_signal_elsewhere")      # nobody was enrolled to be harmed
        self.assertIsNone(m("Terminated for reasons unrelated to safety"))
        self.assertIsNone(m("The DSMB halted the trial prematurely due to futility without any safety concerns"))
        self.assertIsNone(m("Slow accrual"))
        self.assertIsNone(m("High number of withdrawals and no-shows"))


class TestBrielDomains(unittest.TestCase):
    def test_every_mapped_sublabel_exists_and_domains_group(self):
        ids = {i for i, _p, _r in T.SUB}
        self.assertTrue(set(T.BRIEL) <= ids)
        self.assertEqual(T.risk_domains(["ie.eligibility", "res.funding", "saf.death_serious"]),
                         {"design": ["ie.eligibility"], "funding": ["res.funding"]})
        self.assertEqual(T.risk_domains(None), {})


if __name__ == "__main__":
    unittest.main()
