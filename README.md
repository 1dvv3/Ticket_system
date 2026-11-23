# Arthur Phillip High School — Graduation Ticket System

A small local web app used to generate, check, and track graduation tickets for Arthur Phillip High School. It runs entirely on your own computer: there is no database server, no cloud service, and no account system. All data lives in a single `data.json` file next to the app.

Once installed, **running the app does not need internet**. Internet is only needed for the one-time setup (downloading the app, Python, and the two Python packages).

---

## Table of Contents

1. [What the app does](#what-the-app-does)
2. [Quick start (after installation)](#quick-start-after-installation)
3. [First-time installation](#first-time-installation)
4. [Updating an installed copy](#updating-an-installed-copy)
5. [Offline behaviour — what needs internet and what does not](#offline-behaviour--what-needs-internet-and-what-does-not)
6. [The four tabs](#the-four-tabs)
   - [Generate Tickets](#1-generate-tickets)
   - [Assign Barcodes (Barcode Lookup)](#2-assign-barcodes-barcodes-lookup)
   - [Scan Entry](#3-scan-entry)
   - [Sign Out](#4-sign-out)
7. [CSV format](#csv-format)
8. [Ticket counts (0–2)](#ticket-counts-02)
9. [Barcodes](#barcodes)
10. [The PDF tickets](#the-pdf-tickets)
11. [Data storage: `data.json`](#data-storage-datajson)
12. [API reference](#api-reference)
13. [Scripts: `start.sh` and `install.sh`](#scripts-startsh-and-installsh)
14. [Configuration reference](#configuration-reference)
15. [Troubleshooting](#troubleshooting)
16. [Development](#development)
17. [File map](#file-map)

---

## What the app does

The app covers the full life of a graduation ticket:

1. **Import** a class list from a CSV file (surname, given names, student ID, optional ticket count).
2. **Assign** each student 0, 1, or 2 tickets, each with a unique Code 128 barcode.
3. **Generate** a printable PDF of tickets in a 2-column × 4-row grid on A4 landscape pages.
4. **Check tickets at the door** by scanning/entering the barcode: valid tickets are accepted once; already-used or unknown tickets are rejected.
5. **Look up** one or two barcodes to see which student they belong to (and catch a mismatched pair).
6. **Track students leaving and re-entering** the venue from a dedicated Sign Out tab: the same ticket toggles OUT → IN, with a status table and an event log.

Everything is local. The browser talks to a Flask server running on `127.0.0.1` (your own machine) on port `3389` by default.

---

## Quick start (after installation)

From the folder containing `app.py`:

```bash
./start.sh
```

Then open **<http://127.0.0.1:3389>** in your browser. Press `Ctrl+C` in the terminal to stop the server.

If `start.sh` reports that the virtual environment is missing or broken, run the one-time setup:

```bash
SETUP=1 ./start.sh     # needs internet once
./start.sh             # from then on, fully offline
```

You can also start the app manually without any script:

```bash
.venv/bin/python -m flask --app app run --host 127.0.0.1 --port 3389 --no-debug
```

---

## First-time installation

### Option A — from a downloaded ZIP of the source code

1. Download the repository as a ZIP from GitHub: <https://github.com/1dvv3/Ticket_system>
2. Unzip it to a folder, e.g. `~/Applications/ticket-webapp`.
3. Open a terminal in that folder and run:
   ```bash
   SETUP=1 ./start.sh
   ```
   This installs Python 3.11 and the packages (Flask, reportlab) once. It needs internet.
4. Afterwards run `./start.sh` — no internet needed.

### Option B — using `install.sh`

`install.sh` downloads the app from GitHub into `~/Applications/ticket-webapp` (or a directory of your choice), sets up the environment, and starts the app:

```bash
curl -LsSf https://raw.githubusercontent.com/1dvv3/Ticket_system/main/install.sh | bash
```

Or, if you already have the script locally:

```bash
./install.sh
```

Custom install location:

```bash
TICKET_APP_DIR=~/my-tickets ./install.sh
```

Install without starting the server:

```bash
START_APP=0 ./install.sh
```

### What the installer checks

`install.sh` and `start.sh` deliberately fail loudly with an **exact fix command** and an **"Internet required: yes/no"** line for every error. Examples:

| Problem | Message includes |
|---|---|
| Missing `curl` / `tar` | Per-platform install command (`xcode-select --install`, `apt`, `pacman`) |
| `uv` not installed | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Broken venv | `SETUP=1 ./start.sh` and the three manual `uv` commands |
| Port in use | `PORT=4000 ./start.sh` |
| Missing app file | Command to re-download the ZIP |
| Download fails | Retry command and `TICKET_APP_ARCHIVE_URL` override |

Both scripts use `set -Eeuo pipefail` and trap unexpected errors with the line number.

---

## Updating an installed copy

This is the part that catches people out: **running the installer again normally does nothing** if the app folder already exists. You must explicitly ask for an update.

### Correct update command (from the repo's own `install.sh`)

```bash
curl -LsSf https://raw.githubusercontent.com/1dvv3/Ticket_system/main/install.sh | UPDATE=1 bash
```

If you used a custom install directory, include it:

```bash
curl -LsSf https://raw.githubusercontent.com/1dvv3/Ticket_system/main/install.sh \
  | TICKET_APP_DIR=/path/you/used UPDATE=1 bash
```

If the script is already local:

```bash
UPDATE=1 ./install.sh
```

**What `UPDATE=1` does:**
- Downloads the latest `main.tar.gz` from GitHub.
- Replaces all app files (`app.py`, `templates/`, scripts, fonts, background image).
- **Preserves `data.json`** (your students and scan history).
- **Preserves `.venv`** (no re-download of Python/packages needed).
- Skips Python/dependency installation if the venv is healthy.

**Important:** `UPDATE=1` must be set on `bash`, not on `curl`. `UPDATE=1 curl ... | bash` does **not** work because the variable only reaches `curl`, not the script.

### The gist installer

There is also an older installer published as a GitHub gist:

```bash
curl -LsSf https://gist.githubusercontent.com/1dvv3/29fad7d1ec6025e784735892406a6ff6/raw/install.sh | bash
```

To update with it:

```bash
curl -LsSf https://gist.githubusercontent.com/1dvv3/29fad7d1ec6025e784735892406a6ff6/raw/install.sh | UPDATE=1 bash
```

The gist does not have the richer error messages of the in-repo `install.sh`; the repo version is preferred.

---

## Offline behaviour — what needs internet and what does not

| Action | Internet? | Why |
|---|---|---|
| `curl ... \| bash` (install) | **Yes — once** | Downloads the script, Python, Flask, reportlab |
| `SETUP=1 ./start.sh` | **Yes — once** | Builds `.venv` and installs packages |
| `UPDATE=1 ./install.sh` | **Yes** | Downloads the latest app files |
| `./start.sh` (normal use) | **No** | Uses `.venv` with `UV_OFFLINE=1` |
| Uploading a CSV | No | Parsed locally in Python |
| Generating PDFs | No | reportlab is installed locally |
| Scanning / sign-out | No | Reads and writes `data.json` |
| Opening the web UI | No | Served from `127.0.0.1` |

`start.sh` launches Flask with `UV_OFFLINE=1`, so even `uv` cannot reach the network at runtime. A `curl: (6) Could not resolve host` error means the **install** command was run while offline — the app itself was never the problem.

---

## The four tabs

The web UI has four tabs across the top. Use the tab buttons to switch; no page reload is needed.

### 1. Generate Tickets

Purpose: load the student list, adjust how many tickets each student gets, and download the printable PDF.

- **Upload CSV** — choose a `.csv` file and click Upload. The student table below refreshes automatically.
- **Generate & Download PDF** — creates `Graduation_Tickets_2026.pdf` and downloads it.
- **Student Tickets Status table** columns:
  - `First Name` — all words of "Given Names" from the CSV
  - `Last Name` — the "Surname" from the CSV
  - `Student ID`
  - `Tickets` — a dropdown (0, 1, or 2). Changing it immediately updates that student's barcodes.
  - `Barcode 1` / `Barcode 2` — the assigned barcode, or "Not Assigned"
  - `Status` — Assigned / Unassigned

**Note:** reducing a student's ticket count removes the higher-numbered barcode and any entry scan attached to it. Increasing it regenerates the barcodes from the student ID.

### 2. Assign Barcodes (Barcode Lookup)

Purpose: check which student a barcode belongs to, e.g. when a ticket is brought to the desk.

- Enter one or both barcodes (scanning into field 1 then pressing Enter moves to field 2; pressing Enter on an empty field 2 submits a single-ticket lookup).
- Click **Lookup Barcodes**.
- The result table shows Ticket number, First Name, Last Name, Student ID, Barcode and Ticket #.
- A student with only one ticket shows the note **"(Only 1 ticket assigned)"**.
- If the two barcodes belong to different students, a red warning says **"Wrong pair of tickets"**.
- An empty scan field produces no error row; an unknown non-empty barcode shows **"No match found for: …"**.

### 3. Scan Entry

Purpose: validate tickets as students arrive at the venue.

- Scan/type a barcode and press Enter (or click **Validate Entry**).
- Outcomes:
  - **VALID – Welcome, `<name>`! (Ticket #n)** — green banner; the barcode is recorded in the entry log with a timestamp.
  - **INVALID – Already Used at `<time>`** — red banner; the ticket was already scanned.
  - **INVALID – Unknown Ticket** — red banner; the barcode does not exist.
- If the student has only one ticket, the result adds **"This student has only 1 ticket assigned"**.
- The input clears and refocuses after every scan for fast throughput.

### 4. Sign Out

Purpose: track students who leave the venue and come back, using the **same ticket**.

- Scan/type a barcode and press Enter (or click **Toggle Sign Out / In**):
  - First scan marks the student **OUT** (amber banner, e.g. *"Vhonn Allessandrius Acenas signed out at 23/11 22:59 (Ticket #1)"*).
  - Scanning the same barcode again marks them **IN** (green banner, *"signed back in"*).
  - Scanning a barcode that was **never used at entry** is rejected: **"INVALID – Ticket not used at entry"**.
  - Unknown tickets are rejected: **"INVALID – Unknown Ticket"**.
- Status is **per student**: with two tickets, either barcode toggles the same student state.
- Buttons:
  - **Clear Result** — clears the banner only; does not change data.
  - **Reset Tracking** — asks for confirmation, then clears all sign-out status and events (entry scans are kept).
- **Current Status table** — First Name, Last Name, Student ID, Status, Last Change. Status values:
  - `OUT` — red
  - `IN` — green
  - `NOT ENTERED` — grey (no barcode of theirs has been scanned at entry)
  - Sorted: **OUT → IN → NOT ENTERED**, then alphabetically by surname/first name.
- **Sign Out / Sign In Events table** — chronological log with Time, First/Last Name, Student ID, Ticket barcode (and ticket number), and Event (OUT/IN).

**Typical workflow:** a student's ticket is scanned at Entry → later scanned in Sign Out (OUT) → scanned again on return (IN). Staff can see at a glance who is currently outside.

---

## CSV format

The CSV must be a standard comma-separated file with a header row. The parser handles UTF-8 with or without BOM, CRLF or LF line endings, quoted fields, embedded commas, and escaped quotes.

**Required columns** (names are matched case-insensitively from the alias list):

| Meaning | Accepted header names |
|---|---|
| Surname | `Surname`, `surname`, `Last Name` |
| Given names | `Given Names`, `Given Name`, `First Name` |
| Student ID | `Student ID`, `student_id`, `ID` |

**Optional column:**

| Meaning | Accepted header names | Values |
|---|---|---|
| Ticket count | `Ticket Count`, `Tickets`, `ticket_count` | `0`, `1`, `2` (blank = 2) |

**Example:**

```csv
Surname,Given Names,Student ID,Ticket Count
Acenas,Vhonn Allessandrius,454893972,1
Aguilella,Mia Isabelle,444545526
Ahmadshahi,Mohammad Yahia,445097471,5
```

- All words in "Given Names" become the **First Name** (e.g. `Vhonn Allessandrius`); the surname becomes the **Last Name**.
- Rows with a blank Student ID are skipped.
- If a required column is missing, the upload fails with `CSV is missing required column(s): …`.
- Re-uploading a CSV keeps existing barcode assignments for students whose previous count was ≤ the new count. If the new count is lower, the extra barcodes and their entry scans are dropped.

---

## Ticket counts (0–2)

Each student can have 0, 1, or 2 tickets. This can be set from the CSV or changed live in the Generate Tickets table.

| Value | Effect |
|---|---|
| `2` (default) | Barcodes `<id>_1` and `<id>_2`; two tickets in the PDF |
| `1` | Only `<id>_1`; one ticket in the PDF; UI shows a one-ticket note |
| `0` | No barcodes; no tickets in the PDF; student cannot enter or sign out |

Rules applied by `parse_ticket_count()`:

| Input | Result |
|---|---|
| empty / missing column | 2 (no warning) |
| `0`, `1`, `2` (or `0.0`, `1.9` → truncated) | that value |
| negative (e.g. `-3`) | clamped to 0, warning |
| greater than 2 (e.g. `5`) | capped at 2, warning: *"has more than the maximum of 2 tickets (5) – automatically adjusted to 2"* |
| non-numeric (e.g. `abc`) | 2, warning: *"invalid ticket count 'abc' – defaulted to 2"* |

Warnings from a CSV upload are shown in the alert box and in the API response's `warnings` array.

---

## Barcodes

- Format: Code 128, generated by reportlab.
- Value: `<Student ID>_<ticket number>`, e.g. `454893972_1`.
- Barcodes are deterministic: changing a student's count regenerates the same values (not random).
- The human-readable barcode text is printed beside the vertical barcode on the ticket.
- The barcode is the **only** credential used at Entry, Lookup, and Sign Out.

---

## The PDF tickets

Generated by `POST /api/generate_tickets` and downloaded as `Graduation_Tickets_2026.pdf`.

| Setting | Value |
|---|---|
| Page | A4 landscape (297 × 210 mm) |
| Ticket size | 140 × 48 mm |
| Grid | 2 columns × 4 rows = 8 tickets per page |
| Gaps | 3 mm horizontal and vertical |
| Margins | Auto-calculated to centre the grid |
| Background | `ticket_bg.jpg` |
| Font | `Perandory.ttf` (with a faux-bold stroked effect for the name) |
| Barcode | Code 128, rotated 90°, `0.25 mm` bar width |

Printed fields: event date (`24 September 2026 at 5:00 PM`), location (`Rosehill Gardens`), full student name, barcode image and barcode text.

**To edit these values:** see the clearly commented "LAYOUT CONFIGURATION", "TEXT POSITIONING" and "BARCODE POSITIONING" blocks in `app.py` (`generate_tickets()`). Event date and location are plain strings in that function.

Students with `ticket_count = 0` produce no tickets; count 1 produces one ticket; count 2 produces two.

---

## Data storage: `data.json`

All state is in one JSON file in the app folder. It is created automatically on the first upload/scan; before that, the app treats it as empty. **It is intentionally not committed to git** because it contains real student names and IDs.

Top-level structure:

```json
{
  "students": [
    {
      "id": "454893972",
      "name": "Vhonn Allessandrius Acenas",
      "first_name": "Vhonn Allessandrius",
      "last_name": "Acenas",
      "barcode1": "454893972_1",
      "barcode2": "454893972_2",
      "ticket_count": 2,
      "assigned": true
    }
  ],
  "scan_log": {
    "454893972_1": "23/11 19:01"
  },
  "signout_status": {
    "454893972": { "state": "OUT", "since": "23/11 22:35" }
  },
  "signout_log": [
    {
      "time": "23/11 22:35",
      "event": "OUT",
      "student_id": "454893972",
      "name": "Vhonn Allessandrius Acenas",
      "first_name": "Vhonn Allessandrius",
      "last_name": "Acenas",
      "barcode": "454893972_1",
      "ticket_num": 1
    }
  ]
}
```

- `scan_log` — entry scans: `barcode → "DD/MM HH:MM"`. A barcode in this map has been used at entry.
- `signout_status` — current OUT/IN state per student ID, with the time of the last toggle.
- `signout_log` — append-only history of every sign-out/sign-in event (includes a name snapshot so history survives a CSV re-upload).

Timestamps are local machine time with minute resolution (`datetime.now().strftime("%d/%m %H:%M")`). When the app loads an older `data.json` that lacks the newer keys, it adds empty defaults in memory; they are written to disk on the next save.

**Backups:** copy `data.json` to a safe place regularly, especially before re-uploading a CSV or updating the app. Updating via `UPDATE=1` preserves it, but a fresh install into a new directory starts empty.

---

## API reference

All API calls are to the same host/port as the UI. JSON bodies are sent with `Content-Type: application/json` unless noted.

| Method | Endpoint | Purpose / body | Response highlights |
|---|---|---|---|
| GET | `/` | Web UI | HTML page |
| GET | `/api/students` | All students | `{students: [...]}` |
| POST | `/api/load_csv` | Multipart form field `file` | `{message, warnings, count}`; 400 on missing columns |
| POST | `/api/generate_tickets` | — | PDF file (`Graduation_Tickets_2026.pdf`); 400 if no assigned students |
| POST | `/api/assign` | `{student_id}` | `{success, barcode1, barcode2, ticket_count}`; 404 if not found |
| POST | `/api/ticket_count` | `{student_id, ticket_count}` | `{success, ticket_count, warning}`; 404 if not found |
| POST | `/api/bulk_assign` | — | `{success, assigned}` |
| POST | `/api/scan` | `{barcode}` | `{valid, message, name, first_name, last_name, ticket_count}` — entry validation |
| POST | `/api/lookup_barcodes` | `{barcode1, barcode2}` (one may be empty) | `{barcode1, barcode2, error}`; 400 if both empty |
| POST | `/api/signout` | `{barcode}` | `{success, event, state, since, time, message, ...}`; 400 if empty barcode |
| GET | `/api/signout/status` | — | `{students: [{id, first_name, last_name, state, entry_time, last_change, ...}], events: [...]}` |
| POST | `/api/signout/reset` | `{confirm: true}` | `{success: true}`; 400 without confirmation |

All state-changing endpoints read `data.json`, modify it, and write it back. Sign-out mutations are protected by a thread lock within the single Flask process.

**Example with curl:**

```bash
# Validate a ticket at entry
curl -s -X POST http://127.0.0.1:3389/api/scan \
  -H 'Content-Type: application/json' -d '{"barcode":"454893972_1"}'

# Sign the same student out, then back in
curl -s -X POST http://127.0.0.1:3389/api/signout \
  -H 'Content-Type: application/json' -d '{"barcode":"454893972_1"}'
curl -s -X POST http://127.0.0.1:3389/api/signout \
  -H 'Content-Type: application/json' -d '{"barcode":"454893972_1"}'

# Current status
curl -s http://127.0.0.1:3389/api/signout/status
```

---

## Scripts: `start.sh` and `install.sh`

Both scripts are executable bash scripts (`#!/usr/bin/env bash`) with `set -Eeuo pipefail` and consistent error reporting. They work on macOS and Linux.

### `start.sh` — daily offline launcher

| Invocation | Meaning |
|---|---|
| `./start.sh` | Start the app fully offline (default port 3389) |
| `SETUP=1 ./start.sh` | Build the venv first (internet once), then start |
| `START_APP=0 ./start.sh` | Only run the checks; print the manual start command |
| `PORT=4000 ./start.sh` | Use a different port |
| `HOST=0.0.0.0 ./start.sh` | Bind to all interfaces (**not recommended** without a firewall) |
| `PYTHON_VERSION=3.12 ./start.sh` | Use a different Python version during setup |

Behaviour:
- Resolves its own directory, so it works from any working directory.
- Verifies `app.py`, `requirements.txt`, `templates/index.html`, `fonts/Perandory.ttf`, `ticket_bg.jpg`.
- Checks that `.venv/bin/python` can import `flask` and `reportlab`.
- If healthy: starts `env UV_OFFLINE=1 .venv/bin/python -m flask --app app run --host 127.0.0.1 --port 3389 --no-debug`.
- If not healthy and `SETUP≠1`: prints the exact repair commands and exits with an error.
- If not healthy and `SETUP=1`: installs Python via uv, creates the venv, installs requirements, verifies imports.
- Checks the port with `lsof` if available and suggests `PORT=4000` when busy.

### `install.sh` — first-time installer / updater

| Invocation | Meaning |
|---|---|
| `./install.sh` | Install into `~/Applications/ticket-webapp` and start |
| `TICKET_APP_DIR=~/my-tickets ./install.sh` | Install into a custom folder |
| `UPDATE=1 ./install.sh` | Refresh app files, preserving `data.json` and `.venv` |
| `START_APP=0 ./install.sh` | Install/check but do not start |
| `TICKET_APP_ARCHIVE_URL=file:///path/app.tar.gz ./install.sh` | Install from a local archive (offline) |

Behaviour:
- Checks for `curl` and `tar`; installs `uv` if missing.
- Downloads `main.tar.gz` from GitHub (one-time internet) and validates the archive contents (including `start.sh`).
- Fresh install: refuses to overwrite a non-empty directory unless `UPDATE=1`.
- Update: backs up `data.json` and `.venv`, replaces app files, restores the backups.
- Creates/validates `requirements.txt`, sets up the venv, verifies Flask and reportlab.
- On launch, waits up to 15 seconds for the server, then opens the browser (`open` on macOS, `xdg-open` on Linux) or prints the URL.

---

## Configuration reference

### Environment variables (scripts)

| Variable | Default | Used by | Meaning |
|---|---|---|---|
| `HOST` | `127.0.0.1` | both | Address Flask binds to |
| `PORT` | `3389` | both | Port Flask listens on |
| `START_APP` | `1` | both | `0` = check only, don't start |
| `SETUP` | `0` | `start.sh` | `1` = run one-time venv setup |
| `PYTHON_VERSION` | `3.11` | both | Python version installed by uv |
| `TICKET_APP_DIR` | `~/Applications/ticket-webapp` | `install.sh` | Install destination |
| `UPDATE` | `0` | `install.sh` | `1` = refresh existing install |
| `TICKET_APP_ARCHIVE_URL` | GitHub `main.tar.gz` | `install.sh` | Override the source archive URL |

### Hard-coded values in `app.py` (edit the source to change)

| Setting | Where | Default |
|---|---|---|
| `DATA_FILE` | top of file | `data.json` |
| `MAX_TICKETS` / `DEFAULT_TICKET_COUNT` | top of file | `2` / `2` |
| Dev server port | `if __name__ == "__main__"` | `5000` (only when running `python app.py` directly) |
| Event date | `generate_tickets()` | `24 September 2026 at 5:00 PM` |
| Venue | `generate_tickets()` | `Rosehill Gardens` |
| PDF output filename | `generate_tickets()` | `Graduation_Tickets_2026.pdf` |
| Ticket/page dimensions, gaps, positions | `generate_tickets()` | see [The PDF tickets](#the-pdf-tickets) |

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `curl: (6) Could not resolve host` | Internet was off during **install**. Reconnect and re-run the install command. Running the app itself never needs internet. |
| `App directory already exists — skipping download` | Normal re-run without `UPDATE=1`. Use `UPDATE=1 ./install.sh` to refresh. |
| "UPDATE=1 didn't work" | The variable was set on `curl`, not `bash`. Use `curl ... \| UPDATE=1 bash`. |
| `uv is not installed` | Run `curl -LsSf https://astral.sh/uv/install.sh \| sh`, then `SETUP=1 ./start.sh` (internet once). |
| `virtual environment is missing or broken` | Run `SETUP=1 ./start.sh`. Manual equivalent: `uv python install 3.11`, `uv venv --python 3.11 .venv`, `uv pip install --python .venv/bin/python -r requirements.txt`. |
| `port 3389 is already in use` | Use `PORT=4000 ./start.sh`, or stop the process using the port. |
| Missing file error on startup | Re-download the source ZIP; the script prints the exact command. |
| `No assigned students. Assign barcodes first.` | Upload a CSV first (Generate Tickets tab). |
| `CSV is missing required column(s)` | Check the CSV header — see [CSV format](#csv-format). |
| Ticket rejected as "Already Used" | That barcode was already scanned at Entry; each ticket works once. |
| "Ticket not used at entry" on Sign Out | The exact barcode scanned must first be validated in the Scan Entry tab. |
| Student shows NOT ENTERED | None of their barcodes appear in `scan_log` yet. |
| Names display as one string | Old `data.json` entries are split on the last space when loaded (e.g. "Vhonn Allessandrius Acenas" → "Vhonn Allessandrius" / "Acenas"). Re-uploading the CSV stores the split fields explicitly. |
| Data disappeared after a fresh install | A fresh install uses a new empty `data.json`. Restore your backup, or use `UPDATE=1` which preserves it. |

---

## Development

Run directly from the repo (uses port **5000**, debug mode on):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open <http://127.0.0.1:5000>. The debug reloader picks up changes to `app.py` and templates automatically.

Loose files not committed to git:

- `data.json` — live student data and logs (contains personal information)
- `Testing data set.csv` — sample class list used during development

API smoke test:

```bash
curl -s http://127.0.0.1:5000/api/students
curl -s http://127.0.0.1:5000/api/signout/status
```

---

## File map

| File | Purpose |
|---|---|
| `app.py` | Flask app: data helpers, CSV parsing, PDF generation, all API endpoints |
| `templates/index.html` | Entire web UI (HTML/CSS/vanilla JS), four tabs |
| `requirements.txt` | Python dependencies: Flask 3.x, reportlab 4.x |
| `fonts/Perandory.ttf` | Font used for ticket text in the PDF |
| `fonts/Perandory Cond.ttf` | Additional font asset |
| `ticket_bg.jpg` | Background image printed on each ticket |
| `start.sh` | Daily launcher (offline once the venv exists) |
| `install.sh` | First-time installer / updater |
| `data.json` | Runtime state (untracked): students, entry scans, sign-out status and history |
| `Testing data set.csv` | Sample CSV used during development (untracked) |

---

**Repository:** <https://github.com/1dvv3/Ticket_system> — branch `ticket-count-field` contains all current features.
