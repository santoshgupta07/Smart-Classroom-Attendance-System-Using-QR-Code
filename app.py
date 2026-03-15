from flask import Flask, request, jsonify, render_template, send_file
import sqlite3, uuid, qrcode, json, csv, io, os, re
from datetime import datetime, timedelta
from geopy.distance import geodesic

app = Flask(__name__)

CLASSROOM_LAT = 19.0760
CLASSROOM_LON = 72.8777
ALLOWED_RADIUS_METERS = 50

DB_PATH = "database.db"
QR_DIR = "static/qr"
os.makedirs(QR_DIR, exist_ok=True)

SUBJECTS = [
    "Data Structures", "Algorithms", "Operating Systems",
    "Database Management", "Computer Networks", "Software Engineering",
    "Machine Learning", "Web Development", "Mathematics", "Physics"
]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            phone       TEXT,
            department  TEXT,
            year        TEXT,
            device_id   TEXT,
            face_image  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id           TEXT PRIMARY KEY,
            qr_token     TEXT UNIQUE NOT NULL,
            subject      TEXT DEFAULT 'General',
            lecture_no   INTEGER DEFAULT 1,
            created_time TEXT NOT NULL,
            expiry_time  TEXT NOT NULL,
            stopped_at   TEXT,
            status       TEXT DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT NOT NULL,
            session_id  TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            latitude    REAL,
            longitude   REAL,
            status      TEXT DEFAULT 'present',
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            UNIQUE(student_id, session_id)
        );
    """)
    demo = [
        ("STU001","Aarav Sharma","aarav@college.edu","9876543210","Computer Science","3rd Year"),
        ("STU002","Priya Patel","priya@college.edu","9876543211","Computer Science","3rd Year"),
        ("STU003","Rohit Kumar","rohit@college.edu","9876543212","Information Tech","2nd Year"),
        ("STU004","Sneha Mehta","sneha@college.edu","9876543213","Computer Science","3rd Year"),
        ("STU005","Arjun Nair","arjun@college.edu","9876543214","Electronics","4th Year"),
    ]
    for s in demo:
        c.execute("INSERT OR IGNORE INTO students (id,name,email,phone,department,year) VALUES (?,?,?,?,?,?)", s)
    conn.commit()
    conn.close()

def now_iso():
    return datetime.utcnow().isoformat()

def is_within_range(lat, lon):
    if lat is None or lon is None:
        return False, 0
    dist = geodesic((lat, lon), (CLASSROOM_LAT, CLASSROOM_LON)).meters
    return dist <= ALLOWED_RADIUS_METERS, round(dist, 1)

def next_lecture_no(subject):
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) FROM sessions WHERE subject=?", (subject,)).fetchone()
    conn.close()
    return row[0] + 1

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/student")
def student_page():
    return render_template("student.html")

@app.route("/subjects", methods=["GET"])
def get_subjects():
    conn = get_db()
    rows = conn.execute("SELECT subject, COUNT(*) as count FROM sessions GROUP BY subject").fetchall()
    conn.close()
    subject_map = {r["subject"]: r["count"] for r in rows}
    result = [{"name": s, "count": subject_map.get(s, 0)} for s in SUBJECTS]
    for s in subject_map:
        if s not in SUBJECTS:
            result.append({"name": s, "count": subject_map[s]})
    return jsonify(result)

@app.route("/generate_session", methods=["POST"])
def generate_session():
    data = request.get_json(silent=True) or {}
    subject = data.get("subject", "General").strip()
    lecture_no = next_lecture_no(subject)
    session_id = str(uuid.uuid4())
    qr_token   = str(uuid.uuid4())
    created    = datetime.utcnow()
    expiry     = created + timedelta(minutes=2)
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (id,qr_token,subject,lecture_no,created_time,expiry_time,status) VALUES (?,?,?,?,?,?,?)",
        (session_id, qr_token, subject, lecture_no, created.isoformat(), expiry.isoformat(), "active")
    )
    conn.commit()
    conn.close()
    payload = json.dumps({"session_id": session_id, "token": qr_token, "ts": created.isoformat()})
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=3)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a26", back_color="white")
    qr_filename = f"{session_id}.png"
    img.save(os.path.join(QR_DIR, qr_filename))
    return jsonify({
        "session_id": session_id, "qr_token": qr_token,
        "qr_image": f"/static/qr/{qr_filename}",
        "expiry_time": expiry.isoformat(),
        "subject": subject, "lecture_no": lecture_no
    })

@app.route("/stop_session", methods=["POST"])
def stop_session():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()
    if not session_id:
        return jsonify({"success": False, "message": "session_id required"}), 400
    conn = get_db()
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "message": "Session not found"}), 404
    conn.execute(
        "UPDATE sessions SET status='stopped', stopped_at=?, expiry_time=? WHERE id=?",
        (now_iso(), now_iso(), session_id)
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM attendance WHERE session_id=?", (session_id,)).fetchone()[0]
    conn.close()
    return jsonify({
        "success": True,
        "message": f"Session stopped. {count} student(s) attended.",
        "attended": count, "subject": row["subject"], "lecture_no": row["lecture_no"]
    })

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id","").strip().upper()
    session_id = data.get("session_id","").strip()
    qr_token   = data.get("qr_token","").strip()
    latitude   = data.get("latitude")
    longitude  = data.get("longitude")
    device_id  = data.get("device_id","").strip()
    if not all([student_id, session_id, qr_token]):
        return jsonify({"success": False, "message": "Missing required fields."}), 400
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return jsonify({"success": False, "message": "Student ID not found. Please register on the student page."}), 404
    session = conn.execute("SELECT * FROM sessions WHERE id=? AND qr_token=?", (session_id, qr_token)).fetchone()
    if not session:
        conn.close()
        return jsonify({"success": False, "message": "Invalid QR code."}), 400
    if session["status"] == "stopped":
        conn.close()
        return jsonify({"success": False, "message": "This session has been stopped by the teacher."}), 400
    if datetime.utcnow() > datetime.fromisoformat(session["expiry_time"]):
        conn.close()
        return jsonify({"success": False, "message": "QR code has expired. Ask teacher to regenerate."}), 400
    if student["device_id"] and student["device_id"] != device_id:
        conn.close()
        return jsonify({"success": False, "message": "Device mismatch. Proxy attempt blocked."}), 403
    if not student["device_id"] and device_id:
        conn.execute("UPDATE students SET device_id=? WHERE id=?", (device_id, student_id))
    existing = conn.execute("SELECT id FROM attendance WHERE student_id=? AND session_id=?", (student_id, session_id)).fetchone()
    if existing:
        conn.close()
        return jsonify({"success": False, "message": "Attendance already marked for this session."}), 409
    in_range, distance = is_within_range(latitude, longitude)
    if latitude is not None and not in_range:
        conn.close()
        return jsonify({"success": False, "message": f"You are {distance}m from the classroom (max {ALLOWED_RADIUS_METERS}m)."}), 403
    conn.execute(
        "INSERT INTO attendance (student_id,session_id,timestamp,latitude,longitude,status) VALUES (?,?,?,?,?,?)",
        (student_id, session_id, now_iso(), latitude, longitude, "present")
    )
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": f"Attendance marked! Welcome, {student['name']}.",
        "student_name": student["name"],
        "subject": session["subject"],
        "lecture_no": session["lecture_no"],
        "distance": distance if latitude else "N/A"
    })

@app.route("/register_student", methods=["POST"])
def register_student():
    data = request.get_json(silent=True) or {}
    name       = data.get("name","").strip()
    email      = data.get("email","").strip().lower()
    phone      = data.get("phone","").strip()
    department = data.get("department","").strip()
    year       = data.get("year","").strip()
    if not name or not email:
        return jsonify({"success": False, "message": "Name and email are required."}), 400
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"success": False, "message": "Invalid email address."}), 400
    conn = get_db()
    if conn.execute("SELECT id FROM students WHERE email=?", (email,)).fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Email already registered."}), 409
    last = conn.execute("SELECT id FROM students WHERE id LIKE 'STU%' ORDER BY id DESC LIMIT 1").fetchone()
    try:
        num = int(last["id"][3:]) + 1 if last else 1
    except (ValueError, TypeError):
        num = 100
    student_id = f"STU{num:03d}"
    conn.execute(
        "INSERT INTO students (id,name,email,phone,department,year) VALUES (?,?,?,?,?,?)",
        (student_id, name, email, phone, department, year)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Registered! Your Student ID is {student_id}", "student_id": student_id, "name": name})

@app.route("/attendance_list", methods=["GET"])
def attendance_list():
    session_id = request.args.get("session_id")
    conn = get_db()
    if session_id:
        rows = conn.execute("""
            SELECT a.id, s.id as student_id, s.name, s.email, s.department, s.year,
                   a.timestamp, a.latitude, a.longitude, a.status, a.session_id
            FROM attendance a JOIN students s ON a.student_id = s.id
            WHERE a.session_id = ? ORDER BY a.timestamp DESC
        """, (session_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT a.id, s.id as student_id, s.name, s.email, s.department, s.year,
                   a.timestamp, a.latitude, a.longitude, a.status, a.session_id
            FROM attendance a JOIN students s ON a.student_id = s.id
            ORDER BY a.timestamp DESC
        """).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    conn.close()
    return jsonify({"attendance": [dict(r) for r in rows], "total_students": total, "present_count": len(rows)})

