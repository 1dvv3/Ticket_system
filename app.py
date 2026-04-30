from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import csv
import io
from datetime import datetime
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.graphics.barcode import code128

app = Flask(__name__)
DATA_FILE = 'data.json'
DARK_TEXT = HexColor('#333333')

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"students": [], "scan_log": {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/students', methods=['GET'])
def get_students():
    data = load_data()
    return jsonify({"students": data["students"]})

@app.route('/api/load_csv', methods=['POST'])
def load_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    data = load_data()
    existing = {s["id"]: s for s in data["students"]}

    students = []
    try:
        stream = file.stream.read().decode("UTF-8")
        csv_reader = csv.reader(stream.splitlines())
        next(csv_reader, None)
        for row in csv_reader:
            if len(row) >= 3:
                student_id = row[2].strip()
                student = {
                    "id": student_id,
                    "name": f"{row[1].strip()} {row[0].strip()}",
                    "barcode1": None,
                    "barcode2": None,
                    "assigned": False
                }
                if student_id in existing and existing[student_id]["assigned"]:
                    student["barcode1"] = existing[student_id]["barcode1"]
                    student["barcode2"] = existing[student_id]["barcode2"]
                    student["assigned"] = True
                students.append(student)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    assigned_count = 0
    for stu in students:
        if not stu["assigned"]:
            stu["barcode1"] = f"{stu['id']}_1"
            stu["barcode2"] = f"{stu['id']}_2"
            stu["assigned"] = True
            assigned_count += 1

    data["students"] = students
    save_data(data)
    return jsonify({"message": f"CSV loaded successfully. Assigned {assigned_count} barcodes.", "count": len(students)})

@app.route('/api/generate_tickets', methods=['POST'])
def generate_tickets():
    data = load_data()
    tickets = []
    for stu in data["students"]:
        if stu["assigned"]:
            tickets.append({
                "student_id": stu["id"],
                "name": stu["name"],
                "barcode": stu["barcode1"],
                "ticket_num": 1
            })
            tickets.append({
                "student_id": stu["id"],
                "name": stu["name"],
                "barcode": stu["barcode2"],
                "ticket_num": 2
            })

    if not tickets:
        return jsonify({"error": "No assigned students. Assign barcodes first."}), 400

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    # === LAYOUT CONFIGURATION (edit these values) ===
    PAGE_W, PAGE_H = 297*mm, 210*mm  # A4 landscape

    # Ticket dimensions (edit these)
    TICKET_W = 138*mm   # Ticket width
    TICKET_H = 46*mm    # Ticket height

    # Grid: 2 columns x 4 rows = 8 tickets per page
    COLS, ROWS = 2, 4

    # Gaps between tickets (edit these)
    GAP_X = 5*mm   # Horizontal gap between columns
    GAP_Y = 5*mm   # Vertical gap between rows

    # Page margins (auto-calculated to center the grid)
    MARGIN_X = (PAGE_W - (COLS * TICKET_W + (COLS-1) * GAP_X)) / 2
    MARGIN_Y = (PAGE_H - (ROWS * TICKET_H + (ROWS-1) * GAP_Y)) / 2

    bg_path = os.path.join(os.path.dirname(__file__), 'ticket_bg.jpg')

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
            c.drawImage(bg_path, ticket_x, ticket_y, width=TICKET_W, height=TICKET_H, preserveAspectRatio=True, mask='auto')

        # === TEXT POSITIONING (edit these values - all in pixels, relative to ticket) ===
        px = 0.264583 * mm  # 1px in mm (96 DPI)

        # DATE field - edit top/left position here
        c.setFont("Helvetica", 9)
        c.setFillColor(DARK_TEXT)
        date_top = 105   # px from top of ticket
        date_left = 155   # px from left of ticket
        c.drawString(ticket_x + date_left*px, ticket_y + TICKET_H - date_top*px, "24 September 2026")

        # TIME field - edit top/left position here
        time_top = 123
        time_left = 155
        c.drawString(ticket_x + time_left*px, ticket_y + TICKET_H - time_top*px, "5:00 PM")

        # LOCATION field - edit top/left position here
        loc_top = 141
        loc_left = 155
        c.drawString(ticket_x + loc_left*px, ticket_y + TICKET_H - loc_top*px, "Rose Hill Gardens")

        # NAME field - edit top/left position here
        c.setFont("Helvetica-Bold", 12)
        name_top = 159
        name_left = 155
        c.drawString(ticket_x + name_left*px, ticket_y + TICKET_H - name_top*px, ticket["name"])

        # === BARCODE POSITIONING (edit these values) ===
        # Barcode is drawn sideways (rotated 90 degrees clockwise)
        barcode = code128.Code128(ticket["barcode"], barWidth=0.25*mm, barHeight=42*px)
        c.saveState()
        # Position: right=10px from ticket right edge, vertically centered
        barcode_right =80   # px from right edge
        barcode_center_y = ticket_y + TICKET_H / 1.55
        c.translate(ticket_x + TICKET_W - barcode_right*px, barcode_center_y)
        c.rotate(-90)  # Rotate to make barcode vertical
        barcode.drawOn(c, -110*px/2, 6.7)  # 110px = barcode width, centered
        # Draw barcode number text to the right of the barcode
        c.setFont("Helvetica", 8)
        c.rotate(180)
        c.drawString(-5.5 + -50*px, -67*px, ticket["barcode"])
        c.restoreState()


        ticket_count += 1

    c.save()
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name='Graduation_Tickets_2026.pdf')

