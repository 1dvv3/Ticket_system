import csv
import io
import json
import os
import threading
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file
from reportlab.graphics.barcode import code128
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

app = Flask(__name__)

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
# Register Perandory Regular
reg_font = os.path.join(FONT_DIR, "Perandory.ttf")
if os.path.exists(reg_font):
    pdfmetrics.registerFont(TTFont("Perandory", reg_font))
DATA_FILE = "data.json"
DARK_TEXT = HexColor("#333333")


def draw_stroked_string(pdf_canvas, x, y, text, stroke_width=0.42, char_space=0.67):
    pdf_canvas.saveState()
    pdf_canvas.setStrokeColor(DARK_TEXT)
    pdf_canvas.setFillColor(DARK_TEXT)
    pdf_canvas.setLineWidth(stroke_width)

    text_object = pdf_canvas.beginText(x, y)
    text_object.setTextRenderMode(
        2
    )  # Fill and stroke text for a true faux-bold PDF render.
    text_object.setCharSpace(char_space)
    text_object.textOut(text)
    pdf_canvas.drawText(text_object)
    pdf_canvas.restoreState()


MAX_TICKETS = 2
DEFAULT_TICKET_COUNT = 2
_signout_lock = threading.Lock()


def name_parts(student):
    """Return (first_name, last_name); legacy records split on the last space."""
    if student.get("first_name") is not None or student.get("last_name") is not None:
        return student.get("first_name") or "", student.get("last_name") or ""
    full = (student.get("name") or "").strip()
    first, sep, last = full.rpartition(" ")
    return (first, last) if sep else (full, "")


def normalize_student(student):
    """Ensure every student exposes split name fields (legacy data compatibility)."""
    first, last = name_parts(student)
    student["first_name"] = first
    student["last_name"] = last
    if not (student.get("name") or "").strip():
        student["name"] = " ".join(part for part in (first, last) if part)
    return student


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        for student in data.get("students", []):
            normalize_student(student)
    else:
        data = {"students": []}
    data.setdefault("scan_log", {})
    data.setdefault("signout_status", {})
    data.setdefault("signout_log", [])
    return data


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def parse_ticket_count(value):
    """Return a ticket count clamped to 0..MAX_TICKETS, and a warning if clamped."""
    text = (value or "").strip()
    if not text:
        return DEFAULT_TICKET_COUNT, None
    try:
        count = int(float(text))
    except ValueError:
        return DEFAULT_TICKET_COUNT, f"invalid ticket count '{text}' - defaulted to {DEFAULT_TICKET_COUNT}"

    if count < 0:
        return 0, f"ticket count {count} - adjusted to the minimum of 0"
    if count > MAX_TICKETS:
        return MAX_TICKETS, (
            f"has more than the maximum of {MAX_TICKETS} tickets "
            f"({count}) - automatically adjusted to {MAX_TICKETS}"
        )
    return count, None


def ticket_count_of(student):
    count = student.get("ticket_count")
    if count is None:
        return sum(1 for key in ("barcode1", "barcode2") if student.get(key))
    try:
        return max(0, min(MAX_TICKETS, int(count)))
    except (TypeError, ValueError):
        return 0


def barcodes_of(student):
    return [student[key] for key in ("barcode1", "barcode2") if student.get(key)]


def set_ticket_count(student, count):
    """Assign or remove barcodes so the student has exactly `count` of them."""
    student["assigned"] = True
    student["ticket_count"] = count
    for num in range(1, MAX_TICKETS + 1):
        key = f"barcode{num}"
        if num <= count:
            student[key] = f"{student['id']}_{num}"
        else:
            student[key] = None


def find_student_by_barcode(data, barcode):
    for student in data["students"]:
        for num, student_barcode in enumerate(barcodes_of(student), start=1):
            if student_barcode == barcode:
                return student, num
    return None, None


# ── Sign out / sign in helpers ────────────────────────────────

def entry_time_of(data, barcode):
    """Entry time recorded by /api/scan for this exact barcode, or None."""
    return data.get("scan_log", {}).get(barcode)


def student_entry_time(data, student):
    """First entry time among the student's barcodes, or None."""
    for barcode in barcodes_of(student):
        when = entry_time_of(data, barcode)
        if when:
            return when
    return None


def student_signout_state(data, student):
    """Return (state, last_change) for a student: OUT / IN / NOT ENTERED."""
    entry = student_entry_time(data, student)
    if entry is None:
        return "NOT ENTERED", None
    record = data.get("signout_status", {}).get(student["id"])
    if record and record.get("state") == "OUT":
        return "OUT", record.get("since") or entry
    if record and record.get("state") == "IN":
        return "IN", record.get("since") or entry
    return "IN", entry