@app.route("/sessions", methods=["GET"])
def get_sessions():
    subject = request.args.get("subject")
    conn = get_db()
    if subject:
        rows = conn.execute("SELECT * FROM sessions WHERE subject=? ORDER BY created_time DESC", (subject,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sessions ORDER BY created_time DESC LIMIT 30").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/students", methods=["GET"])
def get_students():
    conn = get_db()
    rows = conn.execute("SELECT id,name,email,phone,department,year,created_at FROM students ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/export_csv", methods=["GET"])
def export_csv():
    session_id = request.args.get("session_id", "all")
    conn = get_db()
    if session_id != "all":
        rows = conn.execute("""
            SELECT s.id, s.name, s.email, s.department, s.year,
                   a.timestamp, a.latitude, a.longitude, a.status,
                   ss.subject, ss.lecture_no
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            JOIN sessions ss ON a.session_id = ss.id
            WHERE a.session_id = ? ORDER BY a.timestamp
        """, (session_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT s.id, s.name, s.email, s.department, s.year,
                   a.timestamp, a.latitude, a.longitude, a.status,
                   ss.subject, ss.lecture_no
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            JOIN sessions ss ON a.session_id = ss.id
            ORDER BY a.timestamp
        """).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student ID","Name","Email","Department","Year","Timestamp","Latitude","Longitude","Status","Subject","Lecture No"])
    for r in rows:
        writer.writerow(list(r))
    output.seek(0)
    return send_file(
        io.BytesIO(output.read().encode()), mimetype="text/csv", as_attachment=True,
        download_name=f"attendance_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

if __name__ == "__main__":
    init_db()
    print("\n✅  AttendAI started!")
    print("   Teacher Dashboard → http://127.0.0.1:5000/")
    print("   Student Page      → http://127.0.0.1:5000/student\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
