import os
import re
import csv
import zipfile
import calendar
import secrets
import hmac
import urllib.parse
import urllib.request
import base64
import io
import pyotp
import qrcode
from pathlib import Path
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request, redirect, session, send_file, send_from_directory, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, template_folder=str(BASE_DIR), static_folder=str(BASE_DIR / "static"), static_url_path="/static")
app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    upload_dir = BASE_DIR / "uploads"
    requested_path = upload_dir / filename
    if requested_path.is_file():
        return send_from_directory(upload_dir, filename)
    match = re.match(r"student_(\d+)_", Path(filename).name)
    if match:
        student_prefix = f"student_{match.group(1)}_"
        fallback = next((path for path in upload_dir.glob(f"{student_prefix}*") if path.is_file()), None)
        if fallback:
            return send_from_directory(upload_dir, fallback.name)
    return "File not found", 404


@app.route("/payment-qr")
def payment_qr():
    payment_path = BASE_DIR / "payment.jpeg"
    if not payment_path.is_file():
        return "Payment QR code is not configured", 404
    return send_file(payment_path, mimetype="image/jpeg")

app.secret_key = os.environ.get("SECRET_KEY", "hostel_secret_key")
app.config["SESSION_TYPE"] = "filesystem"
HOSTEL_FEE = 114000.00
ADMIN_2FA_ENABLED = os.environ.get("ADMIN_2FA_ENABLED", "1").lower() not in {"0", "false", "no", "off"}
STUDENT_EMAIL_VERIFICATION_ENABLED = os.environ.get("STUDENT_EMAIL_VERIFICATION_ENABLED", "0").lower() not in {"0", "false", "no", "off"}


def get_db_connection():
    import mysql.connector

    db_host = os.environ.get("MYSQLHOST", "localhost")
    db_port = int(os.environ.get("MYSQLPORT", 3306))
    db_user = os.environ.get("MYSQLUSER", "root")
    db_password = os.environ.get("MYSQLPASSWORD", "")
    db_name = os.environ.get("MYSQLDATABASE", "hostel_tracker")

    return mysql.connector.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
    )


def find_admin(cursor, value: str):
    cursor.execute(
        "SELECT * FROM `admin` WHERE role IN ('admin', 'super_admin') AND (LOWER(email)=%s OR LOWER(`admin id`)=%s OR LOWER(`neme`)=%s)",
        (value, value, value),
    )
    return cursor.fetchone()


def find_staff_role(cursor, value: str, role: str):
    cursor.execute(
        "SELECT * FROM `admin` WHERE role=%s AND (LOWER(email)=%s OR LOWER(`admin id`)=%s OR LOWER(`neme`)=%s)",
        (role, value, value, value),
    )
    return cursor.fetchone()


def find_any_staff(cursor, value: str):
    cursor.execute(
        "SELECT * FROM `admin` WHERE LOWER(email)=%s OR LOWER(`admin id`)=%s OR LOWER(`neme`)=%s",
        (value, value, value),
    )
    return cursor.fetchone()


def find_warden(cursor, value: str):
    return find_staff_role(cursor, value, "warden")


def initialize_database():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100),
                phone VARCHAR(20),
                hostel VARCHAR(100),
                block VARCHAR(100),
                room VARCHAR(20),
                password VARCHAR(255),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                rent_paid VARCHAR(10) NOT NULL DEFAULT 'no',
                rent_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                rent_paid_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                college VARCHAR(150),
                course VARCHAR(100),
                aadhaar VARCHAR(20),
                guardian_name VARCHAR(100),
                guardian_phone VARCHAR(20),
                guardian_phone_2 VARCHAR(20),
                father_name VARCHAR(100),
                mother_name VARCHAR(100),
                home_address VARCHAR(255),
                address_city VARCHAR(100),
                address_district VARCHAR(100),
                address_state VARCHAR(100),
                address_pincode VARCHAR(10),
                address_country VARCHAR(100),
                emergency_contact VARCHAR(100),
                photo_url VARCHAR(255),
                email_verified TINYINT(1) NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN rent_paid VARCHAR(10) NOT NULL DEFAULT 'no'
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN rent_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN rent_paid_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN college VARCHAR(150)
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN course VARCHAR(100)
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN aadhaar VARCHAR(20)
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN guardian_name VARCHAR(100)
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN guardian_phone VARCHAR(20)
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN guardian_phone_2 VARCHAR(20)
                """
            )
        except Exception:
            pass
        for column_sql in (
            "ALTER TABLE students ADD COLUMN father_name VARCHAR(100)",
            "ALTER TABLE students ADD COLUMN mother_name VARCHAR(100)",
            "ALTER TABLE students ADD COLUMN home_address VARCHAR(255)",
            "ALTER TABLE students ADD COLUMN address_city VARCHAR(100)",
            "ALTER TABLE students ADD COLUMN address_district VARCHAR(100)",
            "ALTER TABLE students ADD COLUMN address_state VARCHAR(100)",
            "ALTER TABLE students ADD COLUMN address_pincode VARCHAR(10)",
            "ALTER TABLE students ADD COLUMN address_country VARCHAR(100)",
            "ALTER TABLE students ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1",
        ):
            try:
                cursor.execute(column_sql)
            except Exception:
                pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN emergency_contact VARCHAR(100)
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN photo_url VARCHAR(255)
                """
            )
        except Exception:
            pass
        try:
            cursor.execute(
                """
                ALTER TABLE students
                ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                """
            )
        except Exception:
            pass
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS `admin` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                `neme` VARCHAR(100),
                `email` VARCHAR(100) UNIQUE,
                `admin id` VARCHAR(100) UNIQUE,
                `password` VARCHAR(255),
                phone VARCHAR(20),
                role VARCHAR(20) NOT NULL DEFAULT 'admin',
                two_factor_secret VARCHAR(64),
                two_factor_enabled TINYINT(1) NOT NULL DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INT AUTO_INCREMENT PRIMARY KEY,
                hostel VARCHAR(100),
                block VARCHAR(100),
                room VARCHAR(20),
                capacity INT NOT NULL DEFAULT 1,
                status VARCHAR(20) NOT NULL DEFAULT 'available',
                maintenance_notes VARCHAR(255),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        homepage_rooms = [
            ("RKH", "Basement", f"B-{number:02d}") for number in range(1, 8)
        ] + [
            ("RKH", "1st Floor", str(number)) for number in range(101, 109)
        ] + [
            ("RKH", "2nd Floor", str(number)) for number in range(201, 209)
        ] + [
            ("RKH", "3rd Floor", str(number)) for number in range(301, 309)
        ]
        cursor.execute(
            "UPDATE rooms SET block='Basement', room='B-01' WHERE hostel='RKH' AND block='Basment' AND room='01'"
        )
        cursor.execute("SELECT hostel, block, room FROM rooms")
        existing_rooms = set(cursor.fetchall())
        missing_rooms = [room for room in homepage_rooms if room not in existing_rooms]
        if missing_rooms:
            cursor.executemany(
                "INSERT INTO rooms (hostel, block, room, capacity, status) VALUES (%s, %s, %s, 1, 'available')",
                missing_rooms,
            )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                category VARCHAR(50),
                subject VARCHAR(150),
                description TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS laundry_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                token_no VARCHAR(50),
                verification_code CHAR(6),
                token_date VARCHAR(50),
                token_time VARCHAR(50),
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                attendance_date VARCHAR(50),
                status VARCHAR(20) NOT NULL DEFAULT 'present',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance_locks (
                attendance_date VARCHAR(50) PRIMARY KEY,
                locked_by INT NOT NULL,
                locked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS leave_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                leave_type VARCHAR(30) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                reason VARCHAR(255) NOT NULL,
                destination VARCHAR(255),
                emergency_contact VARCHAR(30),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                admin_note VARCHAR(255),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NULL,
                title VARCHAR(150) NOT NULL,
                message TEXT NOT NULL,
                image_url VARCHAR(255),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_submissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                utr VARCHAR(100) NOT NULL,
                payment_date DATE NOT NULL,
                payment_method VARCHAR(50) NOT NULL DEFAULT 'UPI',
                notes VARCHAR(500),
                screenshot_url VARCHAR(255),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                admin_note VARCHAR(255),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_access_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                admin_id INT NOT NULL,
                email VARCHAR(150) NOT NULL,
                role VARCHAR(30) NOT NULL,
                ip_address VARCHAR(64),
                user_agent TEXT,
                accessed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for column_sql in (
            "ALTER TABLE admin_access_logs ADD COLUMN session_token VARCHAR(128)",
            "ALTER TABLE admin_access_logs ADD COLUMN session_active TINYINT(1) NOT NULL DEFAULT 1",
        ):
            try:
                cursor.execute(column_sql)
            except Exception:
                pass
        for column_sql in [
            "ALTER TABLE students ADD COLUMN department VARCHAR(100)",
            "ALTER TABLE students ADD COLUMN year_semester VARCHAR(100)",
            "ALTER TABLE students ADD COLUMN bed_number VARCHAR(20)",
            "ALTER TABLE students ADD COLUMN blood_group VARCHAR(10)",
            "ALTER TABLE students ADD COLUMN college_id_url VARCHAR(255)",
            "ALTER TABLE students ADD COLUMN valid_until VARCHAR(50)",
            "ALTER TABLE students ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0",
            "ALTER TABLE `admin` ADD COLUMN phone VARCHAR(20)",
            "ALTER TABLE `admin` ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin'",
            "ALTER TABLE `admin` ADD COLUMN two_factor_secret VARCHAR(64)",
            "ALTER TABLE `admin` ADD COLUMN two_factor_enabled TINYINT(1) NOT NULL DEFAULT 0",
            "ALTER TABLE laundry_tokens ADD COLUMN valid_until VARCHAR(50)",
                "ALTER TABLE laundry_tokens ADD COLUMN verification_code CHAR(6)",
                "ALTER TABLE laundry_tokens ADD COLUMN bag_in_at DATETIME NULL",
                "ALTER TABLE laundry_tokens ADD COLUMN bag_out_at DATETIME NULL",
                "ALTER TABLE laundry_tokens ADD COLUMN out_code CHAR(6)",
        ]:
            try:
                cursor.execute(column_sql)
            except Exception:
                pass
        cursor.execute(
            """
            INSERT INTO `admin` (`neme`, `email`, `admin id`, `password`, phone)
            VALUES ('Hostel admin', 'admin@gmail.com', 'admin@gmail.com', %s, NULL)
            ON DUPLICATE KEY UPDATE
                `neme` = VALUES(`neme`),
                `email` = VALUES(`email`),
                `admin id` = VALUES(`admin id`),
                `password` = VALUES(`password`)
            """,
            (hash_password("admin123"),),
        )
        mukesh_admin_password = os.environ.get("MUKESH_ADMIN_PASSWORD", "RkHostel!Admin#2026")
        cursor.execute(
            """
            INSERT INTO `admin` (`neme`, `email`, `admin id`, `password`, phone)
            VALUES ('Mukesh Bagri', 'mukeshbagri538@gmail.com', 'mukeshbagri538@gmail.com', %s, '7357548523')
            ON DUPLICATE KEY UPDATE
                `neme` = VALUES(`neme`),
                `password` = VALUES(`password`),
                phone = VALUES(phone)
            """,
            (hash_password(mukesh_admin_password),),
        )
        for name, email, password, role in [
            ("Warden", "mukeshbagri598@gmail.com", "Mukeshbagri598@#", "warden"),
            ("Laundry Admin", "mukeshbagri599@gmail.com", "Mukeshbagri599", "laundry_admin"),
            ("Mess Admin", "mukesh24@gmail.com", "mukesh24@#", "mess_admin"),
        ]:
            cursor.execute(
                """
                INSERT INTO `admin` (`neme`, `email`, `admin id`, `password`, phone, role, two_factor_enabled)
                VALUES (%s, %s, %s, %s, NULL, %s, 0)
                ON DUPLICATE KEY UPDATE `neme`=VALUES(`neme`), `password`=VALUES(`password`), role=VALUES(role), two_factor_enabled=0
                """,
                (name, email, email, hash_password(password), role),
            )
        cursor.execute("SELECT id, two_factor_secret FROM `admin`")
        for admin in cursor.fetchall():
            if not admin[1]:
                cursor.execute("UPDATE `admin` SET two_factor_secret=%s WHERE id=%s", (pyotp.random_base32(), admin[0]))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Database initialization skipped:", exc)


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return check_password_hash(hashed_password, password)


def get_admin_security_context(admin_id):
    try:
        session_secret = session.get("admin_2fa_secret")
        session_email = session.get("admin_2fa_email", "")
        if session_secret and session_email:
            provisioning_uri = pyotp.TOTP(session_secret).provisioning_uri(
                name=session_email, issuer_name="Radha Krishan Hostel"
            )
            qr = qrcode.make(provisioning_uri)
            qr_buffer = io.BytesIO()
            qr.save(qr_buffer, format="PNG")
            return {
                "enabled": bool(session.get("admin_2fa_enabled", 0)),
                "qr_data": "data:image/png;base64," + base64.b64encode(qr_buffer.getvalue()).decode(),
                "email": session_email,
            }
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(
            "SELECT id, email, two_factor_secret, two_factor_enabled FROM `admin` WHERE id=%s",
            (admin_id,),
        )
        admin = cursor.fetchone()
        if not admin:
            cursor.close()
            connection.close()
            return {"enabled": False, "qr_data": "", "email": ""}
        if not admin.get("two_factor_secret"):
            admin_secret = pyotp.random_base32()
            cursor.execute(
                "UPDATE `admin` SET two_factor_secret=%s WHERE id=%s",
                (admin_secret, admin_id),
            )
            connection.commit()
            admin["two_factor_secret"] = admin_secret
        session["admin_2fa_secret"] = admin["two_factor_secret"]
        session["admin_2fa_email"] = admin.get("email", "")
        session["admin_2fa_enabled"] = bool(admin.get("two_factor_enabled", 0))
        provisioning_uri = pyotp.TOTP(admin["two_factor_secret"]).provisioning_uri(
            name=admin["email"], issuer_name="Radha Krishan Hostel"
        )
        qr = qrcode.make(provisioning_uri)
        qr_buffer = io.BytesIO()
        qr.save(qr_buffer, format="PNG")
        qr_data = "data:image/png;base64," + base64.b64encode(qr_buffer.getvalue()).decode()
        cursor.close()
        connection.close()
        return {
            "enabled": bool(admin.get("two_factor_enabled", 0)),
            "qr_data": qr_data,
            "email": admin.get("email", ""),
        }
    except Exception as exc:
        print("Admin security context failed:", exc)
        fallback_secret = session.get("admin_2fa_secret") or pyotp.random_base32()
        fallback_email = session.get("admin_2fa_email") or "mukeshbagri538@gmail.com"
        session["admin_2fa_secret"] = fallback_secret
        session["admin_2fa_email"] = fallback_email
        provisioning_uri = pyotp.TOTP(fallback_secret).provisioning_uri(
            name=fallback_email, issuer_name="Radha Krishan Hostel"
        )
        qr = qrcode.make(provisioning_uri)
        qr_buffer = io.BytesIO()
        qr.save(qr_buffer, format="PNG")
        return {
            "enabled": bool(session.get("admin_2fa_enabled", 0)),
            "qr_data": "data:image/png;base64," + base64.b64encode(qr_buffer.getvalue()).decode(),
            "email": fallback_email,
        }


def record_admin_access(admin, role):
    try:
        session_token = secrets.token_urlsafe(32)
        session["admin_session_token"] = session_token
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO admin_access_logs (admin_id, email, role, ip_address, user_agent, session_token, session_active) VALUES (%s, %s, %s, %s, %s, %s, 1)",
            (
                admin["id"],
                admin.get("email", ""),
                role,
                request.headers.get("X-Forwarded-For", request.remote_addr),
                request.user_agent.string[:1000],
                session_token,
            ),
        )
        connection.commit()
        session["admin_access_log_id"] = cursor.lastrowid
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Admin access logging failed:", exc)


