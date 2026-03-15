# 🎓 AttendAI — QR Code Attendance System

A full-stack AI-powered QR attendance system built with Flask, SQLite, and vanilla JS.

---

## 🚀 Quick Start

```bash
# 1. Navigate to the project folder
cd project

# 2. (Recommended) Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open:
- **Teacher Dashboard** → http://127.0.0.1:5000/
- **Student Page** → http://127.0.0.1:5000/student

---

## 📁 Folder Structure

```
project/
├── app.py                  # Flask backend (all APIs)
├── run.py                  # Auto-install + run script
├── requirements.txt        # Python dependencies
├── database.db             # SQLite DB (auto-created)
├── templates/
│   ├── dashboard.html      # Teacher dashboard
│   └── student.html        # Student attendance page
└── static/
    ├── css/                # (reserved for custom CSS)
    ├── js/                 # (reserved for custom JS)
    └── qr/                 # QR code images (auto-generated)
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/generate_session` | Generate new QR session |
| POST | `/mark_attendance` | Mark student attendance |
| GET | `/attendance_list` | List attendance records |
| GET | `/sessions` | List all sessions |
| GET | `/export_csv` | Download attendance CSV |
| GET | `/students` | List all students |

### POST /generate_session
```json
{ "subject": "Data Structures" }
```
Response:
```json
{
  "session_id": "uuid",
  "qr_token": "uuid",
  "qr_image": "/static/qr/uuid.png",
  "expiry_time": "ISO datetime",
  "subject": "Data Structures"
}
```

### POST /mark_attendance
```json
{
  "student_id": "STU001",
  "session_id": "uuid",
  "qr_token": "uuid",
  "latitude": 19.076,
  "longitude": 72.877,
  "device_id": "DEV-XXXXXXXX"
}
```

---

## 🔒 Security Features

| Feature | Description |
|---------|-------------|
| ⏱ QR Expiry | QR codes expire after 2 minutes |
| 📍 Location Check | Must be within 50m of classroom |
| 📱 Device Binding | Device ID locked to student on first use |
| 🔁 Duplicate Guard | One attendance per student per session |
| 🔄 Auto-Refresh | New QR auto-generated before expiry |

---

## ⚙️ Configuration

Edit these constants in `app.py`:

```python
CLASSROOM_LAT = 19.0760       # Your classroom latitude
CLASSROOM_LON = 72.8777       # Your classroom longitude
ALLOWED_RADIUS_METERS = 50    # Allowed distance in meters
```

---

## 👥 Demo Students (Pre-seeded)

| ID | Name | Email |
|----|------|-------|
| STU001 | Aarav Sharma | aarav@college.edu |
| STU002 | Priya Patel | priya@college.edu |
| STU003 | Rohit Kumar | rohit@college.edu |
| STU004 | Sneha Mehta | sneha@college.edu |
| STU005 | Arjun Nair | arjun@college.edu |

---

## 🧪 Testing Locally

Since GPS verification requires real location, for local testing the system will:
- Skip distance check if no GPS coordinates provided
- Accept attendance without strict location enforcement

For production, enable strict GPS enforcement and set your real classroom coordinates.

---

## 📦 Dependencies

- **Flask** — Web framework
- **qrcode[pil]** — QR code generation
- **geopy** — Distance calculation
- **Pillow** — Image processing
- **jsQR** — Client-side QR scanning (CDN)