@app.route('/api/assign', methods=['POST'])
def assign_barcode():
    req = request.json
    student_id = req.get('student_id')
    data = load_data()

    for stu in data["students"]:
        if stu["id"] == student_id:
            stu["barcode1"] = f"{student_id}_1"
            stu["barcode2"] = f"{student_id}_2"
            stu["assigned"] = True
            save_data(data)
            return jsonify({"success": True, "barcode1": stu["barcode1"], "barcode2": stu["barcode2"]})

    return jsonify({"success": False, "error": "Student not found"}), 404

@app.route('/api/bulk_assign', methods=['POST'])
def bulk_assign():
    data = load_data()
    assigned_count = 0
    for stu in data["students"]:
        if not stu["assigned"]:
            stu["barcode1"] = f"{stu['id']}_1"
            stu["barcode2"] = f"{stu['id']}_2"
            stu["assigned"] = True
            assigned_count += 1
    save_data(data)
    return jsonify({"success": True, "assigned": assigned_count})

@app.route('/api/scan', methods=['POST'])
def scan_barcode():
    req = request.json
    barcode = req.get('barcode', '').strip()
    data = load_data()

    student = None
    ticket_num = None
    for stu in data["students"]:
        if stu["barcode1"] == barcode:
            student, ticket_num = stu, 1
            break
        elif stu["barcode2"] == barcode:
            student, ticket_num = stu, 2
            break

    if not student:
        return jsonify({"valid": False, "message": "INVALID - Unknown Ticket"})

    scan_log = data.get("scan_log", {})
    if barcode in scan_log:
        return jsonify({
            "valid": False,
            "message": f"INVALID - Already Used at {scan_log[barcode]}",
            "name": student["name"]
        })

    scan_log[barcode] = datetime.now().strftime("%d/%m %H:%M")
    data["scan_log"] = scan_log
    save_data(data)

    return jsonify({
        "valid": True,
        "message": f"VALID - Welcome, {student['name']}! (Ticket #{ticket_num})",
        "name": student["name"]
    })

@app.route('/api/lookup_barcodes', methods=['POST'])
def lookup_barcodes():
    req = request.json
    barcode1 = req.get('barcode1', '').strip()
    barcode2 = req.get('barcode2', '').strip()
    data = load_data()

    result = {"barcode1": None, "barcode2": None, "error": None}

    student1 = None
    student2 = None

    for stu in data["students"]:
        if stu["barcode1"] == barcode1 or stu["barcode2"] == barcode1:
            student1 = stu
            result["barcode1"] = {
                "name": stu["name"],
                "student_id": stu["id"],
                "barcode": barcode1,
                "ticket_num": 1 if stu["barcode1"] == barcode1 else 2
            }
        if stu["barcode1"] == barcode2 or stu["barcode2"] == barcode2:
            student2 = stu
            result["barcode2"] = {
                "name": stu["name"],
                "student_id": stu["id"],
                "barcode": barcode2,
                "ticket_num": 1 if stu["barcode1"] == barcode2 else 2
            }

    # Check if both barcodes belong to the same student
    if result["barcode1"] and result["barcode2"]:
        if student1["id"] != student2["id"]:
            result["error"] = "Wrong pair of tickets - barcodes belong to different students"

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