def reconcile_signout_data(data):
    """Drop active sign-out state when a student no longer has entry evidence."""
    valid_ids = {
        student["id"]
        for student in data.get("students", [])
        if student_entry_time(data, student) is not None
    }
    status = data.get("signout_status", {})
    for student_id in list(status):
        if student_id not in valid_ids:
            del status[student_id]
    data["signout_status"] = status


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/students", methods=["GET"])
def get_students():
    data = load_data()
    return jsonify({"students": data["students"]})


@app.route("/api/load_csv", methods=["POST"])
def load_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    data = load_data()
    existing = {s["id"]: s for s in data["students"]}

    students = []
    warnings = []
    try:
        stream = file.stream.read().decode("utf-8-sig")
        csv_reader = csv.DictReader(stream.splitlines())
        if csv_reader.fieldnames is None:
            return jsonify({"error": "CSV is empty"}), 400

        def column(names):
            for name in names:
                if name in csv_reader.fieldnames:
                    return name
            return None

        surname_col = column(["Surname", "surname", "Last Name"])
        given_col = column(["Given Names", "Given Name", "First Name"])
        id_col = column(["Student ID", "student_id", "ID"])
        count_col = column(["Ticket Count", "Tickets", "ticket_count"])

        missing = [
            name
            for name, found in (
                ("Surname", surname_col),
                ("Given Names", given_col),
                ("Student ID", id_col),
            )
            if not found
        ]
        if missing:
            return jsonify(
                {"error": f"CSV is missing required column(s): {', '.join(missing)}"}
            ), 400

        for row in csv_reader:
            student_id = (row.get(id_col) or "").strip()
            if not student_id:
                continue
            first_name = (row.get(given_col) or "").strip()
            last_name = (row.get(surname_col) or "").strip()
            name = f"{first_name} {last_name}".strip()
            count, warning = parse_ticket_count(
                (row.get(count_col) or "") if count_col else ""
            )
            if warning:
                warnings.append(f"{name} ({student_id}) {warning}")

            # Reuse the barcode assignment from an existing student with the same ID.
            old = existing.get(student_id)
            previous_count = None
            if old is not None:
                if "ticket_count" in old:
                    previous_count = ticket_count_of(old)
                elif old.get("assigned"):
                    previous_count = sum(
                        1 for key in ("barcode1", "barcode2") if old.get(key)
                    )

            student = {
                "id": student_id,
                "name": name,
                "first_name": first_name,
                "last_name": last_name,
                "barcode1": None,
                "barcode2": None,
                "ticket_count": count,
                "assigned": False,
            }
            if previous_count is not None and previous_count <= count:
                keep = min(previous_count, count)
                for num in range(1, keep + 1):
                    student[f"barcode{num}"] = old.get(f"barcode{num}")
                student["assigned"] = True
            students.append(student)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    assigned_count = 0
    for stu in students:
        if not stu["assigned"]:
            set_ticket_count(stu, stu["ticket_count"])
            assigned_count += 1

    data["students"] = students
    reconcile_signout_data(data)
    save_data(data)
    message = f"CSV loaded successfully. Assigned {assigned_count} students."
    if warnings:
        message += " " + " ".join(warnings)
    return jsonify(
        {
            "message": message,
            "warnings": warnings,
            "count": len(students),
        }
    )