def readable_device_name(user_agent):
    agent = (user_agent or "").lower()
    if "edg/" in agent:
        browser = "Microsoft Edge"
    elif "chrome/" in agent:
        browser = "Google Chrome"
    elif "firefox/" in agent:
        browser = "Mozilla Firefox"
    elif "safari/" in agent and "chrome/" not in agent:
        browser = "Safari"
    else:
        browser = "Other Browser"
    if "windows" in agent:
        platform = "Windows"
    elif "android" in agent:
        platform = "Android"
    elif "iphone" in agent or "ipad" in agent:
        platform = "iPhone/iPad"
    elif "mac os" in agent:
        platform = "macOS"
    elif "linux" in agent:
        platform = "Linux"
    else:
        platform = "Unknown device"
    return f"{browser} on {platform}"


def send_otp_email(email: str, otp: str, purpose: str = "verification") -> bool:
    try:
        host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        if not host:
            print(f"OTP for {email}: {otp}")
            return False
        import smtplib
        from email.message import EmailMessage

        port = int(os.environ.get("SMTP_PORT", "587"))
        username = os.environ.get("SMTP_USERNAME")
        password = os.environ.get("SMTP_PASSWORD")
        if not username or not password:
            print("OTP email not sent: SMTP_USERNAME and SMTP_PASSWORD are required")
            return False

        message = EmailMessage()
        message["Subject"] = f"Your 6-digit Hostel {purpose.title()} Verification Code"
        message["From"] = username
        message["To"] = email
        message.set_content(
            f"Your 6-digit verification code is: {otp}\n\n"
            f"Use this code to verify that you own this email address and complete the {purpose}. "
            "This code expires in 10 minutes. If you did not request this, ignore this email."
        )

        if os.environ.get("SMTP_USE_SSL", "0").lower() in {"1", "true", "yes"} or port == 465:
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(message)
        return True
    except Exception as exc:
        print("OTP email failed:", exc)
        return False


def send_otp_sms(phone: str, otp: str, purpose: str = "admin login") -> bool:
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_phone = os.environ.get("TWILIO_FROM_PHONE")
    if not account_sid or not auth_token or not from_phone:
        print(f"OTP for +91{phone}: {otp}")
        return False
    try:
        payload = urllib.parse.urlencode({
            "To": f"+91{phone}",
            "From": from_phone,
            "Body": f"Your Hostel {purpose} OTP is {otp}. It expires in 10 minutes.",
        }).encode()
        request = urllib.request.Request(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            data=payload,
        )
        credentials = f"{account_sid}:{auth_token}".encode()
        request.add_header("Authorization", "Basic " + __import__("base64").b64encode(credentials).decode())
        with urllib.request.urlopen(request, timeout=15):
            return True
    except Exception as exc:
        print("OTP SMS failed:", exc)
        return False


def create_otp() -> str:
    return str(secrets.randbelow(1000000)).zfill(6)


