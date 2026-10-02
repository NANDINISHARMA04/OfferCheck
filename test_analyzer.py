"""Run with:  python -m unittest discover tests   (or: pytest)"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.analyzer import analyze                         # noqa: E402
from app.analyzer.email_check import find_lookalike      # noqa: E402
from app.analyzer.salary_check import extract_yearly_amounts  # noqa: E402
from app.analyzer.url_check import extract_urls          # noqa: E402

SAMPLES = ROOT / "samples"


def run(text, **kw):
    return analyze(text, use_llm=False, **kw)


class TestSamples(unittest.TestCase):
    def test_fake_gmail_offer_is_scam(self):
        r = run((SAMPLES / "fake_gmail_fee.txt").read_text())
        self.assertEqual(r.verdict, "Likely scam")

    def test_lookalike_site_is_scam(self):
        r = run((SAMPLES / "lookalike_site.txt").read_text())
        self.assertEqual(r.verdict, "Likely scam")
        self.assertTrue(any(f.title == "Lookalike careers website" for f in r.findings))

    def test_task_scam_flagged(self):
        r = run((SAMPLES / "task_scam.txt").read_text())
        self.assertGreaterEqual(r.risk_score, 60)

    def test_genuine_offer_is_low_risk(self):
        r = run((SAMPLES / "genuine.txt").read_text())
        self.assertEqual(r.verdict, "No major red flags")


class TestTextRules(unittest.TestCase):
    def test_salary_payment_is_not_a_fee_request(self):
        r = run("Your salary payment will be credited on the 1st of every month.")
        self.assertFalse(any(f.title == "Asks you to pay money" for f in r.findings))

    def test_fee_request_detected(self):
        r = run("Kindly pay the training fee of Rs 1500 to proceed.")
        self.assertTrue(any(f.title == "Asks you to pay money" for f in r.findings))
        self.assertGreaterEqual(r.risk_score, 75)   # combination rule

    def test_payment_from_official_domain_still_flagged(self):
        r = run("Please pay the joining fee of Rs 999.", sender="hr@infosys.com")
        self.assertEqual(r.verdict, "Suspicious")


class TestEmail(unittest.TestCase):
    def test_lookalikes(self):
        self.assertIsNotNone(find_lookalike("infosys-careers.com"))
        self.assertIsNotNone(find_lookalike("inf0sys.com"))
        self.assertIsNotNone(find_lookalike("hr-tcs.in"))
        self.assertIsNotNone(find_lookalike("acenture.com"))

    def test_unrelated_domains_are_not_lookalikes(self):
        for d in ["gmail.com", "iilm.edu", "github.com", "leetcode.com"]:
            self.assertIsNone(find_lookalike(d), d)

    def test_official_subdomain_trusted(self):
        r = run("Interview update", sender="noreply@careers.tcs.com")
        self.assertTrue(r.extracted["verified_sender"])


class TestExtraction(unittest.TestCase):
    def test_email_not_read_as_link(self):
        self.assertEqual(extract_urls("Contact hr.infosys@gmail.com"), [])

    def test_bare_short_link(self):
        self.assertIn("bit.ly/abc", extract_urls("Join bit.ly/abc now"))

    def test_salary_parsing(self):
        yearly = dict((t, a) for a, t in extract_yearly_amounts("Rs 50,000 per month"))
        self.assertIn(600000, yearly.values())
        amounts = [a for a, _ in extract_yearly_amounts("CTC 12 LPA")]
        self.assertEqual(amounts, [1200000])

    def test_empty_input(self):
        r = run("")
        self.assertEqual(r.risk_score, 0)


class TestCommunity(unittest.TestCase):
    def test_reported_domain_raises_risk(self):
        import os, tempfile
        os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")
        import importlib
        from app import db
        importlib.reload(db)
        db.init_db()
        db.add_report("domain", "fresher-jobs-hub.in", "Wipro", "asked for a fee")
        r = run("Wipro offer. Apply at https://fresher-jobs-hub.in/form",
                community_lookup=db.report_counts)
        self.assertTrue(any(f.check == "community" for f in r.findings))
        self.assertGreaterEqual(r.risk_score, 25)


if __name__ == "__main__":
    unittest.main()