@app.route("/api/generate_tickets", methods=["POST"])
def generate_tickets():
    data = load_data()
    tickets = []
    for stu in data["students"]:
        if stu["assigned"]:
            for ticket_num, barcode in enumerate(barcodes_of(stu), start=1):
                tickets.append(
                    {
                        "student_id": stu["id"],
                        "name": stu["name"],
                        "barcode": barcode,
                        "ticket_num": ticket_num,
                    }
                )

    if not tickets:
        return jsonify({"error": "No assigned students. Assign barcodes first."}), 400

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    # === LAYOUT CONFIGURATION (edit these values) ===
    PAGE_W, PAGE_H = 297 * mm, 210 * mm  # A4 landscape

    # Ticket dimensions (edit these)
    TICKET_W = 140 * mm  # Ticket width
    TICKET_H = 48 * mm  # Ticket height

    # Grid: 2 columns x 4 rows = 8 tickets per page
    COLS, ROWS = 2, 4

    # Gaps between tickets (edit these)
    GAP_X = 3 * mm  # Horizontal gap between columns
    GAP_Y = 3 * mm  # Vertical gap between rows

    # Page margins (auto-calculated to center the grid)
    MARGIN_X = (PAGE_W - (COLS * TICKET_W + (COLS - 1) * GAP_X)) / 2
    MARGIN_Y = (PAGE_H - (ROWS * TICKET_H + (ROWS - 1) * GAP_Y)) / 2

    bg_path = os.path.join(os.path.dirname(__file__), "ticket_bg.jpg")

    ticket_count = 0
    for i, ticket in enumerate(tickets):
        col = i % COLS
        row = (i // COLS) % ROWS  # Reset row after each page

        # New page after every 8 tickets (2x4 grid)
        if ticket_count > 0 and ticket_count % (COLS * ROWS) == 0:
            c.showPage()

        # Calculate ticket position (bottom-left origin)
        ticket_x = MARGIN_X + col * (TICKET_W + GAP_X)
        ticket_y = PAGE_H - MARGIN_Y - TICKET_H - row * (TICKET_H + GAP_Y)

        # Draw background image
        if os.path.exists(bg_path):
            c.drawImage(
                bg_path,
                ticket_x,
                ticket_y,
                width=TICKET_W,
                height=TICKET_H,
                preserveAspectRatio=True,
                mask="auto",
            )

        # === TEXT POSITIONING (edit these values - all in pixels, relative to ticket) ===
        px = 0.264583 * mm  # 1px in mm (96 DPI)

        # DATE field - edit top/left position here
        c.setFont("Perandory", 14)
        c.setFillColor(DARK_TEXT)
        date_top = 110  # px from top of ticket
        date_left = 155  # px from left of ticket
        c.drawString(
            ticket_x + date_left * px,
            ticket_y + TICKET_H - date_top * px,
            "24 September 2026 at 5:00 PM",
        )

        # LOCATION field - edit top/left position here
        loc_top = 130
        loc_left = 155
        c.drawString(
            ticket_x + loc_left * px,
            ticket_y + TICKET_H - loc_top * px,
            "Rosehill Gardens",
        )

        # NAME field - edit top/left position here
        c.setFont("Perandory", 10)
        name_top = 160
        name_left = 155
        draw_stroked_string(
            c,
            ticket_x + name_left * px,
            ticket_y + TICKET_H - name_top * px,
            ticket["name"],
        )

        # === BARCODE POSITIONING (edit these values) ===
        # Barcode is drawn sideways (rotated 90 degrees clockwise)
        barcode = code128.Code128(
            ticket["barcode"], barWidth=0.25 * mm, barHeight=42 * px
        )
        c.saveState()
        # Position: right=10px from ticket right edge, vertically centered
        barcode_right = 80  # px from right edge
        barcode_center_y = ticket_y + TICKET_H / 1.55
        c.translate(ticket_x + TICKET_W - barcode_right * px, barcode_center_y)
        c.rotate(-90)  # Rotate to make barcode vertical
        barcode.drawOn(c, -110 * px / 2, 6.7)  # 110px = barcode width, centered
        # Draw barcode number text to the right of the barcode
        c.setFont("Helvetica", 8)
        c.rotate(180)
        c.drawString(-5.5 + -50 * px, -67 * px, ticket["barcode"])
        c.restoreState()

        ticket_count += 1

    c.save()
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Graduation_Tickets_2026.pdf",
    )


@app.route("/api/assign", methods=["POST"])
def assign_barcode():
    req = request.json
    student_id = req.get("student_id")
    data = load_data()

    for stu in data["students"]:
        if stu["id"] == student_id:
            set_ticket_count(stu, ticket_count_of(stu))
            save_data(data)
            return jsonify(
                {
                    "success": True,
                    "barcode1": stu["barcode1"],
                    "barcode2": stu["barcode2"],
                    "ticket_count": ticket_count_of(stu),
                }
            )

    return jsonify({"success": False, "error": "Student not found"}), 404


@app.route("/api/ticket_count", methods=["POST"])
def update_ticket_count():
    req = request.json or {}
    student_id = req.get("student_id")
    data = load_data()

    for stu in data["students"]:
        if stu["id"] == student_id:
            count, warning = parse_ticket_count(str(req.get("ticket_count", "")))
            set_ticket_count(stu, count)
            reconcile_signout_data(data)
            save_data(data)
            return jsonify(
                {
                    "success": True,
                    "ticket_count": count,
                    "warning": warning,
                }
            )

    return jsonify({"success": False, "error": "Student not found"}), 404


@app.route("/api/bulk_assign", methods=["POST"])
def bulk_assign():
    data = load_data()
    assigned_count = 0
    for stu in data["students"]:
        if not stu["assigned"]:
            set_ticket_count(stu, ticket_count_of(stu))
            assigned_count += 1
    save_data(data)
    return jsonify({"success": True, "assigned": assigned_count})