def otp_is_valid(stored_otp: str, stored_time: str, submitted_otp: str) -> bool:
    if not stored_otp or not stored_time or not submitted_otp:
        return False
    try:
        created_at = datetime.strptime(stored_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return datetime.now() - created_at <= timedelta(minutes=10) and hmac.compare_digest(stored_otp, submitted_otp.strip())


def write_simple_pdf(path: str, lines: list[str]):
    escaped_lines = []
    for line in lines:
        escaped_lines.append(str(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)"))
    content = []
    y_position = 760
    for line in escaped_lines:
        content.append(f"BT /F1 12 Tf 50 {y_position} Td ({line}) Tj ET")
        y_position -= 14
    stream = "\n".join(content)
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    pdf = ["%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(len("".join(pdf).encode("latin-1")))
        pdf.append(obj)
    xref_offset = len("".join(pdf).encode("latin-1"))
    pdf.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.append(f"{offset:010d} 00000 n \n")
    pdf.append(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n")
    with open(path, "wb") as fh:
        fh.write("".join(pdf).encode("latin-1"))

def write_fee_receipt_pdf(path: str, student, fee_summary, receipt_no: str):
    student = student or {}
    generated = datetime.now().strftime("%d %b %Y %I:%M %p")
    text_items = [
        (50, 748, 20, "RADHA KRISHAN HOSTEL"),
        (50, 728, 11, "HOSTEL FEE RECEIPT"),
        (420, 748, 10, f"Receipt No: {receipt_no}"),
        (420, 732, 10, f"Date: {generated}"),
        (50, 684, 12, "STUDENT DETAILS"),
        (65, 660, 10, f"Name: {student.get('name') or 'Student'}"),
        (65, 642, 10, f"Student ID: {student.get('id') or '-'}"),
        (65, 624, 10, f"Email: {student.get('email') or '-'}"),
        (65, 606, 10, f"Mobile: {student.get('phone') or '-'}"),
        (320, 660, 10, f"Hostel: {student.get('hostel') or '-'}"),
        (320, 642, 10, f"Floor: {student.get('block') or '-'}"),
        (320, 624, 10, f"Room: {student.get('room') or '-'}"),
        (50, 556, 12, "FEE SUMMARY"),
        (70, 522, 11, "Description"),
        (430, 522, 11, "Amount"),
        (70, 488, 11, "Total Hostel Fee"),
        (430, 488, 11, f"Rs. {fee_summary['rent_amount']:,.2f}"),
        (70, 458, 11, "Amount Paid"),
        (430, 458, 11, f"Rs. {fee_summary['rent_paid_amount']:,.2f}"),
        (70, 428, 11, "Balance Due"),
        (430, 428, 11, f"Rs. {fee_summary['pending_amount']:,.2f}"),
        (70, 382, 12, f"Payment Status: {fee_summary['status']}"),
        (50, 320, 10, "This is a computer-generated receipt for hostel fee payment."),
        (50, 292, 10, "Please retain this receipt for your records."),
        (400, 180, 10, "Authorized Signature"),
    ]
    commands = ["0.8 w", "50 700 m 562 700 l S", "50 570 m 562 570 l S", "50 540 m 562 540 l S", "50 505 m 562 505 l S", "50 475 m 562 475 l S", "50 445 m 562 445 l S", "50 350 m 562 350 l S", "50 590 512 94 re S"]
    for x, y, size, value in text_items:
        escaped = str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET")
    stream = "\n".join(commands)
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    pdf = ["%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(len("".join(pdf).encode("latin-1")))
        pdf.append(obj)
    xref_offset = len("".join(pdf).encode("latin-1"))
    pdf.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.append(f"{offset:010d} 00000 n \n")
    pdf.append(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n")
    with open(path, "wb") as fh:
        fh.write("".join(pdf).encode("latin-1"))


def get_server_config() -> tuple[str, int, bool]:
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "0") not in {"", "0", "false", "False", "no", "No"}
    return host, port, debug


database_initialized = False


def can_access_student_dashboard(student):
    if not student:
        return False, "Please sign in again."
    if not bool(student.get("is_active", 1)):
        return False, "Your student account is currently inactive. Please contact the administrator."

    status = str(student.get("status", "pending") or "pending").strip().lower()
    if status == "approved":
        return True, ""

    return False, "Please sign in again."


def student_profile_complete(student):
    if not student:
        return False
    required_fields = (
        "name", "phone", "college", "course", "department", "year_semester",
        "guardian_name", "guardian_phone", "guardian_phone_2", "father_name", "mother_name", "home_address",
        "address_city", "address_district", "address_state", "address_pincode", "address_country", "emergency_contact", "aadhaar",
        "blood_group", "photo_url",
    )
    return all(str(student.get(field) or "").strip() for field in required_fields)


def build_attendance_calendar(attendance_records=None):
    records = attendance_records or []
    month_start = datetime.now().replace(day=1)
    days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
    calendar_days = []
    for day in range(1, days_in_month + 1):
        current_day = datetime(month_start.year, month_start.month, day)
        day_key = current_day.strftime("%Y-%m-%d")
        day_display = current_day.strftime("%d %b %Y")
        status = "Absent"
        for record in records:
            record_date = str(record.get("attendance_date") or record.get("date") or "")
            if record_date in {day_key, day_display} or record_date.startswith(day_key):
                status = str(record.get("status") or "Present").capitalize()
                break
        calendar_days.append({"date": day_display, "day": current_day.strftime("%d"), "status": status})
    return calendar_days


def get_student_fee_summary(student):
    student_data = student or {}
    rent_amount = float(student_data.get("rent_amount") or 0)
    rent_paid_amount = float(student_data.get("rent_paid_amount") or 0)
    pending_amount = max(rent_amount - rent_paid_amount, 0.0)
    return {
        "rent_amount": rent_amount,
        "rent_paid_amount": rent_paid_amount,
        "pending_amount": pending_amount,
        "status": "Fully Paid" if pending_amount <= 0 else "Partially Paid" if rent_paid_amount > 0 else "Pending",
    }


def generate_laundry_token_number(cursor):
    cursor.execute("SELECT token_no FROM laundry_tokens ORDER BY id DESC LIMIT 1")
    last_token = cursor.fetchone()
    last_number = 0
    last_token_number = last_token.get("token_no") if isinstance(last_token, dict) else (last_token[0] if last_token else None)
    if last_token_number:
        match = re.search(r"(\d+)$", str(last_token_number))
        if match:
            last_number = int(match.group(1))
    next_number = last_number + 1
    return f"S.R.{next_number:04d}"


def build_student_dashboard_context(student, complaints=None, laundry_token=None, attendance_records=None, fee_summary=None, college_id_url=None, notifications=None, payment_submissions=None):
    student_data = student or {}
    student_id = student_data.get("id") or student_data.get("student_id") or "N/A"
    full_name = student_data.get("name") or "Student"
    hostel_name = student_data.get("hostel") or "Assigned Hostel"
    room_no = student_data.get("room") or "Pending"
    college_name = student_data.get("college") or "ABC University"
    course = student_data.get("course") or "Not provided"
    department = student_data.get("department") or "Department"
    year_semester = student_data.get("year_semester") or "Not provided"
    mobile = student_data.get("phone") or "-"
    email = student_data.get("email") or "-"
    admission_date = student_data.get("created_at") or datetime.now().strftime("%d %b %Y")
    bed_number = student_data.get("bed_number") or "Pending"
    blood_group = student_data.get("blood_group") or "B+"
    fee_summary = fee_summary or get_student_fee_summary(student_data)
    notification_entries = notifications if notifications is not None else [
        "Profile photo updated successfully.",
        "Laundry token generated for the next week.",
        "Complaint updated.",
        "Fee summary refreshed.",
    ]

    return {
        "profile": {
            "full_name": full_name,
            "student_id": student_id,
            "college": college_name,
            "course": course,
            "department": department,
            "year_semester": year_semester,
            "mobile": mobile,
            "email": email,
            "hostel_name": hostel_name,
            "room_number": room_no,
            "bed_number": bed_number,
            "admission_date": admission_date,
            "guardian_name": student_data.get("guardian_name") or "-",
            "guardian_phone": student_data.get("guardian_phone") or "-",
            "guardian_phone_2": student_data.get("guardian_phone_2") or "-",
            "father_name": student_data.get("father_name") or "-",
            "mother_name": student_data.get("mother_name") or "-",
            "home_address": student_data.get("home_address") or "-",
            "address_city": student_data.get("address_city") or "-",
            "address_district": student_data.get("address_district") or "-",
            "address_state": student_data.get("address_state") or "-",
            "address_pincode": student_data.get("address_pincode") or "-",
            "address_country": student_data.get("address_country") or "-",
            "emergency_contact": student_data.get("emergency_contact") or "-",
            "aadhaar": student_data.get("aadhaar") or "-",
            "blood_group": blood_group,
        },
        "hostel_id_card": {
            "hostel_id": f"HST{student_id if str(student_id).isdigit() else '000'}",
            "name": full_name,
            "hostel": hostel_name,
            "room_no": room_no,
            "blood_group": blood_group,
            "mobile": mobile,
            "valid_till": (datetime.now() + timedelta(days=365)).strftime("%d %b %Y"),
        },
        "college_id_card": {
            "college": college_name,
            "course": course,
            "department": department,
            "student_id": student_id,
            "college_id_url": college_id_url or student_data.get("college_id_url") or "",
        },
        "profile_photo": student_data.get("photo_url") or "/uploads/default-avatar.png",
        "attendance": attendance_records or [
            {"attendance_date": datetime.now().strftime("%Y-%m-%d"), "status": "Present"},
        ],
        "attendance_calendar": build_attendance_calendar(attendance_records),
        "fee_receipts": [
            {
                "receipt_no": f"HR{student_id:03d}",
                "student_name": full_name,
                "student_id": student_id,
                "email": email,
                "mobile": mobile,
                "hostel": hostel_name,
                "block": student_data.get("block") or "-",
                "room": room_no,
                "total_fee": f"₹{fee_summary['rent_amount']:,.2f}",
                "paid_amount": f"₹{fee_summary['rent_paid_amount']:,.2f}",
                "due_amount": f"₹{fee_summary['pending_amount']:,.2f}",
                "date": datetime.now().strftime("%d %b %Y"),
                "status": fee_summary["status"],
            }
        ],
        "fee_summary": fee_summary,
        "complaint_categories": [
            "Electrical",
            "Plumbing",
            "Wi-Fi",
            "Furniture",
            "Cleaning",
            "Mess Food",
            "Security",
            "Other",
        ],
        "complaints": complaints or [
            {"category": "Wi-Fi", "subject": "Internet issue", "status": "Pending", "date": datetime.now().strftime("%d %b %Y")},
            {"category": "Fan Repair", "subject": "AC not working", "status": "Completed", "date": (datetime.now() - timedelta(days=3)).strftime("%d %b %Y")},
        ],
        "laundry_token": laundry_token or {
            "token_no": "S.R.0001",
            "date": datetime.now().strftime("%d %b %Y"),
            "time": datetime.now().strftime("%I:%M %p"),
            "status": "Active",
            "valid_until": (datetime.now() + timedelta(days=7)).strftime("%d %b %Y"),
        },
        "notifications": notification_entries,
        "payment_submissions": payment_submissions or [],
        "hostel_info": {
            "hostel_name": hostel_name,
            "room_number": room_no,
            "floor": "2nd Floor",
            "warden_name": "Ms. Priya Nair",
            "warden_contact": "+91 98765 43210",
            "emergency_contact": "+91 99999 00000",
        },
    }


def seed_admin_user():
    initialize_database()


@app.before_request
def ensure_database_seeded():
    global database_initialized
    if not database_initialized:
        seed_admin_user()
        database_initialized = True
    if session.get("user_type") == "admin" and session.get("admin_access_log_id"):
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT session_active FROM admin_access_logs WHERE id=%s", (session["admin_access_log_id"],))
            access = cursor.fetchone()
            cursor.close()
            connection.close()
            if not access or not access[0]:
                session.clear()
                return redirect("/admin-login")
        except Exception as exc:
            print("Admin session validation failed:", exc)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/rooms")
def public_rooms():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(
            """
            SELECT r.id, r.hostel, r.block, r.room, r.capacity, r.status, r.maintenance_notes,
                   COUNT(CASE WHEN s.status IN ('pending', 'approved') THEN 1 END) AS occupants
            FROM rooms r
            LEFT JOIN students s ON s.hostel=r.hostel AND s.block=r.block AND s.room=r.room
            GROUP BY r.id, r.hostel, r.block, r.room, r.capacity, r.status, r.maintenance_notes
            ORDER BY r.hostel, r.block, r.room
            """
        )
        rooms = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify({"rooms": rooms})
    except Exception as exc:
        print("Public room lookup failed:", exc)
        return jsonify({"rooms": [], "error": "Room availability is temporarily unavailable."}), 503


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)

            admin = find_any_staff(cursor, email)
            if admin:
                stored_admin_password = admin.get("password", "")
                if verify_password(password, stored_admin_password):
                    session["user_type"] = "admin"
                    session["user_id"] = admin["id"]
                    cursor.close()
                    connection.close()
                    return redirect("/admin-dashboard")

            cursor.execute("SELECT * FROM students WHERE LOWER(email)=%s", (email,))
            student = cursor.fetchone()
            cursor.close()
            connection.close()

            stored_student_password = student.get("password", "") if student else ""
            if student and not student.get("is_active", 1):
                return render_template("student_login.html", error="Your account is inactive. Please contact the admin."), 403
            if STUDENT_EMAIL_VERIFICATION_ENABLED and student and not student.get("email_verified"):
                return render_template("student_login.html", error="Please verify your email before signing in."), 403
            if student and (
                verify_password(password, stored_student_password)
            ):
                session["user_type"] = "student"
                session["user_id"] = student["id"]
                if str(student.get("status", "pending") or "pending").lower() == "approved":
                    return redirect("/student-dashboard" if student_profile_complete(student) else "/complete-profile")
                return redirect("/student-pending")
        except Exception as exc:
            print("Login failed:", exc)

        return render_template("login.html", error="Invalid email or password"), 401

    return render_template("login.html")


@app.route("/student-login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)
            cursor.execute("SELECT * FROM students WHERE LOWER(email)=%s", (email,))
            student = cursor.fetchone()
            cursor.close()
            connection.close()

            stored_student_password = student.get("password", "") if student else ""
            if student and not student.get("is_active", 1):
                return render_template("student_login.html", error="Your account is inactive. Please contact the admin."), 403
            if STUDENT_EMAIL_VERIFICATION_ENABLED and student and not student.get("email_verified"):
                return render_template("student_login.html", error="Please verify your email before signing in."), 403
            if student and (
                verify_password(password, stored_student_password)
            ):
                session["user_type"] = "student"
                session["user_id"] = student["id"]
                if str(student.get("status", "pending") or "pending").lower() == "approved":
                    return redirect("/student-dashboard" if student_profile_complete(student) else "/complete-profile")
                return redirect("/student-pending")
        except Exception as exc:
            print("Student login failed:", exc)

        return render_template("student_login.html", error="Invalid student email or password"), 401

    return render_template("student_login.html")


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)
            admin = find_any_staff(cursor, email)
            cursor.close()
            connection.close()

            stored_admin_password = admin.get("password", "") if admin else ""
            if admin and (
                verify_password(password, stored_admin_password)
            ):
                role_redirects = {
                    "warden": ("warden", "/warden-dashboard"),
                    "laundry_admin": ("laundry_admin", "/laundry-admin-dashboard"),
                    "mess_admin": ("mess_admin", "/mess-warden-dashboard"),
                }
                if admin.get("role") in role_redirects:
                    session["admin_2fa_secret"] = admin.get("two_factor_secret", "")
                    session["admin_2fa_email"] = admin.get("email", "")
                    session["admin_2fa_enabled"] = bool(admin.get("two_factor_enabled", 0))
                    if ADMIN_2FA_ENABLED and bool(admin.get("two_factor_enabled", 0)):
                        session["admin_2fa_id"] = admin["id"]
                        session["admin_2fa_email"] = admin["email"]
                        return redirect("/admin-2fa")
                    session["user_type"], destination = role_redirects[admin["role"]]
                    session["user_id"] = admin["id"]
                    record_admin_access(admin, admin["role"])
                    return redirect(destination)
                if not ADMIN_2FA_ENABLED or not bool(admin.get("two_factor_enabled", 0)):
                    session["admin_2fa_secret"] = admin.get("two_factor_secret", "")
                    session["admin_2fa_email"] = admin.get("email", "")
                    session["admin_2fa_enabled"] = bool(admin.get("two_factor_enabled", 0))
                    session["user_type"] = "admin"
                    session["user_id"] = admin["id"]
                    record_admin_access(admin, admin.get("role", "admin"))
                    return redirect("/admin-dashboard")
                session["admin_2fa_secret"] = admin.get("two_factor_secret", "")
                session["admin_2fa_email"] = admin.get("email", "")
                session["admin_2fa_enabled"] = bool(admin.get("two_factor_enabled", 0))
                session["admin_2fa_id"] = admin["id"]
                return redirect("/admin-2fa")
        except Exception as exc:
            print("Admin login failed:", exc)

        return render_template("admin_login.html", error="Invalid admin email or password"), 401

    return render_template("admin_login.html")


@app.route("/admin-2fa", methods=["GET", "POST"])
def admin_2fa():
    if not session.get("admin_2fa_id"):
        return redirect("/admin-login")
    show_qr = request.args.get("show_qr") == "1"
    if request.method == "POST":
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)
            cursor.execute("SELECT two_factor_secret FROM `admin` WHERE id=%s", (session["admin_2fa_id"],))
            admin = cursor.fetchone()
            cursor.close()
            connection.close()
            secret = (admin or {}).get("two_factor_secret") or session.get("admin_2fa_secret")
            if not secret or not pyotp.TOTP(secret).verify(request.form.get("code", "").strip(), valid_window=1):
                return render_template("admin_2fa.html", error="Invalid authenticator code."), 400
        except Exception as exc:
            print("Admin authenticator verification failed:", exc)
            secret = session.get("admin_2fa_secret")
            if not secret or not pyotp.TOTP(secret).verify(request.form.get("code", "").strip(), valid_window=1):
                return render_template("admin_2fa.html", error="Authenticator verification failed.", show_qr=False), 400
        session["user_type"] = "admin"
        admin_id = session.pop("admin_2fa_id")
        session["user_id"] = admin_id
        record_admin_access({"id": admin_id, "email": session.get("admin_2fa_email", "")}, "admin")
        session.pop("admin_2fa_email", None)
        return redirect("/admin-dashboard")
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT email, two_factor_secret FROM `admin` WHERE id=%s", (session["admin_2fa_id"],))
        admin = cursor.fetchone()
        cursor.close()
        connection.close()
        if not admin:
            return redirect("/admin-login")
        qr_data = None
        if show_qr:
            provisioning_uri = pyotp.TOTP(admin["two_factor_secret"]).provisioning_uri(
                name=admin["email"], issuer_name="Radha Krishan Hostel"
            )
            qr = qrcode.make(provisioning_uri)
            qr_buffer = io.BytesIO()
            qr.save(qr_buffer, format="PNG")
            qr_data = "data:image/png;base64," + base64.b64encode(qr_buffer.getvalue()).decode()
        return render_template("admin_2fa.html", qr_data=qr_data, setup=show_qr, show_qr=show_qr)
    except Exception as exc:
        print("Admin authenticator setup failed:", exc)
        return render_template("admin_2fa.html", error="Authenticator setup is unavailable.", show_qr=False), 500


@app.route("/admin-2fa-settings", methods=["GET", "POST"])
def admin_2fa_settings():
    if session.get("user_type") != "admin":
        return redirect("/admin-login")
    if request.method == "GET":
        return redirect("/admin-dashboard#security")
    admin_id = session.get("user_id")
    enabled = request.form.get("toggle_2fa") == "on"
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        if not admin_id:
            cursor.close(); connection.close(); return redirect("/admin-login")
        cursor.execute("SELECT two_factor_secret FROM `admin` WHERE id=%s", (admin_id,))
        admin = cursor.fetchone()
        if admin and not admin[0]:
            secret = pyotp.random_base32()
            cursor.execute("UPDATE `admin` SET two_factor_secret=%s, two_factor_enabled=%s WHERE id=%s", (secret, int(enabled), admin_id))
        else:
            cursor.execute("UPDATE `admin` SET two_factor_enabled=%s WHERE id=%s", (int(enabled), admin_id))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Admin security toggle failed:", exc)
        flash("Security setting could not be updated.", "danger")
        return redirect("/admin-dashboard#security")
    flash("Security setting updated successfully.", "success")
    if enabled:
        return redirect("/admin-2fa?show_qr=1")
    return redirect("/admin-dashboard#security")


@app.route("/warden-login", methods=["GET", "POST"])
def warden_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)
            warden = find_warden(cursor, email)
            cursor.close()
            connection.close()
            stored_password = warden.get("password", "") if warden else ""
            if warden and (verify_password(password, stored_password)):
                session["user_type"] = "warden"
                session["user_id"] = warden["id"]
                record_admin_access(warden, "warden")
                return redirect("/warden-dashboard")
        except Exception as exc:
            print("Warden login failed:", exc)
        return render_template("warden_login.html", error="Invalid warden email or password"), 401
    return render_template("warden_login.html")


@app.route("/warden-dashboard")
def warden_dashboard():
    if session.get("user_type") != "warden":
        return redirect("/warden-login")

    attendance_date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    try:
        datetime.strptime(attendance_date, "%Y-%m-%d")
    except ValueError:
        attendance_date = datetime.now().strftime("%Y-%m-%d")

    students = []
    leave_requests = []
    day_locked = False
    total_students = 0
    marked_students = 0
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(
            """
            SELECT s.id, s.name, s.email, s.phone, s.hostel, s.block, s.room,
                   s.department, s.year_semester, s.guardian_name, s.guardian_phone,
                   s.guardian_phone_2, s.father_name, s.mother_name,
                   a.status AS attendance_status
            FROM students s
            LEFT JOIN attendance a ON a.student_id=s.id AND a.attendance_date=%s
            WHERE s.status='approved'
            ORDER BY s.name
            """,
            (attendance_date,),
        )
        students = cursor.fetchall()
        cursor.execute("SELECT attendance_date FROM attendance_locks WHERE attendance_date=%s", (attendance_date,))
        day_locked = cursor.fetchone() is not None
        cursor.execute("SELECT COUNT(*) AS total FROM students WHERE status='approved'")
        total_students = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM attendance a JOIN students s ON s.id=a.student_id WHERE s.status='approved' AND a.attendance_date=%s", (attendance_date,))
        marked_students = cursor.fetchone()["total"]
        cursor.execute(
            """
            SELECT l.id, l.leave_type, l.start_date, l.end_date, l.reason,
                   l.destination, l.emergency_contact, l.status, l.admin_note,
                   l.created_at, s.id AS student_id, s.name, s.room, s.guardian_phone
            FROM leave_requests l
            JOIN students s ON s.id=l.student_id
            ORDER BY l.created_at DESC
            """
        )
        leave_requests = cursor.fetchall()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Warden dashboard load failed:", exc)

    return render_template(
        "warden_dashboard.html",
        students=students,
        leave_requests=leave_requests,
        attendance_date=attendance_date,
        day_locked=day_locked,
        all_attendance_marked=total_students > 0 and marked_students == total_students,
    )


@app.route("/warden-attendance", methods=["POST"])
def warden_attendance():
    if session.get("user_type") != "warden":
        return redirect("/warden-login")

    student_id = request.form.get("student_id")
    attendance_date = request.form.get("attendance_date", datetime.now().strftime("%Y-%m-%d"))
    status = request.form.get("status", "present").lower()
    if status not in {"present", "absent", "late"}:
        status = "present"
    try:
        datetime.strptime(attendance_date, "%Y-%m-%d")
    except ValueError:
        attendance_date = datetime.now().strftime("%Y-%m-%d")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM students WHERE id=%s AND status='approved'", (student_id,))
        if cursor.fetchone():
            cursor.execute(
                "SELECT id FROM attendance WHERE student_id=%s AND attendance_date=%s",
                (student_id, attendance_date),
            )
            existing = cursor.fetchone()
            cursor.execute("SELECT attendance_date FROM attendance_locks WHERE attendance_date=%s", (attendance_date,))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return redirect(f"/warden-dashboard?date={attendance_date}")
            if not existing:
                cursor.execute(
                    "INSERT INTO attendance (student_id, attendance_date, status) VALUES (%s, %s, %s)",
                    (student_id, attendance_date, status),
                )
            connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Warden attendance save failed:", exc)

    return redirect(f"/warden-dashboard?date={attendance_date}")


@app.route("/warden-lock-attendance", methods=["POST"])
def warden_lock_attendance():
    if session.get("user_type") != "warden":
        return redirect("/admin-login")
    attendance_date = request.form.get("attendance_date", datetime.now().strftime("%Y-%m-%d"))
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM students WHERE status='approved'")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM attendance a JOIN students s ON s.id=a.student_id WHERE s.status='approved' AND a.attendance_date=%s", (attendance_date,))
        marked = cursor.fetchone()[0]
        if total > 0 and marked == total:
            cursor.execute("INSERT IGNORE INTO attendance_locks (attendance_date, locked_by) VALUES (%s, %s)", (attendance_date, session["user_id"]))
            connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Attendance lock failed:", exc)
    return redirect(f"/warden-dashboard?date={attendance_date}")


@app.route("/mess-warden-login", methods=["GET", "POST"])
def mess_warden_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)
            staff = find_staff_role(cursor, email, "mess_admin")
            cursor.close()
            connection.close()
            stored_password = staff.get("password", "") if staff else ""
            if staff and (verify_password(password, stored_password)):
                session["user_type"] = "mess_admin"
                session["user_id"] = staff["id"]
                record_admin_access(staff, "mess_admin")
                return redirect("/mess-warden-dashboard")
        except Exception as exc:
            print("Mess Warden login failed:", exc)
        return render_template("staff_login.html", title="Mess Warden Login", endpoint="/mess-warden-login", error="Invalid Mess Warden email or password"), 401
    return render_template("staff_login.html", title="Mess Warden Login", endpoint="/mess-warden-login")


