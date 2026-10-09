"""Stateless dashboard for Tresorit administrative CSV exports."""

import os
from itertools import islice
from pathlib import Path

from flask import Flask, Request, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

from analysis import analyze
from Parser import DuplicateReport, ParseError, Parser
from import_limits import DEFAULT_LIMITS, ImportBudget, ImportLimitError

class BoundedRequest(Request):
    # Flask 3.0 does not consume the newer MAX_FORM_PARTS config setting.
    max_form_parts = DEFAULT_LIMITS.max_files
    # Leave room for Werkzeug's 64 KiB chunks and multipart boundary buffering.
    max_form_memory_size = 512 * 1024


app = Flask(__name__)
app.request_class = BoundedRequest
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["MAX_FORM_PARTS"] = DEFAULT_LIMITS.max_files
app.config["IMPORT_LIMITS"] = DEFAULT_LIMITS
app.config["LOG_DATA_DIR"] = os.environ.get("LOG_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))


@app.after_request
def prevent_export_caching(response):
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"
    return response


def dashboard(reports=None, errors=None, status=200):
    try:
        data = analyze(reports or [], limits=app.config["IMPORT_LIMITS"])
    except ImportLimitError as exc:
        # Do not send a silently truncated dataset after analysis or join overflow.
        data = {"reports": [], "analyzed_at": "", "stale_days": 90}
        errors = [*(errors or []), str(exc)]
        status = 400
    return render_template("index.html", data=data, errors=errors or []), status


@app.get("/")
def index():
    return dashboard()


@app.post("/process")
def process():
    reports, errors, seen = [], [], set()
    budget = ImportBudget(app.config["IMPORT_LIMITS"])
    files = [file for file in request.files.getlist("file") if file.filename]
    if not files:
        return dashboard(errors=["Choose one or more CSV exports to upload."], status=400)
    if len(files) > budget.limits.max_files:
        return dashboard(errors=["Import exceeds the file-count limit."], status=400)
    for file in files:
        name = Path(file.filename.replace("\\", "/")).name
        try:
            if not name.lower().endswith(".csv"):
                raise ParseError("Only CSV exports are supported.")
            report = Parser().parse(file.read(budget.limits.max_file_bytes + 1), name, budget, seen)
            seen.add(report["kind"])
            reports.append(report)
        except ImportLimitError as exc:
            errors.append(f"{name}: {exc}")
            if exc.fatal:
                break
        except ParseError as exc:
            errors.append(f"{name}: {exc}")
    return dashboard(reports, errors, 200 if reports else 400)


@app.post("/load-local")
def load_local():
    """Read only the configured directory; choose the latest filename per type."""
    directory = Path(app.config["LOG_DATA_DIR"])
    if not directory.is_dir():
        return dashboard(errors=["Local data folder is unavailable. Upload exports or configure LOG_DATA_DIR."], status=400)
    latest, errors = {}, []
    budget = ImportBudget(app.config["IMPORT_LIMITS"])
    paths = list(islice(directory.glob("*.csv"), budget.limits.max_files + 1))
    if len(paths) > budget.limits.max_files:
        return dashboard(errors=["Local folder exceeds the CSV file-count limit. Move older snapshots to an archive folder."], status=400)
    for path in sorted(paths, reverse=True):
        try:
            with path.open("rb") as source:
                data = source.read(budget.limits.max_file_bytes + 1)
            report = Parser().parse(data, path.name, budget, latest)
            latest.setdefault(report["kind"], report)
            if len(latest) == 6:
                break
        except DuplicateReport:
            continue
        except ImportLimitError as exc:
            errors.append(f"{path.name}: {exc}")
            if exc.fatal:
                break
        except (ParseError, OSError) as exc:
            errors.append(f"{path.name}: {exc}")
    if not latest and not errors:
        errors.append("No CSV exports found in the local data folder.")
    return dashboard(list(latest.values()), errors, 200 if latest else 400)


@app.errorhandler(RequestEntityTooLarge)
def too_large(error):
    return dashboard(errors=["Upload exceeds 32 MB or the multipart form limits. Choose fewer or smaller exports."], status=413)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("APP_PORT", "5000")))