@app.route("/api/scan", methods=["POST"])
def scan_barcode():
    req = request.json
    barcode = req.get("barcode", "").strip()
    data = load_data()

    student, ticket_num = find_student_by_barcode(data, barcode)

    if not student:
        return jsonify({"valid": False, "message": "INVALID - Unknown Ticket"})

    first_name, last_name = name_parts(student)
    count = ticket_count_of(student)
    scan_log = data.get("scan_log", {})
    if barcode in scan_log:
        return jsonify(
            {
                "valid": False,
                "message": f"INVALID - Already Used at {scan_log[barcode]}",
                "name": student["name"],
                "first_name": first_name,
                "last_name": last_name,
                "ticket_count": count,
            }
        )

    scan_log[barcode] = datetime.now().strftime("%d/%m %H:%M")
    data["scan_log"] = scan_log
    save_data(data)

    return jsonify(
        {
            "valid": True,
            "message": f"VALID - Welcome, {student['name']}! (Ticket #{ticket_num})",
            "name": student["name"],
            "first_name": first_name,
            "last_name": last_name,
            "ticket_count": count,
        }
    )


@app.route("/api/signout", methods=["POST"])
def signout_barcode():
    """Toggle a student's OUT/IN status using the same ticket barcode."""
    req = request.json or {}
    barcode = (req.get("barcode") or "").strip()
    if not barcode:
        return jsonify({"success": False, "error": "Please scan a ticket"}), 400

    with _signout_lock:
        data = load_data()
        student, ticket_num = find_student_by_barcode(data, barcode)
        if student is None:
            return jsonify(
                {"success": False, "error": "INVALID - Unknown Ticket"}
            )

        entry_time = entry_time_of(data, barcode)
        if entry_time is None:
            return jsonify(
                {"success": False, "error": "INVALID - Ticket not used at entry"}
            )

        now = datetime.now().strftime("%d/%m %H:%M")
        status = data.setdefault("signout_status", {})
        previous = status.get(student["id"], {}).get("state")
        event = "IN" if previous == "OUT" else "OUT"
        status[student["id"]] = {"state": event, "since": now}

        first_name, last_name = name_parts(student)
        data.setdefault("signout_log", []).append(
            {
                "time": now,
                "event": event,
                "student_id": student["id"],
                "name": student["name"],
                "first_name": first_name,
                "last_name": last_name,
                "barcode": barcode,
                "ticket_num": ticket_num,
            }
        )
        save_data(data)

    label = "signed out" if event == "OUT" else "signed back in"
    return jsonify(
        {
            "success": True,
            "event": event,
            "state": event,
            "since": now,
            "time": now,
            "message": f"{student['name']} {label} at {now}",
            "name": student["name"],
            "first_name": first_name,
            "last_name": last_name,
            "student_id": student["id"],
            "barcode": barcode,
            "ticket_num": ticket_num,
            "entry_time": entry_time,
            "ticket_count": ticket_count_of(student),
        }
    )


@app.route("/api/signout/status", methods=["GET"])
def signout_status():
    data = load_data()
    rows = []
    for student in data.get("students", []):
        first_name, last_name = name_parts(student)
        state, last_change = student_signout_state(data, student)
        record = data.get("signout_status", {}).get(student["id"], {})
        rows.append(
            {
                "id": student["id"],
                "name": student["name"],
                "first_name": first_name,
                "last_name": last_name,
                "state": state,
                "since": record.get("since"),
                "entry_time": student_entry_time(data, student),
                "last_change": last_change,
            }
        )
    return jsonify({"students": rows, "events": data.get("signout_log", [])})


@app.route("/api/signout/reset", methods=["POST"])
def reset_signout():
    req = request.json or {}
    if req.get("confirm") is not True:
        return jsonify({"success": False, "error": "Confirmation required"}), 400
    with _signout_lock:
        data = load_data()
        data["signout_status"] = {}
        data["signout_log"] = []
        save_data(data)
    return jsonify({"success": True})


@app.route("/api/lookup_barcodes", methods=["POST"])
def lookup_barcodes():
    req = request.json
    barcode1 = (req.get("barcode1") or "").strip()
    barcode2 = (req.get("barcode2") or "").strip()
    if not barcode1 and not barcode2:
        return jsonify({"error": "Please scan at least one ticket"}), 400
    data = load_data()

    result = {"barcode1": None, "barcode2": None, "error": None}

    for key, barcode in (("barcode1", barcode1), ("barcode2", barcode2)):
        if not barcode:
            continue
        student, ticket_num = find_student_by_barcode(data, barcode)
        if student is None:
            continue
        first_name, last_name = name_parts(student)
        result[key] = {
            "name": student["name"],
            "first_name": first_name,
            "last_name": last_name,
            "student_id": student["id"],
            "barcode": barcode,
            "ticket_num": ticket_num,
            "ticket_count": ticket_count_of(student),
        }

    # Check if both barcodes belong to the same student
    if result["barcode1"] and result["barcode2"]:
        if result["barcode1"]["student_id"] != result["barcode2"]["student_id"]:
            result["error"] = (
                "Wrong pair of tickets - barcodes belong to different students"
            )

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