@app.route("/mess-warden-dashboard")
def mess_warden_dashboard():
    if session.get("user_type") != "mess_admin":
        return redirect("/mess-warden-login")
    students = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(
            """
                 SELECT id, name, photo_url
            FROM students
            WHERE status='approved'
            ORDER BY name
            """
        )
        students = cursor.fetchall()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Mess Warden dashboard load failed:", exc)
    return render_template("mess_warden_dashboard.html", students=students)


@app.route("/laundry-admin-login", methods=["GET", "POST"])
def laundry_admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)
            staff = find_staff_role(cursor, email, "laundry_admin")
            cursor.close()
            connection.close()
            stored_password = staff.get("password", "") if staff else ""
            if staff and (verify_password(password, stored_password)):
                session["user_type"] = "laundry_admin"
                session["user_id"] = staff["id"]
                record_admin_access(staff, "laundry_admin")
                return redirect("/laundry-admin-dashboard")
        except Exception as exc:
            print("Laundry Admin login failed:", exc)
        return render_template("staff_login.html", title="Laundry Admin Login", endpoint="/laundry-admin-login", error="Invalid Laundry Admin email or password"), 401
    return render_template("staff_login.html", title="Laundry Admin Login", endpoint="/laundry-admin-login")


@app.route("/laundry-admin-dashboard")
def laundry_admin_dashboard():
    if session.get("user_type") != "laundry_admin":
        return redirect("/laundry-admin-login")
    laundry_students = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(
            """
                 SELECT s.id AS student_id, s.name, s.email, s.phone, s.hostel, s.room,
                     s.college_id_url, l.id AS token_id, l.token_no,
                   l.verification_code, l.out_code, l.bag_in_at, l.bag_out_at, l.token_date, l.token_time, l.status,
                   l.valid_until
            FROM students s
            LEFT JOIN laundry_tokens l ON l.id=(
                SELECT latest.id FROM laundry_tokens latest
                WHERE latest.student_id=s.id ORDER BY latest.id DESC LIMIT 1
            )
            WHERE s.status='approved'
            ORDER BY s.name
            """
        )
        laundry_students = cursor.fetchall()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Laundry Admin dashboard load failed:", exc)
    return render_template("laundry_admin_dashboard.html", laundry_students=laundry_students)


@app.route("/laundry-verify", methods=["POST"])
def laundry_verify():
    if session.get("user_type") != "laundry_admin":
        return redirect("/laundry-admin-login")
    token_id = request.form.get("token_id")
    submitted_code = request.form.get("verification_code", "").strip()
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT verification_code, status FROM laundry_tokens WHERE id=%s", (token_id,))
        token = cursor.fetchone()
        if token and token.get("verification_code") and hmac.compare_digest(str(token["verification_code"]), submitted_code):
            out_code = f"{secrets.randbelow(900000) + 100000:06d}"
            cursor.execute("UPDATE laundry_tokens SET status='picked_up', out_code=%s, bag_in_at=NOW() WHERE id=%s", (out_code, token_id))
            connection.commit()
            flash("Bag code verified. Student out code has been generated.", "success")
        else:
            flash("Verification code does not match. Laundry token remains invalid.", "danger")
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Laundry verification failed:", exc)
        flash("Laundry verification could not be completed.", "danger")
    return redirect("/laundry-admin-dashboard")


@app.route("/laundry-out-verify", methods=["POST"])
def laundry_out_verify():
    if session.get("user_type") != "laundry_admin":
        return redirect("/admin-login")
    token_id = request.form.get("token_id")
    submitted_code = request.form.get("out_code", "").strip()
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT out_code, status FROM laundry_tokens WHERE id=%s", (token_id,))
        token = cursor.fetchone()
        if token and token.get("status") == "picked_up" and token.get("out_code") and hmac.compare_digest(str(token["out_code"]), submitted_code):
            cursor.execute("UPDATE laundry_tokens SET status='out_verified' WHERE id=%s", (token_id,))
            connection.commit()
            flash("Out code verified. Bag can now be handed to the student.", "success")
        else:
            flash("Out code does not match. Bag cannot be handed over.", "danger")
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Laundry out-code verification failed:", exc)
        flash("Out-code verification could not be completed.", "danger")
    return redirect("/laundry-admin-dashboard")


@app.route("/admin-attendance-action", methods=["POST"])
def admin_attendance_action():
    if session.get("user_type") != "admin":
        return redirect("/admin-login")
    attendance_id = request.form.get("attendance_id")
    status = request.form.get("status", "present")
    if status not in {"present", "absent", "late"}:
        status = "present"
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE attendance SET status=%s WHERE id=%s", (status, attendance_id))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Admin attendance update failed:", exc)
    return redirect("/admin-dashboard")


@app.route("/admin-attendance-save", methods=["POST"])
def admin_attendance_save():
    if session.get("user_type") != "admin":
        return redirect("/admin-login")
    attendance_date = request.form.get("attendance_date", datetime.now().strftime("%Y-%m-%d"))
    student_id = request.form.get("student_id")
    status = request.form.get("status", "present")
    if status not in {"present", "absent", "late"}:
        status = "present"
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM attendance WHERE student_id=%s AND attendance_date=%s", (student_id, attendance_date))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("UPDATE attendance SET status=%s WHERE id=%s", (status, existing[0]))
        else:
            cursor.execute(
                "INSERT INTO attendance (student_id, attendance_date, status) VALUES (%s, %s, %s)",
                (student_id, attendance_date, status),
            )
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Admin attendance save failed:", exc)
    return redirect(f"/admin-dashboard?attendance_date={attendance_date}#attendance-records")


