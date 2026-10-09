"""Shared budgets for CSV decoding and the data sent to the browser."""

from dataclasses import dataclass

from jinja2.utils import htmlsafe_json_dumps


class ParseError(ValueError):
    """An export is malformed or does not match a supported schema."""


class ImportLimitError(ParseError):
    def __init__(self, message, fatal=False):
        super().__init__(message)
        self.fatal = fatal


@dataclass(frozen=True)
class ImportLimits:
    max_file_bytes: int = 32 * 1024 * 1024
    max_total_bytes: int = 32 * 1024 * 1024
    max_files: int = 100
    max_rows_per_file: int = 20_000
    max_total_rows: int = 30_000
    max_columns: int = 64
    max_header_chars: int = 128
    max_field_chars: int = 8_192
    max_total_cells: int = 250_000
    max_total_chars: int = 2_000_000
    max_output_chars: int = 16 * 1024 * 1024


DEFAULT_LIMITS = ImportLimits()


class ImportBudget:
    """Charge work even when a file is subsequently rejected or discarded."""

    def __init__(self, limits=DEFAULT_LIMITS):
        self.limits = limits
        self.files = self.bytes = self.rows = self.cells = self.chars = 0

    def start_file(self, size):
        if size > self.limits.max_file_bytes:
            raise ImportLimitError("CSV exceeds the per-file byte limit.")
        if self.files + 1 > self.limits.max_files:
            raise ImportLimitError("Import exceeds the file-count limit.", fatal=True)
        if self.bytes + size > self.limits.max_total_bytes:
            raise ImportLimitError("Import exceeds the combined byte limit.", fatal=True)
        self.files += 1
        self.bytes += size

    def record(self, values, file_rows=None):
        if len(values) > self.limits.max_columns:
            raise ImportLimitError("CSV exceeds the column limit.")
        if any(len(value) > self.limits.max_field_chars for value in values):
            raise ImportLimitError("CSV exceeds the field-length limit.")
        if file_rows is not None and file_rows > self.limits.max_rows_per_file:
            raise ImportLimitError("CSV exceeds the row limit (blank records count too).")
        rows = self.rows + (file_rows is not None)
        cells = self.cells + max(1, len(values))
        chars = self.chars + sum(map(len, values))
        if rows > self.limits.max_total_rows:
            raise ImportLimitError("Import exceeds the combined row limit.", fatal=True)
        if cells > self.limits.max_total_cells:
            raise ImportLimitError("Import exceeds the combined cell limit.", fatal=True)
        if chars > self.limits.max_total_chars:
            raise ImportLimitError("Import exceeds the combined text limit.", fatal=True)
        self.rows, self.cells, self.chars = rows, cells, chars


class OutputBudget:
    """Check each analyzed row, including joins, before retaining full output."""

    def __init__(self, limits=DEFAULT_LIMITS):
        self.limit = limits.max_output_chars
        self.used = 0

    def add(self, value):
        # ASCII JSON plus HTML-safe escapes matches the template's data encoding.
        # Rows and fields are bounded before this small piece is serialized.
        size = len(htmlsafe_json_dumps(value)) + 2
        if self.used + size > self.limit:
            raise ImportLimitError("Analyzed data exceeds the output limit. Load smaller exports.", fatal=True)
        self.used += size
