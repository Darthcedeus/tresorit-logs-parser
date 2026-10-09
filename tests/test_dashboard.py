import csv
import io
import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from analysis import analyze, date_value
from app import app
from Parser import ParseError, Parser, REPORT_TYPES


def export(kind, rows=(), extra=()):
    headers = list(REPORT_TYPES[kind].required) + list(extra)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, headers)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def payload(response):
    match = re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', response.get_data(as_text=True), re.S)
    return json.loads(match.group(1))


class ParserTests(unittest.TestCase):
    def test_all_schemas_detected_without_filename(self):
        for kind in REPORT_TYPES:
            with self.subTest(kind=kind):
                result = Parser().parse(export(kind), "arbitrary.csv")
                self.assertEqual(result["kind"], kind)
                self.assertEqual(result["rows"], [])

    def test_bom_quotes_commas_and_multiline(self):
        name = 'Folder, with "quotes"\nand a newline'
        result = Parser().parse(export("folder_members", [{"User": "someone@example.com", "Tresor": name, "Subscription Member": "Yes", "Permission": "Owner"}]))
        self.assertEqual(result["rows"][0]["Tresor"], name)

    def test_reordered_columns_and_future_columns(self):
        cols = list(reversed(REPORT_TYPES["folder_members"].required)) + ["Future Column"]
        report = Parser().parse((",".join(cols) + "\nOwner,Yes,Folder,user@example.com,new\n").encode())
        self.assertEqual(report["rows"][0]["User"], "user@example.com")
        self.assertEqual(report["rows"][0]["Future Column"], "new")

    def test_bad_csv_does_not_return_partial_data(self):
        good = export("folder_members", [{"User": "one", "Tresor": "Folder", "Subscription Member": "Yes", "Permission": "Owner"}])
        for raw in [b"", b"a,a\n1,2", b"unrecognized\nvalue", good + b"bad,row\n", good + b'"unterminated', b"\xff"]:
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(ParseError):
                    Parser().parse(raw)


class AnalysisTests(unittest.TestCase):
    def test_day_first_dates(self):
        self.assertEqual(date_value("04/09/2026 08:08:56"), datetime(2026, 9, 4, 8, 8, 56))
        self.assertIsNone(date_value("N/A"))
        self.assertIsNone(date_value("31/02/2026"))

    def test_link_rules_and_activity_join(self):
        link = {"Link ID": "abc", "Active": "Yes", "Open Count": "3", "Creator Email": "owner@example.com", "Tresor": "Folder", "Password Protected": "No", "Expiration Date": "01/09/2026", "Email Verification": "N/A"}
        event = {"Link ID": "abc", "Timestamp": "01/09/2026", "Event": "FailedLinkOpen", "IsExternal": "Yes", "Opener Email": "guest@example.com", "Creator Email": "owner@example.com", "Tresor": "Folder"}
        results = analyze([Parser().parse(export("shared_links", [link])), Parser().parse(export("link_activity", [event]))], now=datetime(2026, 10, 9))["reports"]
        self.assertEqual(len(results[0]["rows"][0]["notes"]), 3)
        self.assertEqual(results[1]["rows"][0]["cells"]["Related link status"], "Yes")
        self.assertEqual(len(results[1]["rows"][0]["notes"]), 2)

    def test_missing_expiration_and_inactive_links(self):
        link = {"Link ID": "a", "Active": "Yes", "Open Count": "0", "Creator Email": "owner", "Tresor": "Folder", "Password Protected": "Yes", "Expiration Date": "N/A", "Email Verification": "Enabled"}
        rows = analyze([Parser().parse(export("shared_links", [link, {**link, "Active": "No"}]))])["reports"][0]["rows"]
        self.assertEqual(rows[0]["notes"], ["Active link without expiration"])
        self.assertEqual(rows[1]["notes"], [])

    def test_devices_stale_boundary_and_revocation(self):
        device = {"Email": "user", "Device Name": "Laptop", "Device ID": "a", "Platform": "Windows", "Latest Activity Date": "01/07/2026", "Revocation": "No"}
        variants = [device, {**device, "Revocation": "Yes"}, {**device, "Latest Activity Date": "11/07/2026"}, {**device, "Latest Activity Date": "N/A"}]
        rows = analyze([Parser().parse(export("device_status", variants))], now=datetime(2026, 10, 9))["reports"][0]["rows"]
        self.assertTrue(rows[0]["notes"])
        self.assertFalse(rows[1]["notes"])
        self.assertFalse(rows[2]["notes"])
        self.assertIn("no valid", rows[3]["notes"][0])

    def test_invalid_numbers_dates_and_duplicates_are_visible(self):
        row = {"Tresor Name": "Folder", "Owner Email": "owner", "Overall Size (byte)": "oops", "Deleted Items (byte)": "-1", "External Members": "0", "Shared Links": "1", "Last Modified Date": "not a date"}
        report = analyze([Parser().parse(export("folder_summary", [row, row], ["Last Modified Date"]))])["reports"][0]
        self.assertEqual(report["rows"][0]["numbers"]["Overall Size (byte)"], None)
        self.assertEqual(report["rows"][0]["numbers"]["Deleted Items (byte)"], None)
        self.assertEqual(len(report["warnings"]), 2)
        self.assertIn("6 invalid", report["warnings"][0])
        self.assertIn("1 exact duplicate", report["warnings"][1])

    def test_storage_and_pending_invitation_rules(self):
        folder = {"Tresor Name": "Folder", "Owner Email": "owner", "Overall Size (byte)": "100", "Deleted Items (byte)": "25", "External Members": "1", "Shared Links": "2"}
        invite = {"Invited Email": "guest", "Invitation Accepted": "No", "Tresor": "Folder", "Inviter Email": "owner", "Permission": "Editor", "Expiration Date of Invite": "01/01/2026"}
        reports = [Parser().parse(export("folder_summary", [folder])), Parser().parse(export("external_users", [invite], ["Expiration Date of Invite"]))]
        result = analyze(reports, now=datetime(2026, 10, 9))["reports"]
        self.assertEqual(len(result[0]["rows"][0]["notes"]), 2)
        self.assertIn("Pending invitation has expired", result[1]["rows"][0]["notes"])


class RouteTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_empty_and_missing_upload(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.post("/process").status_code, 400)

    def test_partial_upload_and_safe_filename(self):
        response = self.client.post("/process", data={"file": [(io.BytesIO(export("folder_members")), "../../app.py.csv"), (io.BytesIO(b"bad"), "bad.csv")]})
        self.assertEqual(response.status_code, 200)
        reports = payload(response)["reports"]
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["filename"], "app.py.csv")
        self.assertIn("bad.csv:", response.get_data(as_text=True))

    def test_duplicate_export_not_double_counted(self):
        response = self.client.post("/process", data={"file": [(io.BytesIO(export("folder_members")), name) for name in ["one.csv", "two.csv"]]})
        self.assertEqual(len(payload(response)["reports"]), 1)
        self.assertIn("Only one export per type", response.get_data(as_text=True))

    def test_latest_local_export_and_missing_directory(self):
        original = app.config["LOG_DATA_DIR"]
        try:
            with tempfile.TemporaryDirectory() as tmp:
                app.config["LOG_DATA_DIR"] = tmp
                for name in ["folder_members_2026.09.01.csv", "folder_members_2026.10.01.csv"]:
                    Path(tmp, name).write_bytes(export("folder_members"))
                report = payload(self.client.post("/load-local"))["reports"][0]
                self.assertEqual(report["filename"], "folder_members_2026.10.01.csv")
            self.assertEqual(self.client.post("/load-local").status_code, 400)
        finally:
            app.config["LOG_DATA_DIR"] = original

    def test_script_content_escaped_and_no_upload_written(self):
        response = self.client.post("/process", data={"file": (io.BytesIO(export("folder_members", [{"User": "</script><script>alert(1)</script>", "Tresor": "Folder", "Subscription Member": "Yes", "Permission": "Owner"}])), "should-not-be-written.csv")})
        self.assertNotIn("</script><script>alert", response.get_data(as_text=True))
        self.assertFalse(Path("should-not-be-written.csv").exists())

    def test_upload_limit(self):
        original = app.config["MAX_CONTENT_LENGTH"]
        try:
            app.config["MAX_CONTENT_LENGTH"] = 20
            response = self.client.post("/process", data={"file": (io.BytesIO(b"x" * 30), "large.csv")})
            self.assertEqual(response.status_code, 413)
            self.assertIn("exceeds 32 MB", response.get_data(as_text=True))
        finally:
            app.config["MAX_CONTENT_LENGTH"] = original


if __name__ == "__main__":
    unittest.main()