@app.route("/laundry-pickup", methods=["POST"])
def laundry_pickup():
    if session.get("user_type") != "laundry_admin":
        return redirect("/admin-login")
    token_id = request.form.get("token_id")
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE laundry_tokens SET status='handed_over', bag_out_at=NOW() WHERE id=%s AND status='out_verified'", (token_id,))
        connection.commit()
        cursor.close()
        connection.close()
        flash("Laundry bag marked as picked up.", "success")
    except Exception as exc:
        print("Laundry pickup failed:", exc)
        flash("Bag pickup could not be recorded.", "danger")
    return redirect("/laundry-admin-dashboard")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100),
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    hostel VARCHAR(100),
                    block VARCHAR(100),
                    room VARCHAR(20),
                    password VARCHAR(255),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    rent_paid VARCHAR(10) NOT NULL DEFAULT 'no',
                    rent_amount DECIMAL(10,2) NOT NULL DEFAULT 114000.00,
                    rent_paid_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00
                )
                """
            )
            try:
                cursor.execute(
                    """
                    ALTER TABLE students
                    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    """
                )
            except Exception:
                pass
            try:
                cursor.execute(
                    """
                    ALTER TABLE students
                    ADD COLUMN rent_paid VARCHAR(10) NOT NULL DEFAULT 'no'
                    """
                )
            except Exception:
                pass
            try:
                cursor.execute(
                    """
                    ALTER TABLE students
                    ADD COLUMN rent_amount DECIMAL(10,2) NOT NULL DEFAULT 114000.00
                    """
                )
            except Exception:
                pass
            try:
                cursor.execute(
                    """
                    ALTER TABLE students
                    ADD COLUMN rent_paid_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00
                    """
                )
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE students ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0")
            except Exception:
                pass
            email = request.form.get("email", "").strip().lower()
            hostel = request.form.get("hostel", "").strip()
            floor = request.form.get("block", "").strip()
            room_number = request.form.get("room", "").strip()
            cursor.execute(
                "SELECT capacity, status FROM rooms WHERE hostel=%s AND block=%s AND room=%s",
                (hostel, floor, room_number),
            )
            selected_room = cursor.fetchone()
            if not selected_room or selected_room[1] != "available":
                cursor.close()
                connection.close()
                return render_template("registration.html", error="Please select an available room.", rooms=get_registration_rooms()), 400
            cursor.execute(
                "SELECT COUNT(*) FROM students WHERE hostel=%s AND block=%s AND room=%s AND status IN ('pending', 'approved')",
                (hostel, floor, room_number),
            )
            if cursor.fetchone()[0] >= selected_room[0]:
                cursor.close()
                connection.close()
                return render_template("registration.html", error="That room is already full. Please select another room.", rooms=get_registration_rooms()), 400
            cursor.execute("SELECT id FROM students WHERE LOWER(email)=%s", (email,))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return render_template(
                    "registration.html",
                    error="This email is already registered. Please log in instead, or use the Forgot Password link.",
                    rooms=get_registration_rooms(),
                ), 400

            name = request.form.get("name", "").strip()[:100]
            phone = request.form.get("phone", "").strip()[:20]
            raw_password = request.form.get("password", "")
            if not name or not email or not raw_password:
                cursor.close()
                connection.close()
                return render_template(
                    "registration.html",
                    error="Name, email and password are all required.",
                    rooms=get_registration_rooms(),
                ), 400
            if len(raw_password) < 6:
                cursor.close()
                connection.close()
                return render_template(
                    "registration.html",
                    error="Password must be at least 6 characters long.",
                    rooms=get_registration_rooms(),
                ), 400

            otp = create_otp()
            cursor.execute(
                """
                INSERT INTO students (name, email, phone, hostel, block, room, password, rent_paid, rent_amount, rent_paid_amount, email_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name,
                    email,
                    phone,
                    hostel,
                    floor,
                    room_number,
                    hash_password(raw_password),
                    "no",
                    HOSTEL_FEE,
                    "0.00",
                    1 if not STUDENT_EMAIL_VERIFICATION_ENABLED else 0,
                ),
            )
            connection.commit()
            cursor.close()
            connection.close()
            if STUDENT_EMAIL_VERIFICATION_ENABLED:
                session["email_verification_email"] = email
                session["email_verification_otp"] = otp
                session["email_verification_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                send_otp_email(email, otp, "email verification")
                return render_template("verify_email.html", email=email)
            return redirect("/student-login")
        except Exception as exc:
            print("Registration failed:", exc)
            return render_template(
                "registration.html",
                error="Registration failed. Please try again.",
                rooms=get_registration_rooms(),
            ), 400

    return render_template("registration.html", rooms=get_registration_rooms())


@app.route("/verify-email", methods=["POST"])
def verify_email():
    email = request.form.get("email", "").strip().lower()
    otp = request.form.get("otp", "").strip()
    if email != session.get("email_verification_email") or not otp_is_valid(
        session.get("email_verification_otp", ""),
        session.get("email_verification_time", ""),
        otp,
    ):
        return render_template("verify_email.html", email=email, error="Invalid or expired verification code."), 400

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE students SET email_verified=1 WHERE LOWER(email)=LOWER(%s)", (email,))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Email verification failed:", exc)
        return render_template("verify_email.html", email=email, error="Email could not be verified."), 400

    session.pop("email_verification_email", None)
    session.pop("email_verification_otp", None)
    session.pop("email_verification_time", None)
    return redirect("/student-login?verified=1")


def get_registration_rooms():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(
            """
            SELECT r.hostel, r.block, r.room, r.capacity, r.status,
                   COUNT(CASE WHEN s.status IN ('pending', 'approved') THEN 1 END) AS occupants
            FROM rooms r
            LEFT JOIN students s ON s.hostel=r.hostel AND s.block=r.block AND s.room=r.room
            GROUP BY r.id, r.hostel, r.block, r.room, r.capacity, r.status
            ORDER BY FIELD(r.block, 'Basement', '1st Floor', '2nd Floor', '3rd Floor'), r.room
            """
        )
        rooms = cursor.fetchall()
        cursor.close()
        connection.close()
        return [room for room in rooms if room["status"] == "available" and room["occupants"] < room["capacity"]]
    except Exception as exc:
        print("Registration room lookup failed:", exc)
        return []


@app.route("/student-pending")
def student_pending():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM students WHERE id=%s", (session.get("user_id"),))
        student = cursor.fetchone()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Student pending page load failed:", exc)
        student = None

    can_access, message = can_access_student_dashboard(student)
    if can_access:
        return redirect("/student-dashboard")

    return render_template("student_pending.html", student=student, message=message)


@app.route("/student-approved")
def student_approved():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM students WHERE id=%s", (session.get("user_id"),))
        student = cursor.fetchone()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Student approved page load failed:", exc)
        student = None

    if not student or str(student.get("status", "pending") or "pending").lower() != "approved":
        return redirect("/student-pending")
    if not student_profile_complete(student):
        return redirect("/complete-profile")

    return render_template("student_approved.html", student=student)


