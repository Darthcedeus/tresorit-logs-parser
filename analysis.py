"""Transparent review rules, typed cells, and cross-export link context."""

from datetime import datetime, timedelta

from Parser import DATE_COLUMNS, MISSING, NUMBER_COLUMNS, REPORT_TYPES
from import_limits import DEFAULT_LIMITS, OutputBudget
from locations import location_sources, recorded_location


def date_value(value):
    if value.strip().lower() in MISSING:
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(value, "%d/%m/%Y")
        except ValueError:
            return None


def yes(value):
    return value.strip().lower() in {"yes", "enabled", "true"}


def analyze(reports, now=None, stale_days=90, limits=DEFAULT_LIMITS):
    now = now or datetime.now()
    output_budget = OutputBudget(limits)
    output_budget.add({"reports": [], "analyzed_at": now.isoformat(), "stale_days": stale_days})
    links = {row["Link ID"]: row for report in reports if report["kind"] == "shared_links" for row in report["rows"] if row["Link ID"]}
    result = []
    for report in reports:
        spec = REPORT_TYPES[report["kind"]]
        sources = location_sources(report["kind"], report["columns"])
        output = {**report, "label": spec.label, "date_column": spec.date, "group_column": spec.group, "status_column": spec.status, "date_columns": [col for col in report["columns"] if col in DATE_COLUMNS], "rows": [], "warnings": []}
        output["location_sources"] = sources
        duplicates = set()
        invalid = 0
        duplicate_count = 0
        for original in report["rows"]:
            row = dict(original)
            notes = []
            dates = {}
            numbers = {}
            signature = tuple(original.items())
            if signature in duplicates:
                duplicate_count += 1
            duplicates.add(signature)
            for col, value in original.items():
                if col in DATE_COLUMNS:
                    parsed = date_value(value)
                    dates[col] = parsed.isoformat() if parsed else None
                    if not parsed and value.lower() not in MISSING:
                        invalid += 1
                        notes.append(f"Invalid date: {col}")
                if col in NUMBER_COLUMNS:
                    try:
                        numbers[col] = int(value) if value.lower() not in MISSING else None
                        if numbers[col] is not None and numbers[col] < 0:
                            raise ValueError
                    except ValueError:
                        numbers[col] = None
                        invalid += 1
                        notes.append(f"Invalid number: {col}")
            kind = report["kind"]
            if kind == "shared_links" and yes(row.get("Active", "")):
                if not yes(row.get("Password Protected", "")):
                    notes.append("Active link without password protection")
                if row.get("Expiration Date", "").lower() in MISSING:
                    notes.append("Active link without expiration")
                expires = date_value(row.get("Expiration Date", ""))
                if expires and expires <= now:
                    notes.append("Marked active but expiration has passed")
                if not yes(row.get("Email Verification", "")):
                    notes.append("Active link without email verification")
            elif kind == "link_activity":
                if "fail" in row["Event"].lower():
                    notes.append("Failed access event")
                if yes(row["IsExternal"]):
                    notes.append("External access event")
                link = links.get(row["Link ID"])
                row["Related link status"] = link["Active"] if link else "Not loaded"
                row["Related link expiration"] = link.get("Expiration Date", "N/A") if link else "Not loaded"
            elif kind == "folder_summary":
                if (numbers.get("External Members") or 0) > 0:
                    notes.append("Folder has external members")
                total = numbers.get("Overall Size (byte)") or 0
                deleted = numbers.get("Deleted Items (byte)") or 0
                if total and deleted / total >= 0.25:
                    notes.append("Deleted items use at least 25% of storage")
            elif kind == "folder_members":
                if not yes(row["Subscription Member"]):
                    notes.append("Member outside subscription")
            elif kind == "external_users":
                notes.append("External invitation / membership")
                if not yes(row["Invitation Accepted"]):
                    notes.append("Invitation not accepted")
                expires = date_value(row.get("Expiration Date of Invite", ""))
                if not yes(row["Invitation Accepted"]) and expires and expires <= now:
                    notes.append("Pending invitation has expired")
            elif kind == "device_status" and not yes(row["Revocation"]):
                last_seen = date_value(row["Latest Activity Date"])
                if last_seen and last_seen < now - timedelta(days=stale_days):
                    notes.append(f"Unrevoked device inactive for over {stale_days} days")
                elif not last_seen:
                    notes.append("Unrevoked device has no valid last activity date")
            row["Review notes"] = "; ".join(notes)
            analyzed_row = {"cells": row, "dates": dates, "numbers": numbers, "notes": notes}
            if sources:
                analyzed_row["locations"] = {source["key"]: recorded_location(original, source) for source in sources}
            output_budget.add(analyzed_row)
            output["rows"].append(analyzed_row)
        if report["kind"] == "link_activity":
            output["columns"] = [*report["columns"], "Related link status", "Related link expiration"]
        output["columns"] = [*output["columns"], "Review notes"]
        if invalid:
            output["warnings"].append(f"{invalid} invalid date or numeric cells; excluded from calculations.")
        if duplicate_count:
            output["warnings"].append(f"{duplicate_count} exact duplicate rows retained. Counts include duplicates.")
        output_budget.add({**output, "rows": []})
        result.append(output)
    return {"reports": result, "analyzed_at": now.isoformat(), "stale_days": stale_days}
