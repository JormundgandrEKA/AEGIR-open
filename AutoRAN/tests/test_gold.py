"""Gold review: sample, verdicts CSV, undo, blindness, and the frozen test part staying out. Synthetic data only."""
import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import autoran  # noqa: E402,F401
from autoran import gold, labeller as L, server  # noqa: E402
from autoran.core import Paths, stable_hash  # noqa: E402
from autoran.opentargets import normalise_reason  # noqa: E402

SP = {"seed": "ot-1", "test": 0.2, "dev": 0.1}
CFG = {"opentargets": {"split": SP}}


class Ctx:
    def __init__(self, root):
        self.root = root


def idx_row(nct, why, status="TERMINATED", enr=5):
    r = [None] * 24
    r[0], r[1], r[2], r[16], r[19], r[20], r[21] = nct, "t", status, why, enr, "none", 0
    return r


def lab(classes, src="rules", rules=(), dis=False):
    return {"nct_id": None, "class": "other_stop", "stop_classes": classes, "label_source": src, "confidence": 0.95, "rule_ids": list(rules), "evidence_span": None,
            "labeller_disagree": dis, "caveats": []}


class Base(unittest.TestCase):
    def answer(self, item_id, verdict, note=""):
        """Judge a case the way the page does: a blind case needs the reviewer's own classes first."""
        if gold.is_blind(item_id):
            gold.reveal(self.paths, item_id, [])
        return gold.record(self.paths, item_id, verdict, note)

    def setUp(self):
        gold._PENDING.clear()
        self.tmp = Path(tempfile.mkdtemp())
        self.paths = Paths(self.tmp).ensure()
        texts = {  # nct: (reason, OLD classes) -- the old call is deliberately wrong for some, so they change
            "NCT00000001": ("Slow inclusion", []), "NCT00000002": ("Lack of funding", ["Insufficient_Enrollment"]), "NCT00000003": ("Slow accrual", ["Insufficient_Enrollment"]),
            "NCT00000004": ("Poor recruitment", ["Insufficient_Enrollment"]), "NCT00000005": ("Low enrollment rate", ["Insufficient_Enrollment"]),
            "NCT00000006": ("Funding was not acquired", []), "NCT00000007": ("Stopped by DSMB due to increased wound infection rate", []),
            "NCT00000008": ("Not feasible to enroll participants", []), "NCT00000009": ("FDA clinical hold", []), "NCT00000010": ("Unable to recruit enough patients", ["Insufficient_Enrollment"]),
            "NCT00000011": ("Recruitment was slow", ["Insufficient_Enrollment"]), "NCT00000012": ("PI left the institution", ["Study_Staff_Moved"])}
        # a text that falls in the frozen Open Targets test part must never be drawn
        i = 0
        while True:
            t = f"frozen text number {i}"
            if stable_hash(normalise_reason(t), SP["seed"]) < SP["test"]:
                break
            i += 1
        texts["NCT00000099"] = (t, [])
        self.frozen = t
        (self.paths.derived / "index_20261101T000000Z.jsonl").write_text("\n".join(json.dumps(idx_row(n, w)) for n, (w, _) in texts.items()), encoding="utf-8")
        olds = []
        for n, (w, cl) in texts.items():
            d = lab(cl, rules=["ie_slow"] if cl else [])
            d["nct_id"] = n
            olds.append(json.dumps(d))
        (self.paths.derived / "labels_20261101T000000Z.jsonl").write_text("\n".join(olds), encoding="utf-8")
        ie = ["slow accrual", "poor recruitment", "low enrollment rate", "unable to recruit enough patients", "recruitment was slow"]
        rows = [{"text": x, "labels": ["Insufficient_Enrollment"]} for x in ie] * 3 + [{"text": "lack of funding", "labels": ["Business_Administrative"]}, {"text": "pi left the institution", "labels": ["Study_Staff_Moved"]}] * 3
        man = {"nb": L.NB().train(rows, L.CLASSES, min_count=1).dump(), "choice_ie": "rules",
               "rule_table": {rid: {"precision": 0.95} for rid in L.RULE_INDEX}}
        (self.paths.derived / "labeller_20261101T000000Z.json").write_text(json.dumps(man), encoding="utf-8")
        self.ctx = Ctx(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestBlind(Base):
    def blind_item(self):
        gold.draw(self.ctx, CFG, 6, 4, 28)
        sample, _ = gold.latest_sample(self.paths)
        return next((i for i in sample["items"] if gold.is_blind(i["item"])), None), next((i for i in sample["items"] if not gold.is_blind(i["item"])), None)

    def test_blind_card_hides_every_machine_field_until_the_reviewer_answers(self):
        b, o = self.blind_item()
        self.assertIsNotNone(b)
        c = gold.blind_card(b)
        for k in ("before", "after", "votes", "story", "tree", "rules_after", "added"):
            self.assertNotIn(k, c)
        with self.assertRaises(ValueError):
            gold.record(self.paths, b["item"], "yes")           # refused: nothing locked in yet
        full = gold.reveal(self.paths, b["item"], ["Insufficient_Enrollment"])
        self.assertEqual(full["after"], b["after"])
        gold.record(self.paths, b["item"], "no")
        row = gold.read_verdicts(self.paths)[-1]
        self.assertEqual((row["blind"], row["own"]), ("1", "Insufficient_Enrollment"))
        self.assertIn(row["own_matches_after"], ("0", "1"))

    def test_unknown_class_is_refused_and_blindness_is_fixed_per_case(self):
        b, _ = self.blind_item()
        with self.assertRaises(ValueError):
            gold.reveal(self.paths, b["item"], ["Nonsense"])
        self.assertEqual(gold.is_blind(b["item"]), gold.is_blind(b["item"]))

    def test_old_csv_without_the_new_columns_is_migrated(self):
        gold.draw(self.ctx, CFG, 6, 4, 28)
        f = gold.verdict_file(self.paths)
        old = [c for c in gold.COLUMNS if c not in ("blind", "own", "own_matches_after")]
        import csv as _csv
        with open(f, "w", encoding="utf-8-sig", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=old)
            w.writeheader()
            w.writerow({"reviewed_at": "x", "sample": "s", "item": "i1", "nct_id": "N", "verdict": "yes"})
        gold._append(self.paths, {"reviewed_at": "y", "sample": "s", "item": "i2", "nct_id": "M", "verdict": "no", "blind": 0})
        rows = gold.read_verdicts(self.paths)
        self.assertEqual([r["item"] for r in rows], ["i1", "i2"])
        self.assertEqual(rows[0]["blind"], "")
        self.assertEqual(rows[1]["blind"], "0")


class TestGold(Base):
    def test_draw_mixes_concerning_and_control_and_keeps_the_frozen_test_out(self):
        r = gold.draw(self.ctx, CFG, n_concerning=4, n_control=2, seed=1)
        self.assertEqual((r["concerning"], r["control"], r["n"]), (4, 2, 6))
        sample, _ = gold.latest_sample(self.paths)
        self.assertEqual(sorted(i["stratum"] for i in sample["items"]).count("control"), 2)
        self.assertNotIn(self.frozen, [i["why_stopped"] for i in sample["items"]])
        for i in sample["items"]:
            if i["stratum"] == "concern":
                self.assertNotEqual(i["before"], i["after"])                       # concerning cases are changed calls
            else:
                self.assertEqual(i["before"], i["after"])                          # controls are unchanged and trusted
        self.assertEqual(len({i["item"] for i in sample["items"]}), 6)

    def test_card_is_blind(self):
        gold.draw(self.ctx, CFG, 3, 2, 1)
        st = gold.state(self.paths)
        c = st["next"]
        if c.get("blind") and "after" not in c:
            c = gold.reveal(self.paths, c["item"], [])
        self.assertNotIn("stratum", c)
        self.assertNotIn("concern", c)
        self.assertNotIn("stratum", json.dumps(st))
        self.assertTrue({"why_stopped", "before", "after", "rules_added", "rules_removed"} <= set(c))

    def test_verdicts_go_to_a_csv_and_undo_removes_the_last(self):
        gold.draw(self.ctx, CFG, 3, 2, 1)
        first = gold.state(self.paths)["next"]
        st = self.answer(first["item"], "yes", "looks right")
        self.assertEqual((st["done"], st["counts"]["yes"]), (1, 1))
        second = st["next"]
        self.assertNotEqual(second["item"], first["item"])
        st = self.answer(second["item"], "other")
        self.assertEqual(st["counts"]["other"], 1)
        with open(gold.verdict_file(self.paths), encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual([r["verdict"] for r in rows], ["yes", "other"])
        self.assertEqual(rows[0]["note"], "looks right")
        self.assertIn(rows[0]["stratum"], ("concern", "control"))                   # the CSV keeps the group; the card hides it
        st = gold.undo(self.paths)
        self.assertEqual(st["done"], 1)
        self.assertEqual(st["next"]["item"], second["item"])                        # the undone case comes back
        self.assertEqual(len(gold.read_verdicts(self.paths)), 3)                    # append-only: the undo is a row, nothing is rewritten

    def test_concerning_cases_come_from_several_kinds_of_change(self):
        gold.draw(self.ctx, CFG, n_concerning=7, n_control=2, seed=3)
        sample, _ = gold.latest_sample(self.paths)
        kinds = {i["bucket"] for i in sample["items"] if i["stratum"] == "concern"}
        self.assertGreaterEqual(len(kinds), 2)
        self.assertEqual({i["bucket"] for i in sample["items"] if i["stratum"] == "control"}, {"control"})
        card = gold.state(self.paths)["next"]
        self.assertNotIn("bucket", card)                                              # blind to the kind as well

    def test_bad_verdict_and_unknown_case_are_refused(self):
        gold.draw(self.ctx, CFG, 3, 2, 1)
        c = gold.state(self.paths)["next"]
        with self.assertRaises(ValueError):
            gold.record(self.paths, c["item"], "maybe")
        with self.assertRaises(ValueError):
            gold.record(self.paths, "nope", "yes")
        self.assertFalse(gold.verdict_file(self.paths).exists())

    def test_summary_appears_only_when_everything_is_judged_and_a_second_draw_skips_judged_cases(self):
        r = gold.draw(self.ctx, CFG, 3, 2, 1)
        st = gold.state(self.paths)
        self.assertNotIn("summary", st)
        done_ncts = set()
        while st["next"]:
            done_ncts.add(st["next"]["nct_id"])
            st = self.answer(st["next"]["item"], "yes")
        self.assertEqual(st["done"], r["n"])
        self.assertEqual(st["summary"]["control"]["n"], 2)
        self.assertEqual(st["summary"]["concern"]["yes_rate"], 1.0)
        gold.draw(self.ctx, CFG, 5, 5, 2)
        sample, _ = gold.latest_sample(self.paths)
        self.assertFalse(done_ncts & {i["nct_id"] for i in sample["items"]})

    def test_routes(self):
        class S:
            pass
        s = S()
        s.paths, s.ctx, s.cfg = self.paths, self.ctx, CFG
        code, st = server.dispatch(s, "GET", "/api/gold", {}, None)
        self.assertEqual((code, st["sample"]), (200, None))
        code, st = server.dispatch(s, "POST", "/api/gold/draw", {}, {"n_concerning": 3, "n_control": 2})
        self.assertEqual((code, st["n"]), (200, 5))
        item = st["next"]["item"]
        if gold.is_blind(item):
            self.assertEqual(server.dispatch(s, "POST", "/api/gold/verdict", {}, {"item": item, "verdict": "no"})[0], 400)    # blind: refused until the reviewer answers
            code, full = server.dispatch(s, "POST", "/api/gold/reveal", {}, {"item": item, "own": []})
            self.assertEqual(code, 200)
            self.assertIn("after", full)
        code, st = server.dispatch(s, "POST", "/api/gold/verdict", {}, {"item": item, "verdict": "no"})
        self.assertEqual(st["counts"]["no"], 1)
        code, st = server.dispatch(s, "POST", "/api/gold/verdict", {}, {"item": "x", "verdict": "yes"})
        self.assertEqual(code, 400)
        code, st = server.dispatch(s, "POST", "/api/gold/undo", {}, {})
        self.assertEqual(st["done"], 0)


if __name__ == "__main__":
    unittest.main()