@app.route("/complete-profile", methods=["GET", "POST"])
def complete_profile():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM students WHERE id=%s", (session.get("user_id"),))
        student = cursor.fetchone()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Profile completion load failed:", exc)
        return render_template("student_complete_profile.html", student=None, error="Unable to load your profile."), 500

    if not student or str(student.get("status", "pending") or "pending").lower() != "approved":
        return redirect("/student-pending")
    if request.method == "GET":
        if student_profile_complete(student):
            return redirect("/student-dashboard")
        return render_template("student_complete_profile.html", student=student)

    fields = {
        "name": request.form.get("name", "").strip(),
        "phone": request.form.get("phone", "").strip(),
        "college": request.form.get("college", "").strip(),
        "course": request.form.get("course", "").strip(),
        "department": request.form.get("department", "").strip(),
        "year_semester": request.form.get("year_semester", "").strip(),
        "guardian_name": request.form.get("guardian_name", "").strip(),
        "guardian_phone": request.form.get("guardian_phone", "").strip(),
        "guardian_phone_2": request.form.get("guardian_phone_2", "").strip(),
        "father_name": request.form.get("father_name", "").strip(),
        "mother_name": request.form.get("mother_name", "").strip(),
        "home_address": request.form.get("home_address", "").strip(),
        "address_city": request.form.get("address_city", "").strip(),
        "address_district": request.form.get("address_district", "").strip(),
        "address_state": request.form.get("address_state", "").strip(),
        "address_pincode": request.form.get("address_pincode", "").strip(),
        "address_country": request.form.get("address_country", "").strip(),
        "emergency_contact": request.form.get("emergency_contact", "").strip(),
        "aadhaar": request.form.get("aadhaar", "").strip(),
        "blood_group": request.form.get("blood_group", "").strip(),
    }
    missing = [label for label, value in fields.items() if not value]
    photo = request.files.get("photo")
    college_id = request.files.get("college_id")
    if missing or (not student.get("photo_url") and (not photo or not photo.filename)):
        return render_template(
            "student_complete_profile.html",
            student={**student, **fields},
            error="Please complete every field and upload your profile photo.",
        ), 400

    try:
        upload_dir = os.path.join(BASE_DIR, "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        photo_url = student.get("photo_url") or ""
        if not photo_url and photo and photo.filename:
            photo_name = f"{secrets.token_hex(8)}_{secure_filename(photo.filename)}"
            photo.save(os.path.join(upload_dir, f"student_{student['id']}_{photo_name}"))
            photo_url = f"/uploads/student_{student['id']}_{photo_name}"
        college_id_url = student.get("college_id_url") or ""
        if college_id and college_id.filename:
            college_id_name = f"{secrets.token_hex(8)}_{secure_filename(college_id.filename)}"
            college_id.save(os.path.join(upload_dir, f"college_id_{student['id']}_{college_id_name}"))
            college_id_url = f"/uploads/college_id_{student['id']}_{college_id_name}"

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE students
            SET name=%s, phone=%s, college=%s, course=%s, department=%s, year_semester=%s,
                guardian_name=%s, guardian_phone=%s, guardian_phone_2=%s, father_name=%s, mother_name=%s, home_address=%s,
                address_city=%s, address_district=%s, address_state=%s, address_pincode=%s, address_country=%s,
                emergency_contact=%s, aadhaar=%s,
                blood_group=%s, photo_url=%s, college_id_url=%s
            WHERE id=%s
            """,
            (*fields.values(), photo_url, college_id_url, student["id"]),
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("Profile completed successfully. Welcome to your dashboard.", "success")
        return redirect("/student-dashboard")
    except Exception as exc:
        print("Profile completion save failed:", exc)
        return render_template("student_complete_profile.html", student={**student, **fields}, error="Profile could not be saved. Please try again."), 500


@app.route("/student-dashboard")
def student_dashboard():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM students WHERE id=%s", (session.get("user_id"),))
        student = cursor.fetchone()
        if student:
            cursor.execute("SELECT category, subject, description, status, created_at FROM complaints WHERE student_id=%s ORDER BY created_at DESC", (student["id"],))
            complaints = cursor.fetchall()
            cursor.execute("SELECT id, amount, utr, payment_date, payment_method, notes, screenshot_url, status, admin_note, created_at FROM payment_submissions WHERE student_id=%s ORDER BY created_at DESC", (student["id"],))
            payment_submissions = cursor.fetchall()
            cursor.execute("SELECT token_no, verification_code, out_code, bag_in_at, bag_out_at, token_date, token_time, status, valid_until FROM laundry_tokens WHERE student_id=%s ORDER BY created_at DESC LIMIT 1", (student["id"],))
            laundry_token = cursor.fetchone()
            token_expired = True
            if laundry_token and laundry_token.get("valid_until"):
                try:
                    token_expired = datetime.strptime(str(laundry_token["valid_until"]), "%Y-%m-%d").date() < datetime.now().date()
                except ValueError:
                    token_expired = True
            if not laundry_token or token_expired:
                now = datetime.now()
                token_no = generate_laundry_token_number(cursor)
                verification_code = f"{secrets.randbelow(900000) + 100000:06d}"
                cursor.execute(
                    "INSERT INTO laundry_tokens (student_id, token_no, verification_code, token_date, token_time, status, valid_until) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        student["id"],
                        token_no,
                        verification_code,
                        now.strftime("%d %b %Y"),
                        now.strftime("%I:%M %p"),
                        "pending_verification",
                        (now + timedelta(days=7)).strftime("%Y-%m-%d"),
                    ),
                )
                connection.commit()
                cursor.execute("SELECT token_no, verification_code, out_code, bag_in_at, bag_out_at, token_date, token_time, status, valid_until FROM laundry_tokens WHERE student_id=%s ORDER BY created_at DESC LIMIT 1", (student["id"],))
                laundry_token = cursor.fetchone()
            elif not laundry_token.get("verification_code"):
                verification_code = f"{secrets.randbelow(900000) + 100000:06d}"
                cursor.execute(
                    "UPDATE laundry_tokens SET verification_code=%s WHERE student_id=%s AND token_no=%s",
                    (verification_code, student["id"], laundry_token["token_no"]),
                )
                connection.commit()
                laundry_token["verification_code"] = verification_code
            cursor.execute("SELECT attendance_date, status FROM attendance WHERE student_id=%s ORDER BY id DESC LIMIT 10", (student["id"],))
            attendance_records = cursor.fetchall()
            cursor.execute("SELECT * FROM leave_requests WHERE student_id=%s ORDER BY created_at DESC", (student["id"],))
            leave_requests = cursor.fetchall()
            cursor.execute("SELECT title, message, image_url, created_at FROM notifications WHERE student_id IS NULL OR student_id=%s ORDER BY created_at DESC", (student["id"],))
            notifications = cursor.fetchall()
        else:
            complaints = []
            payment_submissions = []
            laundry_token = None
            attendance_records = []
            leave_requests = []
            notifications = []
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Student dashboard load failed:", exc)
        student = None
        complaints = []
        laundry_token = None
        attendance_records = []
        leave_requests = []
        notifications = []
        payment_submissions = []

    can_access, message = can_access_student_dashboard(student)
    if not can_access:
        return render_template("student_pending.html", student=student, message=message)
    if not student_profile_complete(student):
        return redirect("/complete-profile")

    fee_summary = get_student_fee_summary(student)
    dashboard_context = build_student_dashboard_context(
        student,
        complaints=complaints,
        laundry_token=laundry_token,
        attendance_records=attendance_records,
        fee_summary=fee_summary,
        college_id_url=student.get("college_id_url") if student else "",
        notifications=notifications,
        payment_submissions=payment_submissions,
    )
    dashboard_context["attendance"] = attendance_records if attendance_records else dashboard_context.get("attendance", [])
    dashboard_context["leave_requests"] = leave_requests
    dashboard_context["notifications"] = notifications if notifications is not None else dashboard_context.get("notifications", [])
    return render_template("student_dashboard.html", student=student, dashboard_context=dashboard_context)


@app.route("/student-leave-request", methods=["POST"])
def student_leave_request():
    if session.get("user_type") != "student":
        return redirect("/student-login")
    leave_type = request.form.get("leave_type", "holiday").strip()
    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()
    reason = request.form.get("reason", "").strip()
    if not start_date or not end_date or not reason:
        flash("Please fill the leave dates and reason.", "danger")
        return redirect("/student-dashboard")
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO leave_requests (student_id, leave_type, start_date, end_date, reason, destination, emergency_contact) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (session.get("user_id"), leave_type, start_date, end_date, reason, request.form.get("destination", "").strip(), request.form.get("emergency_contact", "").strip()),
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("Leave request sent to admin for approval.", "success")
    except Exception as exc:
        print("Leave request failed:", exc)
        flash("Leave request could not be submitted.", "danger")
    return redirect("/student-dashboard")


@app.route("/student-payment-submit", methods=["POST"])
def student_payment_submit():
    if session.get("user_type") != "student":
        return redirect("/student-login")
    screenshot = request.files.get("screenshot")
    utr = request.form.get("utr", "").strip()
    payment_method = request.form.get("payment_method", "UPI").strip() or "UPI"
    notes = request.form.get("notes", "").strip()
    payment_date = request.form.get("payment_date", "").strip()
    try:
        amount = float(request.form.get("amount", "0"))
        datetime.strptime(payment_date, "%Y-%m-%d")
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0 or not utr or not payment_date:
        flash("Please enter a valid amount, payment date, and UTR number.", "danger")
        return redirect("/student-dashboard#payments")
    try:
        screenshot_url = ""
        if screenshot and screenshot.filename:
            extension = Path(screenshot.filename).suffix.lower()
            if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
                flash("Payment screenshot must be an image file.", "danger")
                return redirect("/student-dashboard#payments")
            upload_dir = BASE_DIR / "uploads"
            upload_dir.mkdir(exist_ok=True)
            filename = f"payment_{session.get('user_id')}_{secrets.token_hex(8)}{extension}"
            screenshot.save(upload_dir / filename)
            screenshot_url = f"/uploads/{filename}"
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO payment_submissions (student_id, amount, utr, payment_date, payment_method, notes, screenshot_url) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (session.get("user_id"), amount, utr, payment_date, payment_method, notes, screenshot_url),
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("Payment details submitted. Admin will verify your fee payment.", "success")
    except Exception as exc:
        print("Payment submission failed:", exc)
        flash("Payment details could not be submitted.", "danger")
    return redirect("/student-dashboard#payments")


@app.route("/withdraw-application", methods=["POST"])
def withdraw_application():
    if session.get("user_type") != "student":
        return redirect("/student-login")
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE students SET status='withdrawn' WHERE id=%s AND status='pending'",
            (session.get("user_id"),),
        )
        connection.commit()
        withdrawn = cursor.rowcount == 1
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Application withdrawal failed:", exc)
        flash("Your application could not be withdrawn. Please try again.", "danger")
        return redirect("/student-dashboard")
    if not withdrawn:
        flash("Only pending applications can be withdrawn.", "warning")
        return redirect("/student-dashboard")
    session.clear()
    return render_template("withdrawn.html")


@app.route("/student-complaint", methods=["POST"])
def student_complaint():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO complaints (student_id, category, subject, description, status) VALUES (%s, %s, %s, %s, %s)",
            (
                session.get("user_id"),
                request.form.get("category", "Other"),
                request.form.get("subject", "General issue"),
                request.form.get("description", ""),
                "pending",
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Complaint submission failed:", exc)

    return redirect("/student-dashboard")


@app.route("/mark-attendance", methods=["POST"])
def mark_attendance():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT attendance_date FROM attendance_locks WHERE attendance_date=%s", (today,))
        day_locked = cursor.fetchone()
        cursor.execute("SELECT id FROM attendance WHERE student_id=%s AND attendance_date=%s", (session.get("user_id"), today))
        existing = cursor.fetchone()
        if not existing and not day_locked:
            cursor.execute("INSERT INTO attendance (student_id, attendance_date, status) VALUES (%s, %s, %s)", (session.get("user_id"), today, "present"))
            connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Attendance marking failed:", exc)

    return redirect("/student-dashboard")


@app.route("/edit-profile", methods=["POST"])
def edit_profile():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE students
            SET name=%s, phone=%s, hostel=%s, block=%s, room=%s, college=%s, course=%s, department=%s,
                year_semester=%s, guardian_name=%s, guardian_phone=%s, guardian_phone_2=%s, father_name=%s, mother_name=%s, home_address=%s,
                address_city=%s, address_district=%s, address_state=%s, address_pincode=%s, address_country=%s,
                emergency_contact=%s, aadhaar=%s,
                bed_number=%s, blood_group=%s
            WHERE id=%s
            """,
            (
                request.form.get("name", ""),
                request.form.get("phone", ""),
                request.form.get("hostel", ""),
                request.form.get("block", ""),
                request.form.get("room", ""),
                request.form.get("college", ""),
                request.form.get("course", ""),
                request.form.get("department", ""),
                request.form.get("year_semester", ""),
                request.form.get("guardian_name", ""),
                request.form.get("guardian_phone", ""),
                request.form.get("guardian_phone_2", ""),
                request.form.get("father_name", ""),
                request.form.get("mother_name", ""),
                request.form.get("home_address", ""),
                request.form.get("address_city", ""),
                request.form.get("address_district", ""),
                request.form.get("address_state", ""),
                request.form.get("address_pincode", ""),
                request.form.get("address_country", ""),
                request.form.get("emergency_contact", ""),
                request.form.get("aadhaar", ""),
                request.form.get("bed_number", ""),
                request.form.get("blood_group", ""),
                session.get("user_id"),
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Profile update failed:", exc)

    return redirect("/student-dashboard")


@app.route("/upload-profile-photo", methods=["POST"])
def upload_profile_photo():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        import mysql.connector

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT photo_url FROM students WHERE id=%s", (session.get('user_id'),))
        existing_student = cursor.fetchone()
        cursor.close()
        connection.close()
        if existing_student and existing_student.get("photo_url"):
            flash("Your profile photo is already saved and cannot be changed.", "warning")
            return redirect("/student-dashboard")

        if 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename:
                upload_dir = os.path.join(BASE_DIR, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"{secrets.token_hex(8)}_{secure_filename(photo.filename)}"
                photo_path = os.path.join(upload_dir, f"student_{session.get('user_id')}_{filename}")
                photo.save(photo_path)
                relative_path = f"/uploads/student_{session.get('user_id')}_{filename}"
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute("UPDATE students SET photo_url=%s WHERE id=%s", (relative_path, session.get('user_id')))
                connection.commit()
                cursor.close()
                connection.close()
                flash("Profile photo uploaded successfully.", "success")
    except Exception as exc:
        print("Profile photo upload failed:", exc)
        flash("Profile photo upload failed. Please try again.", "danger")

    return redirect("/student-dashboard")


@app.route("/upload-college-id", methods=["POST"])
def upload_college_id():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        import mysql.connector

        if 'college_id' in request.files:
            uploaded_file = request.files['college_id']
            if uploaded_file.filename:
                upload_dir = os.path.join(BASE_DIR, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                filename = f"{secrets.token_hex(8)}_{secure_filename(uploaded_file.filename)}"
                save_path = os.path.join(upload_dir, f"college_id_{session.get('user_id')}_{filename}")
                uploaded_file.save(save_path)
                relative_path = f"/uploads/college_id_{session.get('user_id')}_{filename}"
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute("UPDATE students SET college_id_url=%s WHERE id=%s", (relative_path, session.get('user_id')))
                connection.commit()
                cursor.close()
                connection.close()
                flash("College ID uploaded successfully.", "success")
    except Exception as exc:
        print("College ID upload failed:", exc)
        flash("College ID upload failed. Please try again.", "danger")

    return redirect("/student-dashboard")


@app.route("/download-fee-receipt")
def download_fee_receipt():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE id=%s", (session.get("user_id"),))
        student = cursor.fetchone()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Fee receipt lookup failed:", exc)
        student = None

    fee_summary = get_student_fee_summary(student)
    receipt_path = os.path.join(BASE_DIR, "temp_receipt.pdf")
    receipt_no = f"HR{session.get('user_id') or 0:03d}"
    write_fee_receipt_pdf(receipt_path, student, fee_summary, receipt_no)
    return send_file(receipt_path, as_attachment=True, download_name="fee_receipt.pdf")


@app.route("/download-college-id-card")
def download_college_id_card():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE id=%s", (session.get("user_id"),))
        student = cursor.fetchone()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("College ID lookup failed:", exc)
        student = None

    if student and student.get("college_id_url"):
        file_path = os.path.join(BASE_DIR, student.get("college_id_url").lstrip("/"))
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name='college_id_card.pdf')

    card_lines = [
        "College ID Card",
        f"Student Name: {student.get('name') if student else 'Student'}",
        f"College: {student.get('college') if student else 'ABC University'}",
        f"Course: {student.get('course') if student else '-'}",
        f"Department: {student.get('department') if student else '-'}",
        f"Student ID: {session.get('user_id')}",
    ]
    receipt_path = os.path.join(BASE_DIR, 'college_id_card.pdf')
    write_simple_pdf(receipt_path, card_lines)
    return send_file(receipt_path, as_attachment=True, download_name='college_id_card.pdf')


@app.route("/generate-laundry-token", methods=["POST"])
def generate_laundry_token():
    if session.get("user_type") != "student":
        return redirect("/student-login")

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        student_id = session.get("user_id")
        token_no = generate_laundry_token_number(cursor)
        verification_code = f"{secrets.randbelow(900000) + 100000:06d}"
        now = datetime.now()
        cursor.execute(
            "INSERT INTO laundry_tokens (student_id, token_no, verification_code, token_date, token_time, status, valid_until) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                student_id,
                token_no,
                verification_code,
                now.strftime("%d %b %Y"),
                now.strftime("%I:%M %p"),
                "pending_verification",
                (now + timedelta(days=7)).strftime("%Y-%m-%d"),
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Laundry token generation failed:", exc)

    return redirect("/student-dashboard")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        delivery_method = request.form.get("delivery_method", "email").strip().lower()
        otp = f"{secrets.randbelow(1000000):06d}"
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True, buffered=True)
            cursor.execute("SELECT id, phone FROM students WHERE LOWER(email)=LOWER(%s)", (email,))
            student = cursor.fetchone()
            cursor.close()
            connection.close()
        except Exception as exc:
            print("Password reset lookup failed:", exc)
            student = None

        if student:
            session["password_reset_email"] = email
            session["password_reset_otp"] = otp
            session["password_reset_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if delivery_method == "sms":
                delivered = bool(student.get("phone")) and send_otp_sms(student["phone"], otp, "password reset")
                delivery_label = "registered mobile number"
            else:
                delivered = send_otp_email(email, otp, "password reset")
                delivery_label = "registered email"
            if delivered:
                return render_template("forgot_password.html", sent=True, email=email, delivery_label=delivery_label)
            return render_template(
                "forgot_password.html",
                error=f"OTP could not be sent to the {delivery_label}. Please check the delivery settings and try again.",
            ), 503

        return render_template("forgot_password.html", error="No student account found for that email."), 404

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["POST"])
def reset_password():
    email = request.form.get("email", "").strip().lower()
    otp = request.form.get("otp", "").strip()
    new_password = request.form.get("password", "")
    stored_email = session.get("password_reset_email", "")
    stored_otp = session.get("password_reset_otp", "")
    stored_time = session.get("password_reset_time", "")

    if email != stored_email or not otp_is_valid(stored_otp, stored_time, otp):
        return render_template("forgot_password.html", error="Invalid or expired 6-digit OTP. Please request a new code."), 400

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE students SET password=%s WHERE LOWER(email)=LOWER(%s)", (hash_password(new_password), email))
        connection.commit()
        cursor.close()
        connection.close()
        session.pop("password_reset_email", None)
        session.pop("password_reset_otp", None)
        session.pop("password_reset_time", None)
    except Exception as exc:
        print("Password reset failed:", exc)
        return render_template("forgot_password.html", error="Password could not be changed."), 400

    return render_template("forgot_password.html", success="Password changed successfully. You can now sign in.")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/admin-dashboard")
def admin_dashboard():
    if session.get("user_type") != "admin":
        return redirect("/admin-login")

    search_query = request.args.get("search", "").strip().lower()
    attendance_date = request.args.get("attendance_date", datetime.now().strftime("%Y-%m-%d"))
    try:
        datetime.strptime(attendance_date, "%Y-%m-%d")
    except ValueError:
        attendance_date = datetime.now().strftime("%Y-%m-%d")
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT COUNT(*) AS count FROM students")
        student_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) AS count FROM students WHERE status='pending'")
        pending_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) AS count FROM students WHERE status='approved'")
        approved_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) AS count FROM students WHERE status='rejected'")
        rejected_count = cursor.fetchone()["count"]
        cursor.execute(
            "SELECT COUNT(*) AS count FROM rooms"
        )
        room_count = cursor.fetchone()["count"]
        cursor.execute(
            "SELECT COUNT(DISTINCT CONCAT(hostel, '|', block, '|', room)) AS count FROM students"
        )
        total_rooms = cursor.fetchone()["count"]
        cursor.execute(
            "SELECT COUNT(DISTINCT CONCAT(hostel, '|', block, '|', room)) AS count FROM students WHERE status='approved'"
        )
        occupied_rooms = cursor.fetchone()["count"]
        available_rooms = max(total_rooms - occupied_rooms, 0)
        cursor.execute(
            "SELECT COUNT(*) AS count FROM students WHERE status='approved' AND rent_paid='no'"
        )
        pending_rent_payments = cursor.fetchone()["count"]
        cursor.execute(
            "SELECT COALESCE(SUM(rent_amount), 0) AS total_expected, COALESCE(SUM(rent_paid_amount), 0) AS total_paid, COALESCE(SUM(GREATEST(rent_amount - rent_paid_amount, 0)), 0) AS total_pending FROM students"
        )
        rent_totals = cursor.fetchone()
        cursor.execute(
            "SELECT COUNT(*) AS count FROM students WHERE rent_paid='yes'"
        )
        fully_paid_students = cursor.fetchone()["count"]
        cursor.execute(
            "SELECT COUNT(*) AS count FROM students WHERE rent_paid='no' AND rent_paid_amount > 0"
        )
        partially_paid_students = cursor.fetchone()["count"]
        cursor.execute(
            "SELECT COUNT(*) AS count FROM students WHERE rent_paid='no' AND rent_paid_amount = 0"
        )
        unpaid_students = cursor.fetchone()["count"]
        total_rent_paid = float(rent_totals["total_paid"] or 0)
        total_rent_pending = float(rent_totals["total_pending"] or 0)
        total_expected_fee = float(rent_totals["total_expected"] or 0)
        cursor.execute(
            "SELECT MONTH(created_at) AS month, COUNT(*) AS count FROM students WHERE YEAR(created_at)=YEAR(CURDATE()) GROUP BY MONTH(created_at)"
        )
        raw_monthly_requests = cursor.fetchall()
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        monthly_requests = [
            {"label": month_names[row["month"] - 1], "count": row["count"]}
            for row in raw_monthly_requests
        ]
        cursor.execute(
            "SELECT * FROM rooms ORDER BY hostel, block, room"
        )
        rooms = cursor.fetchall()
        cursor.execute(
            "SELECT l.*, s.name, s.email, s.room FROM leave_requests l JOIN students s ON s.id=l.student_id ORDER BY l.created_at DESC"
        )
        leave_requests = cursor.fetchall()
        cursor.execute("SELECT id, name, email, status, hostel, block, room FROM students WHERE status='approved' ORDER BY name")
        notification_students = cursor.fetchall()
        cursor.execute(
            "SELECT hostel, block, room, COUNT(*) AS occupants FROM students WHERE status='approved' GROUP BY hostel, block, room ORDER BY occupants DESC"
        )
        occupancy_by_room = cursor.fetchall()
        cursor.execute(
            "SELECT c.id, c.student_id, c.category, c.subject, c.description, c.status, c.created_at, s.name, s.email FROM complaints c JOIN students s ON s.id = c.student_id ORDER BY c.created_at DESC"
        )
        complaints = cursor.fetchall()
        cursor.execute(
            "SELECT l.id, l.student_id, l.token_no, l.verification_code, l.out_code, l.bag_in_at, l.bag_out_at, l.token_date, l.token_time, l.status, l.created_at, s.name, s.email FROM laundry_tokens l JOIN students s ON s.id = l.student_id ORDER BY l.created_at DESC"
        )
        laundry_requests = cursor.fetchall()
        cursor.execute(
            "SELECT a.id, a.attendance_date, a.status, s.name, s.id AS student_id FROM attendance a JOIN students s ON s.id=a.student_id WHERE a.attendance_date=%s ORDER BY s.name",
            (attendance_date,),
        )
        attendance_records = cursor.fetchall()
        cursor.execute(
            "SELECT id, email, role, ip_address, user_agent, accessed_at, session_active FROM admin_access_logs ORDER BY accessed_at DESC LIMIT 100"
        )
        access_logs = cursor.fetchall()
        for access_log in access_logs:
            access_log["device_name"] = readable_device_name(access_log.get("user_agent"))
        cursor.execute(
            """
            SELECT p.*, s.name, s.email, s.phone, s.hostel, s.block, s.room
            FROM payment_submissions p
            JOIN students s ON s.id=p.student_id
            ORDER BY p.created_at DESC
            """
        )
        payment_submissions = cursor.fetchall()
        cursor.execute(
            """
            SELECT s.id, s.name, s.email, s.hostel, s.room, a.id AS attendance_id,
                   a.status AS attendance_status
            FROM students s
            LEFT JOIN attendance a ON a.student_id=s.id AND a.attendance_date=%s
            WHERE s.status='approved'
            ORDER BY s.name
            """,
            (attendance_date,),
        )
        admin_attendance_students = cursor.fetchall()
        student_filter_sql = ""
        params = []
        if search_query:
            student_filter_sql = "WHERE LOWER(CONCAT(IFNULL(name, ''), ' ', IFNULL(email, ''), ' ', IFNULL(phone, ''), ' ', IFNULL(hostel, ''), ' ', IFNULL(block, ''), ' ', IFNULL(room, ''))) LIKE %s"
            params.append(f"%{search_query}%")
        cursor.execute(
            f"SELECT * FROM students {student_filter_sql} ORDER BY created_at DESC",
            params,
        )
        students = cursor.fetchall()
        cursor.execute(
            "SELECT id, name, email, phone, hostel, block, room, status FROM students WHERE status='pending' ORDER BY created_at DESC"
        )
        pending_students = cursor.fetchall()
        cursor.execute(
            "SELECT id, name, email, phone, hostel, block, room, status, rent_paid, rent_amount, rent_paid_amount FROM students WHERE status='approved'"
        )
        approved_students = cursor.fetchall()
        room_student_map = {}
        for student in approved_students:
            room_key = f"{student['hostel']}|{student['block']}|{student['room']}"
            room_student_map.setdefault(room_key, []).append(student)
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Admin dashboard load failed:", exc)
        student_count = 0
        pending_count = 0
        approved_count = 0
        rejected_count = 0
        room_count = 0
        occupied_rooms = 0
        total_rooms = 0
        available_rooms = 0
        pending_rent_payments = 0
        total_rent_paid = 0.0
        total_rent_pending = 0.0
        total_expected_fee = 0.0
        fully_paid_students = 0
        partially_paid_students = 0
        unpaid_students = 0
        monthly_requests = []
        rooms = []
        occupancy_by_room = []
        complaints = []
        laundry_requests = []
        attendance_records = []
        access_logs = []
        payment_submissions = []
        admin_attendance_students = []
        pending_students = []
        approved_students = []
        students = []
        room_student_map = {}

    total_rooms = total_rooms if 'total_rooms' in locals() else 0
    available_rooms = available_rooms if 'available_rooms' in locals() else 0
    pending_rent_payments = pending_rent_payments if 'pending_rent_payments' in locals() else 0
    total_rent_paid = total_rent_paid if 'total_rent_paid' in locals() else 0.0
    total_rent_pending = total_rent_pending if 'total_rent_pending' in locals() else 0.0
    total_expected_fee = total_expected_fee if 'total_expected_fee' in locals() else 0.0
    fully_paid_students = fully_paid_students if 'fully_paid_students' in locals() else 0
    partially_paid_students = partially_paid_students if 'partially_paid_students' in locals() else 0
    unpaid_students = unpaid_students if 'unpaid_students' in locals() else 0
    room_count = room_count if 'room_count' in locals() else 0
    search_query = request.args.get("search", "")
    admin_security = get_admin_security_context(session.get("user_id"))

    return render_template(
        "admin_dashboard.html",
        student_count=student_count,
        room_count=room_count,
        total_rooms=total_rooms,
        available_rooms=available_rooms,
        occupied_rooms=occupied_rooms,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        pending_rent_payments=pending_rent_payments,
        total_rent_paid=total_rent_paid,
        total_rent_pending=total_rent_pending,
        total_expected_fee=total_expected_fee,
        fully_paid_students=fully_paid_students,
        partially_paid_students=partially_paid_students,
        unpaid_students=unpaid_students,
        monthly_requests=monthly_requests,
        rooms=rooms,
        occupancy_by_room=occupancy_by_room,
        complaints=complaints,
        laundry_requests=laundry_requests,
        attendance_records=attendance_records,
        access_logs=access_logs,
        admin_attendance_students=admin_attendance_students,
        attendance_date=attendance_date,
        leave_requests=leave_requests,
        notification_students=notification_students,
        pending_students=pending_students,
        approved_students=approved_students,
        students=students,
        room_student_map=room_student_map,
        search_query=search_query,
        hostel_fee=HOSTEL_FEE,
        admin_security=admin_security,
        payment_submissions=payment_submissions,
    )


