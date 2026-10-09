# Tresorit Log Explorer

A local Flask dashboard for six Tresorit CSV exports: shared links, link activity,
folder summary, folder members, external users, and device status.

Use the **Dark mode** toggle in the header to switch themes. The app follows your
system theme initially and remembers your chosen theme in this browser.

## Run locally

Requires Python 3.10 or newer. On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open [localhost:5000](http://127.0.0.1:5000). Select **Load local data folder** to
read CSVs in the sibling `../data` directory (the supplied Tresorit logs folder).
For another directory, set `LOG_DATA_DIR` before starting the app:

```powershell
$env:LOG_DATA_DIR = 'C:\path\to\exports'
.\.venv\Scripts\python.exe app.py
```

Alternatively, upload several CSVs together. Each upload replaces the current
workspace; select all related exports in the same batch. Files are identified by
their columns, not their filenames. Upload one snapshot per type. Local loading
chooses the lexicographically latest filename of each detected type, which
matches Tresorit's `type_YYYY.MM.DD.HH.MM.csv` naming convention. Different types
may have different snapshot dates; check the source filenames before comparing.

## Explore and analyze

- Switch between all six export types. Search text, emails, folder names, link IDs
  and IP addresses; tab counts show search matches across all loaded exports.
- Click an email or link ID to search it across reports, then switch tabs to
  inspect related records. Activity rows include link status and expiration from
  the loaded shared-links snapshot, joined by Link ID.
- Filter by status/permission/event, rows with review notes, and an inclusive date
  range using any available date column. These filters apply to the selected tab;
  search persists between tabs. Rows without valid dates do not match date ranges.
- Metrics and charts update with filters. Compare active links and link opens,
  failed/external events, overall/deleted storage, memberships, invitations, and
  unrevoked/stale devices. Change the distribution's group field to inspect
  countries, clients, platforms, permissions, owners, or other columns.
- Date charts show daily counts, aggregating into larger intervals for long date
  ranges. Snapshot date charts show record dates, not historical state changes.
- Sort all columns, page through records, and download the full filtered result
  as CSV, including review notes. Dates and numbers sort by their typed values.
- In **Link activity** and **Device status**, explore the offline country map.
  The **Activity map** button beside Export filtered CSV opens the first loaded
  export with location fields and scrolls directly to the map.
  Country shading can show records, review notes, failed events or external
  events (the last two apply to link activity). Click a country or city to filter
  the records and CSV download; reset filters to clear the selection.
- Device geography offers latest activity, creation and revocation locations.
  Selecting a source also selects its date field when available. Device counts
  describe snapshots, not a historical activity trail. Country rankings show
  record counts and distinct recorded IP strings; city cards show the top 12
  groups, and the city dropdown includes all groups in the selected country.

The map uses the export's country codes and recorded city labels. It does not
perform IP geolocation, infer travel or place cities at guessed coordinates.
Map/country totals follow search, status, review and date filters before the
country/city selection, so other countries remain available for comparison.
Missing locations remain counted and filterable. Countries without a matching
outline are listed and reported rather than silently omitted. IP-based locations
may reflect VPNs or proxies and cannot establish a person's physical whereabouts.
The public-domain Natural Earth map is bundled locally (see
`static/MAP-LICENSE.md`); no IP addresses or log data are sent to map services.

Review notes are transparent prompts, not a security incident verdict. Rules flag
active links without passwords, expiration or email verification; active links
past expiration; failed/external access events; external memberships and pending
or expired invitations; folders with external members or at least 25% deleted
storage; and unrevoked devices inactive for more than 90 days. Time-based rules
use server time at import. Dates use day/month/year; the exports supply no timezone.
The app does not infer historical link settings from current snapshot values.

Exact duplicate rows are retained and reported, so aggregates include them.
Invalid numeric/date cells are reported and excluded from calculations. Empty
exports with valid headers are supported. Unknown schemas, bad quoting, duplicate
headers, and inconsistent row lengths produce visible errors. Valid files still
load when another file in a batch is invalid.

## Data handling

The app parses uploads and sends the result to your browser. The web framework
may spool uploads to temporary files; the app does not keep uploaded files or
shared server state. Reloading the home page clears the
view. Charts, styling and scripts are served locally, with no CDN dependencies.
Imports are bounded before large datasets are retained:

| Limit | Maximum |
| --- | --- |
| File / combined bytes per import | 32 MiB / 32 MiB |
| Files per import or CSVs in the local folder | 100 |
| CSV records per file / per import | 20,000 / 30,000 |
| Columns / column-name characters | 64 / 128 |
| Characters per field | 8,192 |
| Combined decoded cells / text characters | 250,000 / 2,000,000 |
| Analyzed JSON data, including related-link fields | 16 MiB |

Blank CSV records count toward processing limits; headers count toward cell/text
limits. Budgets count attempted work even for rejected files. Duplicate report
types are detected from the header before body parsing; local loading skips older
types once a valid newer snapshot has been selected. Move old CSV snapshots into
a subfolder if the local folder exceeds the file limit. Local loading shares the
same aggregate budgets and stops once all six types are loaded.

An over-limit file is rejected without truncation. Earlier valid files can still
load with a visible error; output-limit failures clear the entire result instead
of rendering a partial dataset. The legacy `parseSharedLinks` API uses the same
default CSV limits. Filtered CSV downloads prefix formula-like cells with an
apostrophe for spreadsheet safety.

The local-folder action reads only the configured server directory. It is intended
for a trusted local deployment: anyone with access to the app can load that
directory. The development server binds to `127.0.0.1`. Do not expose confidential
exports through a publicly accessible deployment without access controls.

## Validation

```powershell
py -m unittest discover -s tests -v
```

Tests cover CSV parsing, all schemas, review rules, date interpretation, invalid
cells, duplicate handling, uploads, error responses, and local snapshot selection.

## Deploy with Docker Compose

Prerequisites:

- Docker Engine or Docker Desktop
- Docker Compose v2 (`docker compose`)

From the repository directory:

```sh
docker compose up -d --build
```

The app will be available at:

```text
http://localhost:5000
```

To use a different host port:

```sh
APP_PORT=8080 docker compose up -d --build
```

On Windows PowerShell, set `$env:APP_PORT = '8080'` first. You can also copy
`.env.example` to `.env` and edit the port and bind address there. Docker Compose
loads that file automatically. The `.env` file is excluded from Git.

The shell helpers in `scripts/` provide build, deploy and stop shortcuts on Linux
and macOS.

Useful commands:

```sh
docker compose logs -f
./scripts/stop.sh
```

To also load the sibling data folder in Docker (the folder must already exist):

```sh
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

This optional override mounts `../data` read-only at `/data`. Without it, upload
CSVs using the dashboard. Docker serves through Gunicorn. Its published port is
bound to `0.0.0.0` by default so other machines can connect to the deployment.
Set `APP_BIND_ADDRESS=127.0.0.1` if you want host-only access. Both the base
configuration and local-data override respect this setting. Resources are capped at
512 MiB memory, one CPU and 128 processes as additional containment.

For deployments accessible from other machines, use an authenticated reverse
proxy or restrict access to trusted users on your private network, especially
when mounting local exports. The application
does not provide user accounts. A read-only mount protects files from modification
but does not restrict who can retrieve their contents through the app.

## Repository contents

The dashboard lives in `app.py`, `analysis.py`, `locations.py`, `templates/` and `static/`.
`Parser.py` and `import_limits.py` handle CSV validation and resource budgets.
`SharedLink.py` remains for compatibility with the original parser API.
Tests live in `tests/`; GitHub Actions runs them on Python 3.10 and 3.12 and
validates both Compose configurations.

Keep real Tresorit exports outside the repository, such as the sibling `../data`
folder. CSV exports, local environment files, caches and archives are excluded
from Git and the Docker build context.
Test fixtures are generated from synthetic values; do not copy real log rows,
identifiers, emails or exported screenshots into source files or fixtures.
