"""Validated CSV readers for Tresorit's six administrative exports."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from SharedLink import SharedLink
from import_limits import DEFAULT_LIMITS, ImportBudget, ImportLimitError, ParseError


class DuplicateReport(ParseError):
    """A snapshot of this type has already been selected for this import."""


@dataclass(frozen=True)
class ReportType:
    label: str
    required: tuple
    date: str
    group: str
    status: str


REPORT_TYPES = {
    "shared_links": ReportType("Shared links", ("Link ID", "Active", "Open Count", "Creator Email", "Tresor", "Password Protected", "Expiration Date", "Email Verification"), "Creation Date", "Creator Email", "Active"),
    "link_activity": ReportType("Link activity", ("Link ID", "Timestamp", "Event", "IsExternal", "Opener Email", "Creator Email", "Tresor"), "Timestamp", "Event", "Event"),
    "folder_summary": ReportType("Folder summary", ("Tresor Name", "Owner Email", "Overall Size (byte)", "Deleted Items (byte)", "External Members", "Shared Links"), "Last Modified Date", "Owner Email", ""),
    "folder_members": ReportType("Folder members", ("User", "Tresor", "Subscription Member", "Permission"), "", "Permission", "Permission"),
    "external_users": ReportType("External users", ("Invited Email", "Invitation Accepted", "Tresor", "Inviter Email", "Permission"), "Tresor Invitation Date", "Permission", "Invitation Accepted"),
    "device_status": ReportType("Device status", ("Email", "Device Name", "Device ID", "Platform", "Latest Activity Date", "Revocation"), "Latest Activity Date", "Platform", "Revocation"),
}

DATE_COLUMNS = {
    "Creation Date", "Expiration Date", "Suspension Date", "Timestamp",
    "Created Date", "Last Modified Date", "Tresor Invitation Date",
    "Expiration Date of Invite", "Latest Activity Date", "Revocation Date",
}
NUMBER_COLUMNS = {
    "Open Count", "Open Count Limit", "Overall Size (byte)", "Regular Items (byte)",
    "Deleted Items (byte)", "Internal Members", "External Members", "Pending Invites",
    "Shared Links", "File Download Count", "File Save Count", "File Open Count",
}
MISSING = {"", "n/a", "na", "-"}


def bounded_lines(data, max_columns):
    """Count delimiters before csv.reader can allocate an enormous field list.

    Keep quote state across physical lines, including escaped double quotes.
    csv.reader remains responsible for syntax and field decoding.
    """
    state, columns = "start", 1
    for line in io.StringIO(data, newline=""):
        for char in line:
            if state == "quoted":
                if char == '"':
                    state = "after_quote"
                continue
            if state == "after_quote" and char == '"':
                state = "quoted"
                continue
            if char in "\r\n":
                state, columns = "start", 1
            elif char == ",":
                columns += 1
                if columns > max_columns:
                    raise ImportLimitError("CSV exceeds the column limit.")
                state = "start"
            elif char == '"' and state == "start":
                state = "quoted"
            else:
                state = "unquoted"
        yield line


class Parser:
    def parse(self, data, filename="export.csv", budget=None, skip_kinds=()):
        budget = budget or ImportBudget()
        budget.start_file(len(data) if isinstance(data, bytes) else len(data.encode("utf-8")))
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ParseError("Export must be UTF-8 encoded. Please re-export it from Tresorit.") from exc
        data = data.lstrip("\ufeff")
        try:
            reader = csv.reader(bounded_lines(data, budget.limits.max_columns), strict=True)
            raw_headers = next(reader)
            budget.record(raw_headers)
            if any(len(value) > budget.limits.max_header_chars for value in raw_headers):
                raise ImportLimitError("CSV exceeds the column-name length limit.")
            headers = [value.strip() for value in raw_headers]
            if not headers or any(not value for value in headers) or len(set(headers)) != len(headers):
                raise ParseError("Column names must be non-empty and unique.")
            matches = [key for key, spec in REPORT_TYPES.items() if set(spec.required) <= set(headers)]
            if len(matches) != 1:
                raise ParseError("Unrecognized columns. Supported exports: " + ", ".join(spec.label for spec in REPORT_TYPES.values()) + ".")
            if matches[0] in skip_kinds:
                raise DuplicateReport("Only one export per type can be loaded at a time. Choose a single snapshot.")
            rows = []
            for file_rows, values in enumerate(reader, 1):
                budget.record(values, file_rows)
                if not values or all(not value.strip() for value in values):
                    continue
                if len(values) != len(headers):
                    raise ParseError(f"CSV line {reader.line_num}: expected {len(headers)} columns, found {len(values)}.")
                rows.append(dict(zip(headers, (value.strip() for value in values))))
            return {"kind": matches[0], "filename": Path(filename.replace("\\", "/")).name, "columns": headers, "rows": rows}
        except StopIteration as exc:
            raise ParseError("The CSV is empty; it needs a header row.") from exc
        except csv.Error as exc:
            raise ParseError(f"Invalid CSV: {exc}") from exc

    def parseSharedLinks(self, fileName):
        """Keep the original API for existing callers, with proper CSV parsing."""
        with Path(fileName).open("rb") as source:
            data = source.read(DEFAULT_LIMITS.max_file_bytes + 1)
        report = self.parse(data, str(fileName))
        if report["kind"] != "shared_links":
            raise ParseError("Expected a shared links export.")
        fields = ["Active", "Tresor", "Creator", "Creator Email", "Link Target", "Password Protected", "Open Count", "Open Count Limit", "Creation Date", "Expiration Date", "Detailed Access Logs", "Email Verification", "Download Disabled", "Watermark Type", "Watermark Position", "Email Allow List", "Suspension Date", "Link ID", "Cooperative Link"]
        return [SharedLink(*(row.get(field, "") for field in fields)) for row in report["rows"]]