@app.route("/admin-action", methods=["POST"])
def admin_action():
    if session.get("user_type") != "admin":
        return redirect("/admin-login")

    student_id = request.form.get("student_id")
    action = request.form.get("action")
    room_id = request.form.get("room_id")
    payment_id = request.form.get("payment_id")
    if action == "update_laundry":
        return redirect("/admin-dashboard")
    if action in {"update_room", "delete_room"} and (not room_id or (action == "update_room" and not request.form.get("room"))):
        return redirect("/admin-dashboard")
    if action == "add_room" and not request.form.get("room"):
        return redirect("/admin-dashboard")
    if action not in {"update_room", "delete_room", "add_room"} and ((not student_id and action not in {"update_leave"} and not payment_id and not request.form.get("access_log_id")) or action not in {"approve", "reject", "mark_paid", "record_payment", "update_complaint", "update_laundry", "update_leave", "set_student_active", "delete_student", "verify_payment", "logout_device"}):
        return redirect("/admin-dashboard")

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        if action in {"approve", "reject"}:
            status = "approved" if action == "approve" else "rejected"
            if action == "approve":
                cursor.execute(
                    """
                    SELECT s.hostel, s.block, s.room, r.capacity, r.status,
                           COUNT(CASE WHEN other.status='approved' THEN 1 END) AS occupants
                    FROM students s
                    LEFT JOIN rooms r ON r.hostel=s.hostel AND r.block=s.block AND r.room=s.room
                    LEFT JOIN students other ON other.hostel=s.hostel AND other.block=s.block AND other.room=s.room AND other.id <> s.id
                    WHERE s.id=%s
                    GROUP BY s.id, s.hostel, s.block, s.room, r.capacity, r.status
                    """,
                    (student_id,),
                )
                room = cursor.fetchone()
                if not room or room["status"] != "available" or room["occupants"] >= room["capacity"]:
                    connection.rollback()
                    cursor.close()
                    connection.close()
                    flash("This application cannot be approved because its selected room is unavailable or full.", "warning")
                    return redirect("/admin-dashboard")
            cursor.execute("UPDATE students SET status=%s WHERE id=%s", (status, student_id))
        elif action == "mark_paid":
            cursor.execute(
                "UPDATE students SET rent_paid=%s, rent_paid_amount = rent_amount WHERE id=%s",
                ("yes", student_id),
            )
        elif action == "record_payment":
            amount_str = request.form.get("payment_amount", "0")
            try:
                payment_amount = float(amount_str)
            except ValueError:
                payment_amount = 0.0
            cursor.execute(
                "SELECT rent_amount, rent_paid_amount FROM students WHERE id=%s",
                (student_id,),
            )
            current = cursor.fetchone()
            if current:
                rent_amount = float(current["rent_amount"])
                rent_paid_amount = float(current["rent_paid_amount"])
                new_paid_total = min(rent_amount, rent_paid_amount + payment_amount)
                rent_paid = "yes" if new_paid_total >= rent_amount and rent_amount > 0 else "no"
                cursor.execute(
                    "UPDATE students SET rent_paid_amount=%s, rent_paid=%s WHERE id=%s",
                    (new_paid_total, rent_paid, student_id),
                )
        elif action == "update_complaint":
            complaint_id = request.form.get("complaint_id")
            status = request.form.get("status", "pending")
            if complaint_id:
                cursor.execute(
                    "UPDATE complaints SET status=%s WHERE id=%s",
                    (status, complaint_id),
                )
        elif action == "update_leave":
            leave_id = request.form.get("leave_id")
            status = request.form.get("status", "pending")
            cursor.execute("UPDATE leave_requests SET status=%s, admin_note=%s WHERE id=%s", (status, request.form.get("admin_note", "").strip(), leave_id))
        elif action == "logout_device":
            authenticator_code = request.form.get("authenticator_code", "").strip()
            secret = session.get("admin_2fa_secret")
            if not secret:
                cursor.execute("SELECT two_factor_secret FROM `admin` WHERE id=%s", (session.get("user_id"),))
                admin_record = cursor.fetchone()
                secret = admin_record.get("two_factor_secret") if admin_record else None
            if not secret or not pyotp.TOTP(secret).verify(authenticator_code, valid_window=1):
                connection.rollback()
                cursor.close()
                connection.close()
                flash("Invalid authenticator code. Device was not logged out.", "danger")
                return redirect("/admin-dashboard#admin-access-logs")
            cursor.execute("UPDATE admin_access_logs SET session_active=0 WHERE id=%s", (request.form.get("access_log_id"),))
        elif action == "set_student_active":
            is_active = 1 if request.form.get("is_active") == "1" else 0
            cursor.execute("UPDATE students SET is_active=%s WHERE id=%s", (is_active, student_id))
        elif action == "delete_student":
            for table in ("complaints", "laundry_tokens", "attendance", "leave_requests", "notifications"):
                cursor.execute(f"DELETE FROM {table} WHERE student_id=%s", (student_id,))
            cursor.execute("DELETE FROM students WHERE id=%s", (student_id,))
        elif action == "verify_payment":
            payment_status = request.form.get("status", "pending")
            if payment_status not in {"approved", "rejected"}:
                return redirect("/admin-dashboard#payment-verification")
            cursor.execute("SELECT student_id, amount, status FROM payment_submissions WHERE id=%s", (payment_id,))
            payment = cursor.fetchone()
            if payment and payment["status"] == "pending":
                cursor.execute("UPDATE payment_submissions SET status=%s, admin_note=%s WHERE id=%s", (payment_status, request.form.get("admin_note", "").strip(), payment_id))
                if payment_status == "approved":
                    cursor.execute("SELECT rent_amount, rent_paid_amount FROM students WHERE id=%s", (payment["student_id"],))
                    student_fee = cursor.fetchone()
                    if student_fee:
                        paid_amount = min(float(student_fee["rent_amount"] or 0), float(student_fee["rent_paid_amount"] or 0) + float(payment["amount"] or 0))
                        rent_paid = "yes" if paid_amount >= float(student_fee["rent_amount"] or 0) and float(student_fee["rent_amount"] or 0) > 0 else "no"
                        cursor.execute("UPDATE students SET rent_paid_amount=%s, rent_paid=%s WHERE id=%s", (paid_amount, rent_paid, payment["student_id"]))
        elif action == "update_room":
            valid_rooms_by_floor = {
                "Basement": {f"B-{number:02d}" for number in range(1, 8)},
                "1st Floor": {str(number) for number in range(101, 109)},
                "2nd Floor": {str(number) for number in range(201, 209)},
                "3rd Floor": {str(number) for number in range(301, 309)},
            }
            hostel = request.form.get("hostel", "RKH").strip()
            floor = request.form.get("block", "").strip()
            room_number = request.form.get("room", "").strip()
            if hostel != "RKH" or room_number not in valid_rooms_by_floor.get(floor, set()):
                return redirect("/admin-dashboard")
            try:
                capacity = max(1, int(request.form.get("capacity", "1")))
            except ValueError:
                capacity = 1
            status = request.form.get("status", "available")
            if status not in {"available", "maintenance", "unavailable"}:
                status = "available"
            cursor.execute(
                """
                UPDATE rooms
                SET hostel=%s, block=%s, room=%s, capacity=%s, status=%s, maintenance_notes=%s
                WHERE id=%s
                """,
                (
                    hostel,
                    floor,
                    room_number,
                    capacity,
                    status,
                    request.form.get("maintenance_notes", "").strip(),
                    room_id,
                ),
            )
        elif action == "add_room":
            valid_rooms_by_floor = {
                "Basement": {f"B-{number:02d}" for number in range(1, 8)},
                "1st Floor": {str(number) for number in range(101, 109)},
                "2nd Floor": {str(number) for number in range(201, 209)},
                "3rd Floor": {str(number) for number in range(301, 309)},
            }
            hostel = request.form.get("hostel", "RKH").strip()
            floor = request.form.get("block", "").strip()
            room_number = request.form.get("room", "").strip()
            if hostel != "RKH" or room_number not in valid_rooms_by_floor.get(floor, set()):
                return redirect("/admin-dashboard")
            try:
                capacity = max(1, int(request.form.get("capacity", "1")))
            except ValueError:
                capacity = 1
            status = request.form.get("status", "available")
            if status not in {"available", "maintenance", "unavailable"}:
                status = "available"
            cursor.execute(
                "INSERT INTO rooms (hostel, block, room, capacity, status, maintenance_notes) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    hostel,
                    floor,
                    room_number,
                    capacity,
                    status,
                    request.form.get("maintenance_notes", "").strip(),
                ),
            )
        elif action == "delete_room":
            cursor.execute(
                "SELECT COUNT(*) AS occupants FROM students WHERE hostel=(SELECT hostel FROM rooms WHERE id=%s) AND block=(SELECT block FROM rooms WHERE id=%s) AND room=(SELECT room FROM rooms WHERE id=%s) AND status='approved'",
                (room_id, room_id, room_id),
            )
            if cursor.fetchone()["occupants"] == 0:
                cursor.execute("DELETE FROM rooms WHERE id=%s", (room_id,))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as exc:
        print("Admin action failed:", exc)

    return redirect("/admin-dashboard")


