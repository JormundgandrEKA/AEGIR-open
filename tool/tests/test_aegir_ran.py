"""Offline tests: parsers, grading, storage rules, history import, diff/flags, client limits."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
FIX = HERE / "fixtures"

from aegir_ran import ctgov, derive, epmc, labels, link, pmc, pubmed, reports  # noqa: E402
from aegir_ran.context import Ctx  # noqa: E402
from aegir_ran.core import redact_url, read_jsonl  # noqa: E402
from aegir_ran.http import BudgetExceeded, is_ncbi_daytime  # noqa: E402


def fixture(name):
    return (FIX / name).read_bytes()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(HERE.parent.parent / "config", self.tmp / "config",
                        ignore=shutil.ignore_patterns("*.local.json"))
        os.environ.pop("NCBI_API_KEY", None)
        os.environ.pop("NCBI_EMAIL", None)
        self.ctx = Ctx(self.tmp, sleep=lambda s: None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestLicence(Base):
    def lic(self, name):
        return pmc.parse_licence(fixture(f"pmc_{name}.xml"))

    def test_grades(self):
        g = self.ctx.grades
        self.assertEqual(self.lic("ccby")["licence"], "cc-by")
        self.assertEqual(pmc.grade_for(g, "cc-by", "Trials"), "B")
        self.assertEqual(pmc.grade_for(g, "cc-by", "Lancet"), "B-")
        self.assertEqual(pmc.grade_for(g, self.lic("ccbync")["licence"]), "D-")
        self.assertEqual(pmc.grade_for(g, self.lic("custom")["licence"]), "F")
        self.assertEqual(pmc.grade_for(g, self.lic("arr")["licence"]), "F")
        self.assertEqual(pmc.grade_for(g, self.lic("none")["licence"]), "ungraded")

    def test_grade_gate(self):
        g = self.ctx.grades
        self.assertTrue(pmc.grade_at_least(g, "D-", "D-"))
        self.assertFalse(pmc.grade_at_least(g, "F", "D-"))
        self.assertFalse(pmc.grade_at_least(g, "ungraded", "D-"))
        self.assertTrue(pmc.do_not_redistribute(self.ctx, "C"))
        self.assertFalse(pmc.do_not_redistribute(self.ctx, "B-"))

    def test_classify_variants(self):
        c = pmc.classify
        self.assertEqual(c("https://creativecommons.org/licenses/by-sa/4.0/", ""), "cc-by-sa")
        self.assertEqual(c("https://creativecommons.org/publicdomain/zero/1.0/", ""), "cc0")
        self.assertEqual(c("", "Creative Commons Attribution License"), "cc-by")

    def test_fulltext_refused_below_gate(self):
        self.ctx.store.append("licences.jsonl", {"pmcid": "PMC1", "grade": "F", "licence": "custom",
                                                 "licence_url": None, "do_not_redistribute": True})
        pmc.fulltext(self.ctx, ["PMC1"])
        self.assertEqual(self.ctx.counts.get("fulltext_refused_grade"), 1)
        self.assertEqual(self.ctx.client.used, 0)


class TestPubmed(Base):
    def test_parse(self):
        import xml.etree.ElementTree as ET
        el = ET.fromstring(fixture("pubmed_article.xml")).find("PubmedArticle")
        a = pubmed.parse_article(el)
        self.assertEqual((a["pmid"], a["pmcid"], a["doi"], a["journal"]), ("11111111", "PMC7777777", "10.1186/x", "Trials"))
        self.assertEqual(a["secondary_ids"], ["NCT09999999"])
        self.assertEqual(a["text_ncts"], ["NCT08888888"])

    def test_fetch_splits_and_links(self):
        body = fixture("pubmed_article.xml")
        from aegir_ran.http import Response
        resp = Response(200, body, "https://eutils.example/efetch", {}, "GET")
        with mock.patch.object(self.ctx.client, "get", return_value=resp):
            link.from_pubmed(self.ctx, ["11111111"])
        links = read_jsonl(self.ctx.store.cat_path("links.jsonl"))
        self.assertEqual({(l["nct_id"], l["link_type"]) for l in links},
                         {("NCT09999999", "pubmed_si"), ("NCT08888888", "text_mention")})
        f = self.ctx.store.latest_file(["pubmed", "article", "11111111"], ".xml")
        self.assertTrue(f.with_name(f.name + ".meta.json").is_file())


class TestStore(Base):
    def test_never_overwrites(self):
        p = self.tmp / "data" / "x.txt"
        a = self.ctx.store.write_new(p, b"1")
        b = self.ctx.store.write_new(p, b"2")
        self.assertNotEqual(a, b)
        self.assertEqual(a.read_bytes(), b"1")

    def test_strip_personal(self):
        s = json.loads(fixture("ctgov_study.json"))
        self.assertTrue(ctgov.strip_personal(s))
        txt = json.dumps(s)
        for bad in ("x@y.z", "centralContacts", "overallOfficials", "Dr A", '"Z"'):
            self.assertNotIn(bad, txt)
        self.assertIn("US", txt)

    def test_redaction(self):
        self.assertEqual(redact_url("https://h/x?db=a&api_key=SECRET&email=a@b.c"),
                         "https://h/x?db=a&api_key=REDACTED&email=REDACTED")

    def test_dry_run_writes_nothing(self):
        ctx = Ctx(self.tmp, dry_run=True)
        ctx.store.append("studies.jsonl", {"a": 1})
        ctx.store.write_new(self.tmp / "data" / "y", b"1")
        self.assertFalse((self.tmp / "data").exists())


class TestHistory(Base):
    def setUp(self):
        super().setUp()
        d = self.tmp / "in"
        d.mkdir()
        shutil.copy(FIX / "history_index.json", d / "NCT00000001_index.json")
        for v in (1, 2, 3):
            shutil.copy(FIX / f"history_v{v}.json", d / f"NCT00000001_v{v}.json")
        self.files = [str(d / n) for n in sorted(os.listdir(d))]

    def load(self):
        ctgov.import_history(self.ctx, self.files)

    def test_import_and_provenance(self):
        self.load()
        self.assertEqual(self.ctx.counts["imported_versions"], 3)
        vf = self.tmp / "data/raw/ctgov/history/NCT00000001/v2.json"
        meta = json.loads(vf.with_name("v2.json.meta.json").read_text())
        self.assertEqual(meta["collected_via"], "user browser")
        # re-import is a no-op for versions
        ctx2 = Ctx(self.tmp)
        ctgov.import_history(ctx2, self.files)
        self.assertEqual(ctx2.counts.get("version_already_stored"), 3)

    def test_diff(self):
        self.load()
        derive.diff(self.ctx, "NCT00000001", 1, 2)
        self.assertEqual(self.ctx.notes["changed_fields"], ["eligibility_criteria"])
        self.assertLess(self.ctx.notes["similarity"]["eligibility_criteria"], 1.0)

    def test_needed_versions(self):
        idx = ctgov.parse_index(json.loads(fixture("history_index.json")))
        self.assertEqual(ctgov.needed_versions(idx, "2012-01", "2013-01"), [1, 2])

    def test_flags_positive(self):
        self.load()
        search = {"query_id": "q", "studies": [json.loads(fixture("ctgov_study.json"))]}
        ctx = self.ctx
        p = ctx.store.save_raw(["ctgov", "search", "q"], "20260101T000000Z.json", json.dumps(search).encode(),
                               {"ctgov_data_timestamp": "2026-01-01T00:00:00"})
        ctx.store.append("searches.jsonl", {"query_id": "q", "source": "ctgov", "file": ctx.store.rel(p)})
        derive.label_flags(ctx, "q")
        self.assertEqual(ctx.counts["candidate_positive"], 1)
        rows = (self.tmp / ctx.notes["derived_file"]).read_text().splitlines()
        self.assertIn("NCT00000001", rows[1])
        self.assertIn("TERMINATED", rows[1])
        self.assertIn("positive", rows[1])


class TestClient(Base):
    def fake_open(self, status=200, body=b"{}"):
        r = mock.MagicMock()
        r.status, r.read.return_value, r.headers = status, body, {}
        r.__enter__.return_value = r
        return r

    def test_budget(self):
        ctx = Ctx(self.tmp, max_requests=1, sleep=lambda s: None)
        with mock.patch("urllib.request.urlopen", return_value=self.fake_open()):
            ctx.client.get("https://clinicaltrials.gov/api/v2/version")
            with self.assertRaises(BudgetExceeded):
                ctx.client.get("https://clinicaltrials.gov/api/v2/version")

    def test_retry_then_ok_and_key_never_logged(self):
        os.environ["NCBI_API_KEY"], os.environ["NCBI_EMAIL"] = "SECRETKEY", "me@example.org"
        try:
            ctx = Ctx(self.tmp, sleep=lambda s: None)
            seq = [urllib.error.HTTPError("u", 503, "x", {}, io.BytesIO(b"")), self.fake_open()]
            with mock.patch("urllib.request.urlopen", side_effect=seq):
                r = ctx.client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi", {"db": "pubmed"})
            self.assertTrue(r.ok)
            self.assertEqual(ctx.client.used, 2)
            log = (self.tmp / "data/catalogue/fetch_log.jsonl").read_text()
            self.assertNotIn("SECRETKEY", log + json.dumps(r.url) + json.dumps(r.params))
            self.assertNotIn("me@example.org", log + r.url)
        finally:
            os.environ.pop("NCBI_API_KEY"), os.environ.pop("NCBI_EMAIL")

    def test_cross_process_rate_file(self):
        ctx = Ctx(self.tmp, sleep=lambda s: None)
        ctx.client._acquire("clinicaltrials.gov")
        self.assertIn("clinicaltrials.gov", json.loads((self.tmp / "state/rate.json").read_text()))

    def test_window(self):
        from datetime import datetime, timezone
        self.assertFalse(is_ncbi_daytime(datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc)))   # Saturday
        self.assertTrue(is_ncbi_daytime(datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)))    # Wed 11am ET


class TestReports(Base):
    def test_tally_and_snapshot_guard(self):
        reports.tally(self.ctx)
        self.assertIn("stored:articles", self.ctx.notes["tally"])
        ctx = Ctx(self.tmp)
        reports.snapshot(ctx, "s1", "not-a-named-query")
        self.assertTrue(ctx.errors)


class TestV2(Base):
    def test_pmc_journal_from_record_fixes_grade(self):
        lic = pmc.parse_licence(fixture("pmc_ccby.xml"))
        self.assertEqual(lic["journal"], "Trials")
        self.assertEqual(pmc.grade_for(self.ctx.grades, lic["licence"], lic["journal"]), "B")

    def test_epmc_normalise(self):
        self.assertEqual(epmc.normalise("cc by"), "cc-by")
        self.assertEqual(epmc.normalise("CC BY-NC-ND"), "cc-by-nc-nd")
        self.assertEqual(epmc.normalise("cc0"), "cc0")
        self.assertIsNone(epmc.normalise(""))

    def test_epmc_one_pmid_per_request(self):
        from aegir_ran.http import Response
        body = json.dumps({"resultList": {"result": [{"pmid": "1", "pmcid": "PMC1", "license": "cc by",
                           "journalInfo": {"journal": {"medlineAbbreviation": "Trials"}}}]}}).encode()
        seen = []

        def fake(url, params=None, **k):
            seen.append(params["query"])
            return Response(200, body, url, params or {}, "GET")
        with mock.patch.object(self.ctx.client, "get", side_effect=fake):
            epmc.licence(self.ctx, ["1", "2"])
            epmc.licence(self.ctx, ["1"])          # cached
        self.assertEqual(seen, ["EXT_ID:1 AND SRC:MED", "EXT_ID:2 AND SRC:MED"])
        self.assertEqual(self.ctx.store.latest("epmc_licences.jsonl", "pmid")["1"]["indicative_grade"], "B")

    def _history(self):
        d = self.tmp / "in"
        d.mkdir()
        shutil.copy(FIX / "history_index.json", d / "NCT00000001_history.json")
        idx = json.loads((d / "NCT00000001_history.json").read_text())
        (d / "NCT00000001_history.json").write_text(json.dumps({"nct_id": "NCT00000001", "changes": idx["changes"],
                                                                "provenance": {"collected_via": "user browser"}}))
        for v in (1, 2, 3):
            shutil.copy(FIX / f"history_v{v}.json", d / f"NCT00000001_v{v}.json")
        ctgov.import_history(self.ctx, [str(d)])          # a folder is accepted
        search = {"query_id": "q", "studies": [json.loads(fixture("ctgov_study.json"))]}
        p = self.ctx.store.save_raw(["ctgov", "search", "q"], "20260101T000000Z.json", json.dumps(search).encode(),
                                    {"ctgov_data_timestamp": "t"})
        self.ctx.store.append("searches.jsonl", {"query_id": "q", "source": "ctgov", "file": self.ctx.store.rel(p)})

    def test_label_flags_t12(self):
        self._history()
        derive.label_flags(self.ctx, "q")
        # start 2012-01 -> 2012-01-01; v2 (2012-06-15) is in window and labelled Eligibility
        self.assertEqual(self.ctx.counts["candidate_positive"], 1)
        self.assertEqual(self.ctx.counts["low_accrual_stops"], 1)      # "Slow accrual"

    def test_content_flags_and_batch(self):
        self._history()
        derive.content_flags(self.ctx, "q")
        doc = json.loads((self.tmp / self.ctx.notes["derived_file"]).read_text())
        t = doc["trials"]["NCT00000001"]
        self.assertEqual((t["baseline_version"], t["baseline_post_start"], t["window_versions"]), (1, False, [2]))
        self.assertTrue(t["elig_text"] is False or t["elig_text"] is True)
        self.assertTrue(t["substantive"])
        self.assertNotIn("@", json.dumps(t))

    def test_synthetic_batch_and_session(self):
        labels.build_batch(self.ctx, None, 0, 0, 28, name="syn", synthetic=5)
        batch = json.loads((self.tmp / "data/labels/batches/syn.json").read_text())
        self.assertEqual(len(batch["cases"]), 5)
        s = labels.Session(self.ctx, "tester", self.tmp / "data/labels/batches/syn.json")
        public = s.state()["cases"][0]
        self.assertNotIn("provisional", public)
        self.assertNotIn("_design", public)
        cid = batch["cases"][0]["case_id"]
        s.save({"case_id": cid, "answers": {"real_change": "yes", "change_types": ["sample_size", "elig_narrowed"], "severity": "minor"},
                "timing": {"active_seconds": 12}})
        rec = read_jsonl(self.tmp / "data/labels/tester/labels.jsonl")[0]
        self.assertEqual((rec["schema"], rec["label"], rec["change_type"], rec["labeller"]),
                         ("gold-label/0.1", "positive", "enrolment", "human:tester"))
        self.assertEqual(rec["change_types"], ["sample_size", "elig_narrowed"])
        self.assertEqual(rec["change_types_enum"], ["eligibility", "enrolment"])
        with self.assertRaises(ValueError):
            s.save({"case_id": cid, "answers": {"real_change": "yes"}})
        with self.assertRaises(ValueError):
            labels.safe_name("../x")

    def test_server_loopback_only(self):
        import threading
        import urllib.request
        labels.build_batch(self.ctx, None, 0, 0, 28, name="syn", synthetic=2)
        s = labels.Session(self.ctx, "tester", self.tmp / "data/labels/batches/syn.json")
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), labels.make_handler(s, lambda: None))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        try:
            self.assertEqual(srv.server_address[0], "127.0.0.1")
            self.assertIn(b"RAN labelling", urllib.request.urlopen(f"http://127.0.0.1:{port}/").read())
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/state", headers={"Host": "evil.example"})
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(req)
            self.assertNotIn("http://", labels.HTML.replace("http://127.0.0.1", "").replace("http://www.w3.org", ""))
        finally:
            srv.shutdown()

    def test_notepad_persists_and_text_clean(self):
        labels.build_batch(self.ctx, None, 0, 0, 28, name="syn", synthetic=2)
        s = labels.Session(self.ctx, "tester", self.tmp / "data/labels/batches/syn.json")
        s.notepad_save({"text": "first", "case_id": "c001"})
        s.notepad_save({"text": "first and more", "case_id": "c002"})
        s2 = labels.Session(self.ctx, "tester", self.tmp / "data/labels/batches/syn.json")
        self.assertEqual(s2.state()["notepad"], "first and more")
        from aegir_ran.textclean import clean_text
        html_v = "<p>Inclusion Criteria:</p><ul><li>Age &#x2265; 18</li><li>Pi*ZZ a&#x2F;b</li></ul>"
        md_v = "**Inclusion Criteria:**" + chr(10) * 2 + "* Age ≥ 18" + chr(10) + "* Pi*ZZ a/b"
        flat = lambda t: " ".join(t.split())
        self.assertEqual(flat(clean_text(html_v)), flat(clean_text(md_v)))

    def test_confirmation_needs_two_humans(self):
        L = {("human:a", "N1", 1): {"label": "positive"}, ("human:b", "N1", 1): {"label": "positive"},
             ("human:a", "N2", 1): {"label": "positive"}, ("human:b", "N2", 1): {"label": "negative"},
             ("model:x", "N3", 1): {"label": "positive", "provisional": True},
             ("human:a", "N3", 1): {"label": "positive"}}
        conf, dis, single = reports.confirmation(L)
        self.assertEqual((conf, dis, single), ({("N1", 1): "positive"}, [("N2", 1)], 1))


class TestAmend(unittest.TestCase):
    """Rules refined on the first labelled cases and on the stress test (tool/tests/stress_amend.py)."""

    @staticmethod
    def F(text="", **kw):
        base = {"eligibility_criteria": text, "min_age": "18 Years", "max_age": "", "sex": "ALL",
                "healthy_volunteers": "False", "primary_outcomes": "", "enrollment": "100",
                "enrollment_type": "ESTIMATED", "arms": "", "interventions": ""}
        base.update(kw)
        return base

    def kinds(self, a, b, substantive_only=True):
        from aegir_ran import amend
        res = amend.analyse(a, b)["findings"]
        return sorted({f["kind"] for f in res if f["substantive"] or not substantive_only})

    def test_identical_after_normalisation(self):
        a = self.F("Inclusion Criteria:\n\n• FEV1 ≥ 50 percent\n• Age 40 years")
        b = self.F(__import__("aegir_ran.textclean", fromlist=["x"]).clean_text("**Inclusion Criteria:**\n\n* FEV1 >= 50 percent\n* AGE 40 YEARS"))
        self.assertEqual(self.kinds(a, b), [])
        self.assertEqual(self.kinds(a, b, False), ["format_only"])      # listed as a minor format difference only

    def test_wording_edits_are_not_substantive(self):
        a = self.F("Inclusion Criteria:\n• History of exacerbation\n• Chronic obstructive pulmonary disease")
        for b in ("Inclusion Criteria:\n• Hisotry of exacerbation\n• Chronic obstructive pulmonary disease",   # typo
                  "Inclusion Criteria:\n• History of exacerbation\n• Chronic obstructive pulmonary disease (COPD)"):  # acronym
            self.assertEqual(self.kinds(a, self.F(b)), [])

    def test_acronym_expansion_in_parentheses_is_not_a_threshold(self):
        a = self.F("Inclusion Criteria:\n• Diagnosis as documented (FEV1 <80 percent predicted)")
        b = self.F("Inclusion Criteria:\n• Diagnosis as documented (FEV1 (Forced expiratory volume in 1 second) <80 percent predicted)")
        self.assertEqual(self.kinds(a, b), [])

    def test_real_changes_are_substantive(self):
        a = self.F("Inclusion Criteria:\n• FEV1 < 80 percent\n\nExclusion Criteria:\n• Asthma")
        self.assertIn("threshold_changed", self.kinds(a, self.F("Inclusion Criteria:\n• FEV1 < 70 percent\n\nExclusion Criteria:\n• Asthma")))
        self.assertIn("criterion_added", self.kinds(a, self.F("Inclusion Criteria:\n• FEV1 < 80 percent\n\nExclusion Criteria:\n• Asthma\n• Recent stroke within six months")))
        self.assertTrue({"reworded", "criterion_added"} & set(self.kinds(a, self.F("Inclusion Criteria:\n• FEV1 < 80 percent\n\nExclusion Criteria:\n• Pneumonia"))))
        self.assertIn("age_limit_changed", self.kinds(a, self.F(a["eligibility_criteria"], min_age="21 Years")))

    def test_threshold_direction_reads_the_section(self):
        from aegir_ran import amend
        inc = amend.analyse(self.F("Inclusion Criteria:\n• Age ≥ 40"), self.F("Inclusion Criteria:\n• Age ≥ 30"))
        exc = amend.analyse(self.F("Exclusion Criteria:\n• BMI ≥ 40"), self.F("Exclusion Criteria:\n• BMI ≥ 30"))
        self.assertEqual(inc["findings"][0]["direction"], "broadened")
        self.assertEqual(exc["findings"][0]["direction"], "narrowed")

    def test_split_list_is_restructured_not_changed(self):
        a = self.F("Exclusion Criteria:\n• Systolic pressure below 90, recent stroke, unstable angina")
        b = self.F("Exclusion Criteria:\n• Systolic pressure below 90\n• recent stroke\n• unstable angina")
        self.assertEqual(self.kinds(a, b), [])

    def test_enrolment_actual_versus_planned(self):
        a, b = self.F("x"), self.F("x", enrollment="80", enrollment_type="ACTUAL")
        self.assertEqual(self.kinds(a, b), [])
        self.assertEqual(self.kinds(self.F("x"), self.F("x", enrollment="200")), ["sample_size_changed"])

    def test_outcome_elements(self):
        a = self.F("x", primary_outcomes="Change from baseline in FEV1 | Week 12")
        self.assertEqual(self.kinds(a, self.F("x", primary_outcomes="Change from baseline in FEV1 | Week 24")), ["outcome_timepoint_changed"])
        self.assertIn("outcome_added", self.kinds(a, self.F("x", primary_outcomes="Change from baseline in FEV1 | Week 12\nExacerbation rate | Week 12")))
        self.assertEqual(self.kinds(a, self.F("x", primary_outcomes="Change from baseline in FEV1 (total volume) | Week 12")), [])

    def test_provisional_lists_every_finding_and_suggests(self):
        from aegir_ran import amend
        a = self.F("Inclusion Criteria:\n• Age 40\n\nExclusion Criteria:\n• Asthma")
        b = self.F("Inclusion Criteria:\n• Age 40\n\nExclusion Criteria:\n• Asthma\n• Recent stroke within six months", enrollment="150")
        p = amend.provisional(amend.analyse(a, b))
        self.assertEqual(p["label"], "positive")
        self.assertIn("elig_narrowed", p["suggested_types"])
        self.assertIn("sample_size", p["suggested_types"])
        self.assertIn("Not examined", p["evidence"])
        n = amend.provisional(amend.analyse(a, a))
        self.assertEqual(n["label"], "negative")
        self.assertIn("Identical after normalising", n["evidence"])

    def test_taxonomy_consistent(self):
        from aegir_ran import amend, taxonomy
        ids = {t[0] for t in taxonomy.CHANGE_TYPES}
        self.assertTrue(set(amend.KIND_TYPES.values()) <= ids)
        self.assertTrue(all(len(o) == 4 for g in taxonomy.CHANGE_GROUPS for o in g[2]))


class TestDrafts(Base):
    def test_draft_restored_and_new_answer_schema(self):
        labels.build_batch(self.ctx, None, 0, 0, 28, name="syn", synthetic=2)
        s = labels.Session(self.ctx, "tester", self.tmp / "data/labels/batches/syn.json")
        cid = s.state()["cases"][0]["case_id"]
        s.draft_save({"case_id": cid, "answers": {"real_change": "yes"}})
        s2 = labels.Session(self.ctx, "tester", self.tmp / "data/labels/batches/syn.json")
        self.assertEqual(s2.state()["drafts"][cid], {"real_change": "yes"})
        s2.save({"case_id": cid, "answers": {"real_change": "yes", "change_types": ["elig_broadened", "wording_acronym"],
                                             "avoidable": "somewhat_avoidable", "cause": ["recruitment", "bogus"],
                                             "severity": "major"}, "timing": {}})
        rec = read_jsonl(self.tmp / "data/labels/tester/labels.jsonl")[-1]
        self.assertEqual((rec["avoidable"], rec["avoidable_level"], rec["cause"], rec["severity"]),
                         ("yes", "somewhat_avoidable", ["recruitment"], "major"))
        self.assertEqual(rec["change_types_enum"], ["eligibility", "wording_only"])
        self.assertNotIn(cid, s2.state()["drafts"])
        with self.assertRaises(ValueError):       # wording-only types cannot make a change "real"
            s2.save({"case_id": cid, "answers": {"real_change": "yes", "change_types": ["wording_acronym"]}})


if __name__ == "__main__":
    unittest.main()