@app.route("/admin-notification", methods=["POST"])
def admin_notification():
    if session.get("user_type") != "admin":
        return redirect("/admin-login")

    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    audience = request.form.get("audience", "all")
    student_id = request.form.get("student_id") if audience == "student" else None
    image = request.files.get("image")
    if not title or not message or (audience == "student" and not student_id):
        flash("Enter a title, message, and student when sending individually.", "danger")
        return redirect("/admin-dashboard")

    try:
        image_url = None
        if image and image.filename:
            upload_dir = os.path.join(BASE_DIR, "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"notification_{secrets.token_hex(8)}_{secure_filename(image.filename)}"
            image.save(os.path.join(upload_dir, filename))
            image_url = f"/uploads/{filename}"
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO notifications (student_id, title, message, image_url) VALUES (%s, %s, %s, %s)",
            (student_id, title, message, image_url),
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("Notification sent successfully.", "success")
    except Exception as exc:
        print("Notification creation failed:", exc)
        flash("Notification could not be sent.", "danger")
    return redirect("/admin-dashboard")


@app.route("/admin-download-students")
def admin_download_students():
    if session.get("user_type") != "admin":
        return redirect("/admin-login")
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM students ORDER BY created_at DESC")
        students = cursor.fetchall()
        cursor.close()
        connection.close()
        columns = [
            "id", "name", "email", "phone", "status", "hostel", "block", "room", "bed_number",
            "college", "course", "department", "year_semester", "father_name", "mother_name",
            "guardian_name", "guardian_phone", "guardian_phone_2", "emergency_contact", "aadhaar",
            "home_address", "address_city", "address_district", "address_state", "address_pincode",
            "address_country", "blood_group", "photo_url", "college_id_url", "rent_amount",
            "rent_paid_amount", "rent_paid", "created_at",
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for student in students:
            writer.writerow([student.get(column, "") for column in columns])
        response = app.response_class(output.getvalue(), mimetype="text/csv; charset=utf-8")
        response.headers["Content-Disposition"] = "attachment; filename=hostel_students_excel.csv"
        return response
    except Exception as exc:
        print("Student Excel export failed:", exc)
        flash("Student Excel file could not be generated.", "danger")
        return redirect("/admin-dashboard")


@app.route("/admin-download-all-data")
def admin_download_all_data():
    if session.get("user_type") != "admin":
        return redirect("/admin-login")
    datasets = {
        "students.csv": "SELECT * FROM students ORDER BY created_at DESC",
        "rooms.csv": "SELECT * FROM rooms ORDER BY hostel, block, room",
        "complaints.csv": "SELECT c.*, s.name AS student_name, s.email FROM complaints c LEFT JOIN students s ON s.id=c.student_id ORDER BY c.created_at DESC",
        "laundry_requests.csv": "SELECT l.*, s.name AS student_name, s.email FROM laundry_tokens l LEFT JOIN students s ON s.id=l.student_id ORDER BY l.created_at DESC",
        "leave_requests.csv": "SELECT l.*, s.name AS student_name, s.email FROM leave_requests l LEFT JOIN students s ON s.id=l.student_id ORDER BY l.created_at DESC",
        "notifications.csv": "SELECT n.*, s.name AS student_name, s.email FROM notifications n LEFT JOIN students s ON s.id=n.student_id ORDER BY n.created_at DESC",
    }
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as workbook:
            for filename, query in datasets.items():
                cursor.execute(query)
                rows = cursor.fetchall()
                output = io.StringIO()
                if rows:
                    columns = list(rows[0].keys())

                else:
                    columns = []
                writer = csv.writer(output)
                writer.writerow(columns)
                for row in rows:
                    writer.writerow([row.get(column, "") for column in columns])
                workbook.writestr(filename, output.getvalue())
        cursor.close()
        connection.close()
        archive.seek(0)
        return send_file(archive, mimetype="application/zip", as_attachment=True, download_name="hostel_dashboard_all_data.zip")
    except Exception as exc:
        print("Complete dashboard export failed:", exc)
        flash("Complete dashboard data could not be downloaded.", "danger")
        return redirect("/admin-dashboard")


if __name__ == "__main__":
    seed_admin_user()

    host, port, debug = get_server_config()
    app.run(host=host, port=port, debug=debug)
