import os
import io
import hashlib
import smtplib
import mimetypes
import html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Tuple, List

import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# Excel
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DB_URL", "sqlite:///planner.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
db = SQLAlchemy(app)

socketio = SocketIO(app)

# Ensure upload dir exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)



# --- AUTO MIGRATION (SQLite) ---
# Robust migration: derive the *exact* sqlite file path from SQLAlchemy engine URL,
# then use sqlite3 directly to ALTER TABLE if needed. This avoids "wrong file" issues.

import os
import sqlite3
from sqlalchemy import text as _sql_text, or_

def _sqlite_db_path():
    try:
        url = str(db.engine.url)
    except Exception:
        return None
    if not url.startswith("sqlite"):
        return None

    # db.engine.url.database is already decoded by SQLAlchemy
    try:
        p = db.engine.url.database
    except Exception:
        p = None
    if not p:
        return None
    if not os.path.isabs(p):
        p = os.path.abspath(p)
    return p

def _column_exists_sqlite(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols

def ensure_schema():
    '''Ensure missing columns are added (idempotent).'''
    try:
        # Ensure all tables exist first
        db.create_all()
        
        # Use the same DB connection/session the app uses (avoids wrong-file issues)
        rows = db.session.execute(_sql_text("PRAGMA table_info(plan_cell)")).fetchall()
        if not rows:
            return  # table may not exist yet
        cols = [r[1] for r in rows]
        if "team_name" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN team_name TEXT"))
            db.session.commit()
            cols.append("team_name")  # Update cols list

        # plan_cell attachments and mail body
        if "job_mail_body" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN job_mail_body TEXT"))
            db.session.commit()
            cols.append("job_mail_body")
        if "lld_hhd_path" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN lld_hhd_path TEXT"))
            db.session.commit()
            cols.append("lld_hhd_path")
        if "tutanak_path" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN tutanak_path TEXT"))
            db.session.commit()
            cols.append("tutanak_path")
        if "lld_hhd_files" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN lld_hhd_files TEXT"))
            db.session.commit()
            cols.append("lld_hhd_files")
        if "tutanak_files" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN tutanak_files TEXT"))
            db.session.commit()
            cols.append("tutanak_files")

        # plan_cell.isdp_info / po_info
        if "isdp_info" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN isdp_info TEXT"))
            db.session.commit()
            cols.append("isdp_info")  # Update cols list
        if "po_info" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN po_info TEXT"))
            db.session.commit()
            cols.append("po_info")  # Update cols list
        if "important_note" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN important_note TEXT"))
            db.session.commit()
            cols.append("important_note")  # Update cols list
        # plan_cell.updated_at
        if "updated_at" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN updated_at DATETIME"))
            db.session.commit()
            # Mevcut kayıtlar için updated_at'i güncelle
            db.session.execute(_sql_text("UPDATE plan_cell SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))
            db.session.commit()
            cols.append("updated_at")  # Update cols list

        # project.is_active
        prow = db.session.execute(_sql_text("PRAGMA table_info(project)")).fetchall()
        if prow:
            pcols = [r[1] for r in prow]
            if "is_active" not in pcols:
                db.session.execute(_sql_text("ALTER TABLE project ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"))
                db.session.commit()
            # project.karsi_firma_sorumlusu
            if "karsi_firma_sorumlusu" not in pcols:
                db.session.execute(_sql_text("ALTER TABLE project ADD COLUMN karsi_firma_sorumlusu TEXT"))
                db.session.commit()
        
        # person.firma_id, seviye_id, durum
        pcols = [r[1] for r in db.session.execute(_sql_text("PRAGMA table_info(person)")).fetchall()]
        if "firma_id" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN firma_id INTEGER"))
            db.session.commit()
        if "seviye_id" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN seviye_id INTEGER"))
            db.session.commit()
        if "durum" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN durum TEXT NOT NULL DEFAULT 'Aktif'"))
            db.session.commit()
        if "karsi_firma_sorumlusu" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN karsi_firma_sorumlusu TEXT"))
            db.session.commit()
        
        # user.email, full_name, is_active
        try:
            urows = db.session.execute(_sql_text("PRAGMA table_info(user)")).fetchall()
            if urows:
                ucols = [r[1] for r in urows]
                if "email" not in ucols:
                    db.session.execute(_sql_text("ALTER TABLE user ADD COLUMN email TEXT"))
                    db.session.commit()
                if "full_name" not in ucols:
                    db.session.execute(_sql_text("ALTER TABLE user ADD COLUMN full_name TEXT"))
                    db.session.commit()
                if "is_active" not in ucols:
                    db.session.execute(_sql_text("ALTER TABLE user ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"))
                    db.session.commit()
        except Exception:
            pass  # Table might not exist yet
        
        # Firma adını "Netmen"den "Netmon"a güncelle
        try:
            netmen_firma = Firma.query.filter_by(name="Netmen").first()
            if netmen_firma:
                netmen_firma.name = "Netmon"
                db.session.commit()
        except Exception:
            pass  # Table might not exist yet
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("[ensure_schema] migration skipped/failed:", e)

# Initialize default data
def init_default_data():
    try:
        # Initialize default firmalar - always ensure they exist
        firma_names = ["Netmon", "Finans", "Hytech"]
        for name in firma_names:
            existing = Firma.query.filter_by(name=name).first()
            if not existing:
                # Eğer eski "Netmen" varsa onu "Netmon" olarak güncelle
                if name == "Netmon":
                    old_netmen = Firma.query.filter_by(name="Netmen").first()
                    if old_netmen:
                        old_netmen.name = "Netmon"
                        db.session.commit()
                        continue
                db.session.add(Firma(name=name, is_active=True))
        
        # Initialize default seviyeler - always ensure they exist
        seviye_names = ["Ana kadro", "Yardımcı", "Alt yüklenici"]
        for name in seviye_names:
            existing = Seviye.query.filter_by(name=name).first()
            if not existing:
                db.session.add(Seviye(name=name, is_active=True))
        
        # Initialize default vehicles - always ensure at least 4 vehicles exist
        default_vehicles = [
            {"plate": "34HLV281", "brand": "Fiat", "model": "Fiorino", "vehicle_type": "Van"},
            {"plate": "34ABC123", "brand": "Ford", "model": "Transit", "vehicle_type": "Minibüs"},
            {"plate": "34XYZ789", "brand": "Mercedes", "model": "Sprinter", "vehicle_type": "Kamyon"},
            {"plate": "34DEF456", "brand": "Renault", "model": "Master", "vehicle_type": "Van"}
        ]
        for v_data in default_vehicles:
            existing = Vehicle.query.filter_by(plate=v_data["plate"]).first()
            if not existing:
                db.session.add(Vehicle(
                    plate=v_data["plate"],
                    brand=v_data["brand"],
                    model=v_data["model"],
                    vehicle_type=v_data["vehicle_type"],
                    status="available"
                ))
        
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        # Silently fail - will retry on next request


# --- ONE-TIME STARTUP INIT (per process) ---
# Running schema migrations and seed-data on *every* request can cause serious
# contention with SQLite (especially under gunicorn with multiple workers/threads).
# We guard it to run only once per process.
import threading as _threading
__startup_lock = _threading.Lock()
__startup_done = False

def _run_startup_tasks_once():
    global __startup_done
    if __startup_done:
        return
    with __startup_lock:
        if __startup_done:
            return
        ensure_schema()
        init_default_data()
        try:
            # Initialize users if needed
            if 'User' in globals():
                if User.query.count() == 0:
                    init_users()
        except Exception:
            # Don't block the app if user init fails; it can be retried manually
            try:
                db.session.rollback()
            except Exception:
                pass
        __startup_done = True

@app.before_request
def _ensure_schema_before_request():
    _run_startup_tasks_once()
# --- END AUTO MIGRATION ---
TR_DAYS = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"]
SHIFT_ORDER = {"Gündüz": 1, "Gündüz Yol": 2, "Gece": 3}

def normalize_shift(shift_value):
    """Eski shift değerlerini yeni formata çevir (backward compatibility)"""
    if not shift_value:
        return ""
    shift_map = {
        "Gündüz": "08:30-18:00",
        "Gündüz Yol": "08:30-18:00 YOL",
        "Gece": "00:00-06:00"
    }
    return shift_map.get(shift_value, shift_value)

# Türkiye illeri (dropdown için)
TR_CITIES = [
    "Adana","Adıyaman","Afyonkarahisar","Ağrı","Aksaray","Amasya","Ankara","Antalya","Ardahan","Artvin",
    "Aydın","Balıkesir","Bartın","Batman","Bayburt","Bilecik","Bingöl","Bitlis","Bolu","Burdur",
    "Bursa","Çanakkale","Çankırı","Çorum","Denizli","Diyarbakır","Düzce","Edirne","Elazığ","Erzincan",
    "Erzurum","Eskişehir","Gaziantep","Giresun","Gümüşhane","Hakkari","Hatay","Iğdır","Isparta","İstanbul",
    "İzmir","Kahramanmaraş","Karabük","Karaman","Kars","Kastamonu","Kayseri","Kırıkkale","Kırklareli","Kırşehir",
    "Kilis","Kocaeli","Konya","Kütahya","Malatya","Manisa","Mardin","Mersin","Muğla","Muş",
    "Nevşehir","Niğde","Ordu","Osmaniye","Rize","Sakarya","Samsun","Siirt","Sinop","Sivas",
    "Şanlıurfa","Şırnak","Tekirdağ","Tokat","Trabzon","Tunceli","Uşak","Van","Yalova","Yozgat","Zonguldak"
]


# ===================== MODELS =====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="user")  # user, admin
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    full_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Firma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

class Seviye(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    tc_no = db.Column(db.String(20))
    role = db.Column(db.String(80))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    firma_id = db.Column(db.Integer, db.ForeignKey("firma.id"), nullable=True)
    seviye_id = db.Column(db.Integer, db.ForeignKey("seviye.id"), nullable=True)
    durum = db.Column(db.String(20), nullable=False, default="Aktif")  # Aktif veya Pasif
    karsi_firma_sorumlusu = db.Column(db.String(120))  # Karşı Firma Sorumlusu
    
    firma = db.relationship("Firma")
    seviye = db.relationship("Seviye")


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    region = db.Column(db.String(80), nullable=False)
    project_code = db.Column(db.String(80), nullable=False)
    project_name = db.Column(db.String(180), nullable=False)
    responsible = db.Column(db.String(120), nullable=False)
    karsi_firma_sorumlusu = db.Column(db.String(120))  # Karşı Firma Sorumlusu

    is_active = db.Column(db.Boolean, nullable=False, default=True)

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    signature = db.Column(db.String(400), nullable=False, unique=True)


class PlanCell(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)

    shift = db.Column(db.String(20), nullable=True)          # Gündüz / Gündüz Yol / Gece
    vehicle_info = db.Column(db.String(120), nullable=True)
    note = db.Column(db.Text, nullable=True)
    job_mail_body = db.Column(db.Text, nullable=True)  # İş detay maili metni

    isdp_info = db.Column(db.String(200), nullable=True)
    po_info = db.Column(db.String(200), nullable=True)
    important_note = db.Column(db.Text, nullable=True)
    lld_hhd_path = db.Column(db.String(255), nullable=True)  # PDF/Word
    tutanak_path = db.Column(db.String(255), nullable=True)  # Excel
    lld_hhd_files = db.Column(db.Text, nullable=True)  # JSON list
    tutanak_files = db.Column(db.Text, nullable=True)  # JSON list

    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)

    team_name = db.Column(db.String(120), nullable=True)  # rapor için ekip adı
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    project = db.relationship("Project", backref=db.backref("cells", cascade="all, delete-orphan"))
    team = db.relationship("Team", backref=db.backref("cells", cascade="all"))

    __table_args__ = (db.UniqueConstraint("project_id", "work_date", name="uq_project_day"),)


class CellAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cell_id = db.Column(db.Integer, db.ForeignKey("plan_cell.id"), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False, index=True)

    cell = db.relationship("PlanCell", backref=db.backref("assignments", cascade="all, delete-orphan"))
    person = db.relationship("Person")


class PersonDayStatus(db.Model):
    """
    Günlük personel durumu:
      available (boşta) / leave (izinli) / production (üretimde)
    """
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False, index=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="available")
    note = db.Column(db.String(200), nullable=True)

    person = db.relationship("Person")

    __table_args__ = (db.UniqueConstraint("person_id", "work_date", name="uq_person_day"),)


class Vehicle(db.Model):
    """
    Araç/Tool bilgileri
    """
    id = db.Column(db.Integer, primary_key=True)
    plate = db.Column(db.String(20), nullable=False, unique=True)  # Plaka
    brand = db.Column(db.String(80), nullable=False)  # Marka
    model = db.Column(db.String(80), nullable=True)  # Model
    year = db.Column(db.Integer, nullable=True)  # Yıl
    vehicle_type = db.Column(db.String(50), nullable=True)  # Araç tipi (Araba, Kamyon, vb.)
    status = db.Column(db.String(50), nullable=True, default="available")  # Durum (available, maintenance, out_of_service)
    notes = db.Column(db.Text, nullable=True)  # Notlar
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


# ===================== HELPERS =====================

def parse_date(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def pastel_color(key: str) -> str:
    h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
    hue = h % 360
    return f"hsl({hue} 70% 88%)"


def team_color(team_id: int) -> str:
    # Leaflet polyline için tutarlı renk
    hue = (team_id * 47) % 360
    return f"hsl({hue} 75% 45%)"


def ensure_cell(project_id: int, work_date: date) -> PlanCell:
    cell = PlanCell.query.filter_by(project_id=project_id, work_date=work_date).first()
    if cell:
        return cell
    cell = PlanCell(project_id=project_id, work_date=work_date)
    db.session.add(cell)
    db.session.commit()
    return cell


def team_signature(person_ids: List[int]) -> str:
    ids = sorted({int(x) for x in person_ids})
    return ",".join(str(x) for x in ids)


def ensure_team_for_people(person_ids: List[int]) -> Optional[Team]:
    ids = sorted({int(x) for x in person_ids})
    if not ids:
        return None
    sig = team_signature(ids)
    t = Team.query.filter_by(signature=sig).first()
    if t:
        return t
    next_no = (db.session.query(db.func.count(Team.id)).scalar() or 0) + 1
    t = Team(name=f"Ekip {next_no}", signature=sig)
    db.session.add(t)
    return t


def set_assignments_and_team(cell: PlanCell, person_ids: List[int]):
    # Eski personelleri al
    old_person_ids = {a.person_id for a in CellAssignment.query.filter_by(cell_id=cell.id).all()}
    
    CellAssignment.query.filter_by(cell_id=cell.id).delete()
    ids = sorted({int(x) for x in person_ids})
    for pid in ids:
        db.session.add(CellAssignment(cell_id=cell.id, person_id=pid))
    
    # PersonDayStatus güncelle
    # Çıkarılan personeller için, eğer başka işte değillerse 'available' yap
    removed_ids = old_person_ids - set(ids)
    for pid in removed_ids:
        # Bu personelin başka işleri var mı kontrol et
        other_assignments = CellAssignment.query.join(PlanCell, PlanCell.id == CellAssignment.cell_id)\
            .filter(CellAssignment.person_id == pid, PlanCell.work_date == cell.work_date, PlanCell.id != cell.id).count()
        if other_assignments == 0:
            # Başka işi yok, status 'available' yap
            status_rec = PersonDayStatus.query.filter_by(person_id=pid, work_date=cell.work_date).first()
            if status_rec and status_rec.status == 'production':
                status_rec.status = 'available'
    
    # Eklenen personeller için 'production' yap
    added_ids = set(ids) - old_person_ids
    for pid in added_ids:
        status_rec = PersonDayStatus.query.filter_by(person_id=pid, work_date=cell.work_date).first()
        if not status_rec:
            status_rec = PersonDayStatus(person_id=pid, work_date=cell.work_date, status='production')
            db.session.add(status_rec)
        elif status_rec.status == 'available':
            status_rec.status = 'production'
    
    t = ensure_team_for_people(ids)
    cell.team_id = t.id if t else None


def snapshot_cell(cell: Optional[PlanCell]) -> dict:
    if not cell:
        return {"exists": False}
    pids = [a.person_id for a in cell.assignments]
    lld_list = _parse_files(getattr(cell, "lld_hhd_files", None))
    tut_list = _parse_files(getattr(cell, "tutanak_files", None))
    # backward compat: single path
    if getattr(cell, "lld_hhd_path", None) and not lld_list:
        lld_list = [cell.lld_hhd_path]
    if getattr(cell, "tutanak_path", None) and not tut_list:
        tut_list = [cell.tutanak_path]
    return {
        "exists": True,
        "shift": cell.shift,
        "vehicle_info": cell.vehicle_info,
        "note": cell.note,
        "isdp_info": getattr(cell, "isdp_info", None),
        "po_info": getattr(cell, "po_info", None),
        "important_note": getattr(cell, "important_note", None),
        "team_name": cell.team_name,
        "job_mail_body": getattr(cell, "job_mail_body", None),
        "lld_hhd_files": lld_list,
        "tutanak_files": tut_list,
        "person_ids": pids
    }


def apply_snapshot(cell: PlanCell, snap: dict):
    if not snap.get("exists"):
        cell.shift = None
        cell.vehicle_info = None
        cell.note = None
        cell.isdp_info = None
        cell.po_info = None
        cell.important_note = None
        cell.team_name = None
        # delete all attachments
        for fname in _parse_files(getattr(cell, "lld_hhd_files", None)) + ([cell.lld_hhd_path] if getattr(cell, "lld_hhd_path", None) else []):
            delete_upload(fname)
        for fname in _parse_files(getattr(cell, "tutanak_files", None)) + ([cell.tutanak_path] if getattr(cell, "tutanak_path", None) else []):
            delete_upload(fname)
        cell.lld_hhd_path = None
        cell.tutanak_path = None
        cell.lld_hhd_files = None
        cell.tutanak_files = None
        cell.job_mail_body = None
        set_assignments_and_team(cell, [])
        return
    cell.shift = snap.get("shift") or None
    cell.vehicle_info = snap.get("vehicle_info") or None
    cell.note = snap.get("note") or None
    cell.isdp_info = snap.get("isdp_info") or None
    cell.po_info = snap.get("po_info") or None
    cell.important_note = snap.get("important_note") or None
    cell.team_name = snap.get("team_name") or None
    cell.job_mail_body = snap.get("job_mail_body") or None
    lld_list = _parse_files(snap.get("lld_hhd_files"))
    tut_list = _parse_files(snap.get("tutanak_files"))
    cell.lld_hhd_files = _dump_files(lld_list) if lld_list else None
    cell.tutanak_files = _dump_files(tut_list) if tut_list else None
    # backward compat single
    cell.lld_hhd_path = snap.get("lld_hhd_path") or None
    cell.tutanak_path = snap.get("tutanak_path") or None
    set_assignments_and_team(cell, snap.get("person_ids") or [])


_geocode_cache = {}

def geocode_city(city: str):
    city = city.strip().lower()
    if city in _geocode_cache:
        return _geocode_cache[city]
    
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}, Turkey", "format": "json", "limit": 1},
            headers={"User-Agent": "haftalik-planlama"},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            _geocode_cache[city] = (None, None)
            return None, None
        lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
        _geocode_cache[city] = (lat, lon)
        return lat, lon
    except Exception:
        _geocode_cache[city] = (None, None)
        return None, None


ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx"}

def allowed_upload(filename: str) -> bool:
    return bool(filename and "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_UPLOAD_EXTENSIONS)

def _parse_files(val) -> List[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(x) for x in val if x]
    try:
        import json
        arr = json.loads(val)
        if isinstance(arr, list):
            return [str(x) for x in arr if x]
    except Exception:
        pass
    # fallback: comma separated
    if isinstance(val, str):
        return [x.strip() for x in val.split(",") if x.strip()]
    return []

def _dump_files(lst: List[str]) -> str:
    import json
    return json.dumps([x for x in lst if x])

def save_uploaded_file(fs, prefix: str) -> Optional[str]:
    """Save uploaded file and return stored filename."""
    if not fs or not fs.filename:
        return None
    if not allowed_upload(fs.filename):
        raise ValueError("Desteklenmeyen dosya türü. İzin verilenler: pdf, doc, docx, xls, xlsx")
    fname = secure_filename(fs.filename)
    base, ext = os.path.splitext(fname)
    unique = f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hashlib.md5(os.urandom(16)).hexdigest()[:6]}{ext.lower()}"
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    full_path = os.path.join(app.config["UPLOAD_FOLDER"], unique)
    fs.save(full_path)
    return unique

def delete_upload(filename: Optional[str]):
    if not filename:
        return
    full_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception:
        pass


# ---------- MAIL SETTINGS ----------
MAIL_SETTINGS_PATH = os.path.join(app.instance_path, "mail_settings.json")

def load_mail_settings() -> dict:
    import json
    if os.path.exists(MAIL_SETTINGS_PATH):
        try:
            with open(MAIL_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    # fallback to env
    return {
        "host": os.getenv("SMTP_HOST") or "",
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER") or "",
        "password": os.getenv("SMTP_PASS") or "",
        "from_addr": os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "",
        "use_tls": True,
    }

def save_mail_settings(data: dict):
    import json
    os.makedirs(app.instance_path, exist_ok=True)
    with open(MAIL_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def send_email_smtp(to_addr: str, subject: str, html_body: str, attachments: Optional[List[dict]] = None):
    cfg = load_mail_settings()
    host = cfg.get("host")
    port = int(cfg.get("port", 587))
    user = cfg.get("user")
    pw = cfg.get("password")
    from_addr = cfg.get("from_addr") or user
    use_tls = bool(cfg.get("use_tls", True))

    if not (host and user and pw and from_addr):
        raise RuntimeError("SMTP ayarları eksik: SMTP_HOST/PORT/USER/PASS/FROM")

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if attachments:
        for att in attachments:
            try:
                fname = att.get("filename") or "dosya"
                data = att.get("data") or b""
                content_type = att.get("content_type") or "application/octet-stream"
                maintype, subtype = content_type.split("/", 1) if "/" in content_type else ("application", "octet-stream")
                part = MIMEBase(maintype, subtype)
                part.set_payload(data)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
                msg.attach(part)
            except Exception:
                continue

    with smtplib.SMTP(host, port, timeout=20) as s:
        if use_tls:
            s.starttls()
        if user and pw:
            s.login(user, pw)
        s.sendmail(from_addr, [to_addr], msg.as_string())


def get_person_status_map(days: List[date]) -> Dict[Tuple[int, str], str]:
    """
    (person_id, date_iso) -> status
    """
    if not days:
        return {}
    rows = PersonDayStatus.query.filter(
        PersonDayStatus.work_date >= days[0],
        PersonDayStatus.work_date <= days[-1]
    ).all()
    mp = {}
    for r in rows:
        mp[(r.person_id, iso(r.work_date))] = r.status
    return mp


# ===================== AUTH HELPERS =====================

def login_required(f):
    """Decorator to require login for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # Gözlemci rolü POST isteklerini engelle (değişiklik yapamaz)
        if request.method == 'POST':
            current_user = get_current_user()
            if current_user and current_user.role == 'gözlemci':
                flash("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.", "danger")
                return redirect(url_for("plan_week"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash("Bu işlem için admin yetkisi gereklidir.", "danger")
            return redirect(url_for("plan_week"))
        return f(*args, **kwargs)
    return decorated_function


# ---------- MAIL SETTINGS PAGE ----------
@app.route("/mail/settings", methods=["GET", "POST"])
@admin_required
def mail_settings_page():
    if request.method == "POST":
        host = request.form.get("host", "").strip()
        port = request.form.get("port", "587").strip()
        user = request.form.get("user", "").strip()
        password = request.form.get("password", "").strip()
        from_addr = request.form.get("from_addr", "").strip()
        use_tls = (request.form.get("use_tls") == "1")

        if not host or not port:
            flash("Host ve port zorunlu.", "danger")
            return redirect(url_for("mail_settings_page"))

        data = {
            "host": host,
            "port": int(port or 587),
            "user": user,
            "password": password,
            "from_addr": from_addr,
            "use_tls": use_tls
        }
        save_mail_settings(data)
        flash("Mail ayarları kaydedildi.", "success")
        return redirect(url_for("mail_settings_page"))

    cfg = load_mail_settings()
    return render_template("mail_settings.html", cfg=cfg)

def kivanc_required(f):
    """Decorator to require kivanc username for routes (only kivanc can access)"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # Check if user is kivanc by email or username
        current_user = get_current_user()
        if not current_user or (current_user.email != 'kivancozcan@netmon.com.tr' and current_user.username != 'kivanc'):
            flash("Bu sayfaya erişim yetkiniz yok.", "danger")
            return redirect(url_for("plan_week"))
        return f(*args, **kwargs)
    return decorated_function


# ---------- FILES (UPLOAD/DOWNLOAD) ----------
@app.get("/files/<path:filename>")
@login_required
def download_file(filename: str):
    try:
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
    except Exception:
        flash("Dosya bulunamadı.", "danger")
        return redirect(request.referrer or url_for("plan_week"))

def get_current_user():
    """Get current logged in user"""
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])

def observer_required(f):
    """Decorator to allow observer role - can only view, cannot modify"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        current_user = get_current_user()
        if not current_user:
            flash("Oturum açmanız gerekiyor.", "danger")
            return redirect(url_for('login'))
        # Gözlemci rolü sadece görüntüleme yapabilir, değişiklik yapamaz
        if current_user.role == 'gözlemci':
            # POST isteklerini engelle (değişiklik yapma)
            if request.method == 'POST':
                flash("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.", "danger")
                return redirect(url_for("plan_week"))
        return f(*args, **kwargs)
    return decorated_function

def init_users():
    """Initialize default users if they don't exist"""
    users_data = [
        {"username": "kivanc", "password": "kivanc", "is_admin": True, "role": "admin", "email": "kivancozcan@netmon.com.tr", "full_name": "Kıvanç Özcan"},
        {"username": "burak", "password": "burak", "is_admin": False, "role": "user", "email": "burakgul@netmon.com.tr", "full_name": "Burak Gül"},
        {"username": "gizem", "password": "gizem", "is_admin": False, "role": "user", "email": "gizelolmezboyukucar@netmon.com.tr", "full_name": "Gizem Ölmez Boyukucar"},
    ]
    
    for u_data in users_data:
        existing = User.query.filter_by(username=u_data["username"]).first()
        if existing:
            # Update existing user
            if not existing.email:
                existing.email = u_data["email"]
            if not existing.full_name:
                existing.full_name = u_data["full_name"]
            # Ensure is_active is set (default to True for existing users)
            if not hasattr(existing, 'is_active') or existing.is_active is None:
                existing.is_active = True
        else:
            # Create new user
            user = User(
                username=u_data["username"],
                is_admin=u_data["is_admin"],
                role=u_data["role"],
                email=u_data["email"],
                full_name=u_data["full_name"],
                is_active=True
            )
            user.set_password(u_data["password"])
            db.session.add(user)
    db.session.commit()

# ===================== ROUTES =====================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not email or not password:
            flash("Email ve şifre gereklidir.", "danger")
            return render_template("login.html")
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.email
            session['is_admin'] = user.is_admin
            session['role'] = user.role
            flash(f"Hoş geldiniz, {user.full_name or user.email}!", "success")
            return redirect(url_for("plan_week"))
        else:
            flash("Email veya şifre hatalı.", "danger")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Başarıyla çıkış yapıldı.", "success")
    return redirect(url_for("login"))

@app.route("/admin/users")
@kivanc_required
def admin_users():
    users = User.query.order_by(User.username.asc()).all()
    current_user = get_current_user()
    is_kivanc = current_user and (current_user.username == 'kivanc' or current_user.email == 'kivancozcan@netmon.com.tr')
    return render_template("admin_users.html", users=users, is_kivanc=is_kivanc)

@app.route("/admin/users/add", methods=["GET", "POST"])
@kivanc_required
def admin_user_add():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", "user").strip()
        is_admin = request.form.get("is_admin") == "1"
        is_active = request.form.get("is_active") == "1"
        
        if not email or not password:
            flash("Email ve şifre zorunludur.", "danger")
            return redirect(url_for("admin_user_add"))
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Bu email zaten kullanılıyor.", "danger")
            return redirect(url_for("admin_user_add"))
        
        user = User(
            username=None,
            email=email,
            full_name=full_name if full_name else None,
            role=role,
            is_admin=is_admin,
            is_active=is_active
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Kullanıcı eklendi.", "success")
        return redirect(url_for("admin_users"))
    
    return render_template("admin_user_add.html")

@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@kivanc_required
def admin_user_edit(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == "POST":
        new_role = request.form.get("role", "user").strip()
        new_is_admin = request.form.get("is_admin") == "1"
        new_is_active = request.form.get("is_active") == "1"
        new_password = request.form.get("password", "").strip()
        new_email = request.form.get("email", "").strip()
        new_full_name = request.form.get("full_name", "").strip()
        
        if not new_email:
            flash("Email zorunludur.", "danger")
            return redirect(url_for("admin_user_edit", user_id=user_id))
        
        # Check if email already exists for another user
        existing_user = User.query.filter(User.email == new_email, User.id != user_id).first()
        if existing_user:
            flash("Bu email başka bir kullanıcı tarafından kullanılıyor.", "danger")
            return redirect(url_for("admin_user_edit", user_id=user_id))
        
        # Admin kendisini admin'den çıkaramaz
        if user.id == session['user_id'] and not new_is_admin:
            flash("Kendi admin yetkinizi kaldıramazsınız.", "danger")
            return redirect(url_for("admin_user_edit", user_id=user_id))
        
        # Kullanıcı kendisini pasif yapamaz
        if user.id == session['user_id'] and not new_is_active:
            flash("Kendinizi pasif yapamazsınız.", "danger")
            return redirect(url_for("admin_user_edit", user_id=user_id))
        
        user.role = new_role
        user.is_admin = new_is_admin
        user.is_active = new_is_active
        user.email = new_email
        user.full_name = new_full_name if new_full_name else None
        
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash("Kullanıcı güncellendi.", "success")
        return redirect(url_for("admin_users"))
    
    return render_template("admin_user_edit.html", user=user)

@app.route("/")
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for("plan_week"))


# ---------- PLAN ----------
@app.get("/plan")
@login_required
def plan_week():
    d = parse_date(request.args.get("date", "")) or date.today()
    start = week_start(d)
    days = [start + timedelta(days=i) for i in range(7)]

    # Satirdaki isler (sehir bazli) = region != "-" ; proje sablonlari = region == "-"
    # Projeleri sadece bu haftada is eklenmisse goster
    template_projects = Project.query.filter(Project.is_active == True, Project.region == "-").order_by(Project.project_code.asc(), Project.project_name.asc()).all()
    
    # Once bu haftada is eklenmis projeleri bul
    cells = PlanCell.query.filter(PlanCell.work_date >= days[0], PlanCell.work_date <= days[-1]).all()
    project_ids_with_work = {c.project_id for c in cells}
    
    # Projeleri goster: sadece bu haftada isi olanlari ekle
    base_q = Project.query.filter(Project.region != "-")
    if project_ids_with_work:
        projects = base_q.filter(Project.id.in_(project_ids_with_work))\
            .order_by(Project.region.asc(), Project.project_code.asc()).all()
    else:
        projects = []  # Bu haftada hic is yoksa projeleri gosterme
    
    code_colors = {p.project_code: pastel_color(p.project_code) for p in projects}
    cell_by_key: Dict[Tuple[int, str], PlanCell] = {(c.project_id, iso(c.work_date)): c for c in cells}

    ass_map: Dict[int, list] = {}
    if cells:
        cell_ids = [c.id for c in cells]
        rows = (
            db.session.query(CellAssignment.cell_id, Person.full_name)
            .join(Person, Person.id == CellAssignment.person_id)
            .filter(CellAssignment.cell_id.in_(cell_ids))
            .all()
        )
        for cid, name in rows:
            ass_map.setdefault(cid, []).append(name)

        # Cell person IDs for team signature
        cell_person_ids: Dict[int, list] = {}
        for cid, pid in db.session.query(CellAssignment.cell_id, CellAssignment.person_id).filter(CellAssignment.cell_id.in_(cell_ids)).all():
            cell_person_ids.setdefault(cid, []).append(pid)

    # Calculate grey cells for consecutive same teams
    cell_grey: Dict[Tuple[int, str], bool] = {}
    # Collect per day per team signature projects
    day_signature_projects: Dict[str, Dict[str, list]] = {}
    for cell in cells:
        k = iso(cell.work_date)
        person_ids = sorted(cell_person_ids.get(cell.id, []))
        sig = team_signature(person_ids) if person_ids else None
        if sig:
            if k not in day_signature_projects:
                day_signature_projects[k] = {}
            if sig not in day_signature_projects[k]:
                day_signature_projects[k][sig] = []
            day_signature_projects[k][sig].append(cell.project_id)
    
    # Mark grey if a team signature works in multiple projects on the same day
    for k, sig_dict in day_signature_projects.items():
        for sig, project_ids in sig_dict.items():
            if len(project_ids) > 1:
                for proj_id in project_ids:
                    cell_grey[(proj_id, k)] = True

    people = Person.query.order_by(Person.full_name.asc()).all()
    # Netmon firma ID'sini bul
    netmon_firma = Firma.query.filter_by(name="Netmon").first()
    netmon_firma_id = netmon_firma.id if netmon_firma else None
    
    people_json = []
    for p in people:
        person_data = {
            "id": p.id,
            "full_name": p.full_name,
            "phone": p.phone or "",
            "tc_no": p.tc_no or "",
            "firma_id": p.firma_id,
            "firma_name": p.firma.name if p.firma else None,
            "seviye_name": p.seviye.name if p.seviye else None
        }
        people_json.append(person_data)

    status_map = get_person_status_map(days)

    # Her gün için busy olan personelleri hesapla
    busy_map = {}
    for d in days:
        q = db.session.query(CellAssignment.person_id).join(PlanCell, PlanCell.id == CellAssignment.cell_id)\
            .filter(PlanCell.work_date == d)
        busy_ids = {r[0] for r in q.distinct().all()}
        busy_map[iso(d)] = busy_ids

    # Personel durum özeti
    personnel_summary = {}
    for d in days:
        day_iso = iso(d)
        busy_ids = busy_map[day_iso]
        
        # Seviyeler: Ana kadro, Yardımcı, Alt yüklenici
        summary = {
            "total_available": [],
            "ana_kadro_available": [],
            "yardimci_available": [],
            "alt_yuklenici_available": []
        }
        firm_available = {}
        leave_names = []
        leave_by_firm = {}
        
        for p in people:
            st = status_map.get((p.id, day_iso), "available")
            firm_label = p.firma.name if p.firma else "Firma belirtilmemiş"
            if st == "leave":
                leave_entry = f"{p.full_name} ({firm_label})" if firm_label else p.full_name
                leave_names.append(leave_entry)
                leave_by_firm.setdefault(firm_label, []).append(p.full_name)
                continue  # İzinli olanları sayma
            
            if p.id in busy_ids:
                continue  # Çalışan olanları sayma
            
            # Boşta
            summary["total_available"].append(p.full_name)
            firm_available.setdefault(firm_label, []).append(p.full_name)
            
            seviye_name = p.seviye.name if p.seviye else None
            if seviye_name == "Ana kadro":
                summary["ana_kadro_available"].append(p.full_name)
            elif seviye_name == "Yardımcı":
                summary["yardimci_available"].append(p.full_name)
            elif seviye_name == "Alt yüklenici":
                summary["alt_yuklenici_available"].append(p.full_name)
        
        personnel_summary[day_iso] = {
            "total": len(summary["total_available"]),
            "ana_kadro": len(summary["ana_kadro_available"]),
            "yardimci": len(summary["yardimci_available"]),
            "alt_yuklenici": len(summary["alt_yuklenici_available"]),
            "total_names": summary["total_available"],
            "ana_kadro_names": summary["ana_kadro_available"],
            "yardimci_names": summary["yardimci_available"],
            "alt_yuklenici_names": summary["alt_yuklenici_available"],
            "firm_available": firm_available,
            "firm_available_counts": {k: len(v) for k, v in firm_available.items()},
            "leave": len(leave_names),
            "leave_names": leave_names,
            "leave_by_firm": leave_by_firm
        }

    # iller dropdown: önce TR_CITIES, ayrıca DB'deki mevcut iller (yanlış yazılmış eski şehirler de kaybolmasın)
    existing_cities = [r[0] for r in db.session.query(Project.region).filter(Project.region != '-', Project.region != None).distinct().all()]
    cities = []
    for c in TR_CITIES + sorted(set(existing_cities)):
        if c and c not in cities:
            cities.append(c)

    # Araçları veritabanından çek
    vehicles = Vehicle.query.filter(Vehicle.status == "available").order_by(Vehicle.plate.asc()).all()

    return render_template(
        "plan.html",
        start=start, days=days,
        template_projects=template_projects,
        projects=projects,
        cell_by_key=cell_by_key,
        ass_map=ass_map,
        cell_grey=cell_grey,
        people_json=people_json,
                template_projects_json=[
            {"id":p.id,"project_code":p.project_code,"project_name":p.project_name,"responsible":p.responsible}
            for p in template_projects
        ],
        prev_week=iso(start - timedelta(days=7)),
        next_week=iso(start + timedelta(days=7)),
        selected_week=iso(start),
        week_start_iso=iso(start),
        code_colors=code_colors,
        tr_days=TR_DAYS,
        today_iso=iso(date.today()),
        status_map=status_map,
        personnel_summary=personnel_summary,
        cities=cities,
        vehicles=vehicles
    )


# ---------- PROJECTS ----------
@app.route("/projects", methods=["GET", "POST"])
@login_required
@observer_required
def projects_page():
    if request.method == "POST":
        # Artık proje eklemede il/bölge kullanıcıdan alınmıyor (legacy kolon: region)
        region = "-"
        project_code = request.form.get("project_code", "").strip()
        project_name = request.form.get("project_name", "").strip()
        responsible = request.form.get("responsible", "").strip()
        karsi_firma_sorumlusu = request.form.get("karsi_firma_sorumlusu", "").strip()
        is_active = (request.form.get("is_active") == "1")

        if not all([project_code, project_name, responsible]):
            flash("Zorunlu alanlar boş.", "danger")
            return redirect(url_for("projects_page"))

        db.session.add(Project(region=region, project_code=project_code, project_name=project_name,
                               responsible=responsible, karsi_firma_sorumlusu=karsi_firma_sorumlusu if karsi_firma_sorumlusu else None, is_active=is_active))
        db.session.commit()
        flash("Proje eklendi.", "success")
        return redirect(url_for("projects_page"))

    # Projeler menüsü sadece "proje şablonlarını" gösterir (region == '-')
    # Plan sayfasından eklenen "iş satırları" (region != '-') burada görünmez.
    projects = Project.query.filter(Project.region == "-").order_by(Project.project_code.asc(), Project.project_name.asc()).all()
    users = User.query.filter(User.is_active == True).order_by(User.full_name.asc(), User.username.asc()).all()
    return render_template("projects.html", projects=projects, users=users)



@app.post("/projects/<int:project_id>/delete")
@login_required
@observer_required
def project_delete(project_id: int):
    p = Project.query.get_or_404(project_id)
    db.session.delete(p)
    db.session.commit()
    flash("Proje silindi.", "success")
    return redirect(url_for("projects_page"))

@app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
@observer_required
def project_edit(project_id: int):
    p = Project.query.get_or_404(project_id)
    if request.method == "POST":
        p.project_code = request.form.get("project_code", "").strip()
        p.project_name = request.form.get("project_name", "").strip()
        p.responsible = request.form.get("responsible", "").strip()
        p.karsi_firma_sorumlusu = request.form.get("karsi_firma_sorumlusu", "").strip() or None
        p.is_active = (request.form.get("is_active") == "1")
        if not all([p.project_code, p.project_name, p.responsible]):
            flash("Zorunlu alanlar boş.", "danger")
            return redirect(url_for("project_edit", project_id=project_id))
        db.session.commit()
        flash("Proje güncellendi.", "success")
        return redirect(url_for("projects_page"))
    users = User.query.filter(User.is_active == True).order_by(User.full_name.asc(), User.username.asc()).all()
    return render_template("project_edit.html", p=p, users=users)


@app.route("/projects/<int:project_id>/subproject/add", methods=["GET", "POST"])
@login_required
@observer_required
def subproject_add(project_id: int):
    parent_project = Project.query.get_or_404(project_id)
    
    # Sadece template projeler (region == "-") için alt proje eklenebilir
    if parent_project.region != "-":
        flash("Sadece proje şablonlarına alt proje eklenebilir.", "danger")
        return redirect(url_for("project_edit", project_id=project_id))
    
    if request.method == "POST":
        region = request.form.get("region", "").strip()
        project_code = request.form.get("project_code", "").strip()
        project_name = request.form.get("project_name", "").strip()
        responsible = request.form.get("responsible", "").strip()
        karsi_firma_sorumlusu = request.form.get("karsi_firma_sorumlusu", "").strip()
        is_active = (request.form.get("is_active") == "1")
        
        if not all([region, project_code, project_name, responsible]):
            flash("Zorunlu alanlar boş.", "danger")
            return redirect(url_for("subproject_add", project_id=project_id))
        
        # Aynı proje kodu ve şehir kombinasyonu zaten var mı kontrol et
        existing = Project.query.filter(
            Project.project_code == project_code,
            Project.region == region
        ).first()
        
        if existing:
            flash(f"Bu şehir için zaten bir alt proje mevcut: {existing.project_name}", "danger")
            return redirect(url_for("subproject_add", project_id=project_id))
        
        # Yeni alt proje oluştur
        subproject = Project(
            region=region,
            project_code=project_code,
            project_name=project_name,
            responsible=responsible,
            karsi_firma_sorumlusu=karsi_firma_sorumlusu if karsi_firma_sorumlusu else None,
            is_active=is_active
        )
        db.session.add(subproject)
        db.session.commit()
        flash("Alt proje eklendi.", "success")
        return redirect(url_for("subproject_add", project_id=project_id))
    
    # GET: Formu göster
    users = User.query.filter(User.is_active == True).order_by(User.full_name.asc(), User.username.asc()).all()
    
    # Şehir listesi: TR_CITIES + DB'deki mevcut şehirler
    existing_cities = [r[0] for r in db.session.query(Project.region).filter(Project.region != '-', Project.region != None).distinct().all()]
    cities = []
    for c in TR_CITIES + sorted(set(existing_cities)):
        if c and c not in cities:
            cities.append(c)
    
    # Bu projeye ait mevcut alt projeleri getir
    subprojects = Project.query.filter(
        Project.project_code == parent_project.project_code,
        Project.region != "-",
        Project.id != parent_project.id
    ).order_by(Project.region.asc()).all()
    
    return render_template("subproject_add.html", 
                         parent_project=parent_project, 
                         users=users, 
                         cities=cities,
                         subprojects=subprojects)



# ---------- PEOPLE ----------
@app.route("/people", methods=["GET", "POST"])
@login_required
@observer_required
def people_page():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if not full_name:
            flash("Personel adı zorunlu.", "danger")
            return redirect(url_for("people_page"))

        firma_id = request.form.get("firma_id", "").strip()
        seviye_id = request.form.get("seviye_id", "").strip()
        durum = request.form.get("durum", "Aktif").strip()
        
        db.session.add(Person(
            full_name=full_name,
            tc_no=request.form.get("tc_no", "").strip(),
            role=request.form.get("role", "").strip(),
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip(),
            firma_id=int(firma_id) if firma_id else None,
            seviye_id=int(seviye_id) if seviye_id else None,
            durum=durum,
        ))
        db.session.commit()
        flash("Personel eklendi.", "success")
        return redirect(url_for("people_page"))

    people = Person.query.order_by(Person.full_name.asc()).all()
    firmalar = Firma.query.order_by(Firma.name.asc()).all()  # Tüm firmalar (aktif/pasif)
    seviyeler = Seviye.query.order_by(Seviye.name.asc()).all()  # Tüm seviyeler (aktif/pasif)
    # Check if current user is kivanc
    current_user = get_current_user()
    is_kivanc = current_user and (current_user.username == 'kivanc' or current_user.email == 'kivancozcan@netmon.com.tr')
    return render_template("people.html", people=people, firmalar=firmalar, seviyeler=seviyeler, is_kivanc=is_kivanc)


@app.route("/people/<int:person_id>/edit", methods=["GET", "POST"])
@kivanc_required
def person_edit(person_id: int):
    p = Person.query.get_or_404(person_id)
    
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if not full_name:
            flash("Personel adı zorunlu.", "danger")
            return redirect(url_for("person_edit", person_id=person_id))
        
        firma_id = request.form.get("firma_id", "").strip()
        seviye_id = request.form.get("seviye_id", "").strip()
        durum = request.form.get("durum", "Aktif").strip()
        
        p.full_name = full_name
        p.tc_no = request.form.get("tc_no", "").strip() or None
        p.role = request.form.get("role", "").strip() or None
        p.email = request.form.get("email", "").strip() or None
        p.phone = request.form.get("phone", "").strip() or None
        p.firma_id = int(firma_id) if firma_id else None
        p.seviye_id = int(seviye_id) if seviye_id else None
        p.durum = durum
        
        db.session.commit()
        flash("Personel güncellendi.", "success")
        return redirect(url_for("people_page"))
    
    firmalar = Firma.query.order_by(Firma.name.asc()).all()
    seviyeler = Seviye.query.order_by(Seviye.name.asc()).all()
    return render_template("person_edit.html", p=p, firmalar=firmalar, seviyeler=seviyeler)


@app.post("/people/<int:person_id>/delete")
@login_required
@observer_required
def person_delete(person_id: int):
    p = Person.query.get_or_404(person_id)
    db.session.delete(p)
    db.session.commit()
    flash("Personel silindi.", "success")
    return redirect(url_for("people_page"))


# ---------- TANIMLAR: FIRMA ----------
@app.route("/tanimlar/firma", methods=["GET", "POST"])
@login_required
@observer_required
def firma_page():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Firma adı zorunlu.", "danger")
            return redirect(url_for("firma_page"))
        
        is_active = (request.form.get("is_active") == "1")
        db.session.add(Firma(name=name, is_active=is_active))
        db.session.commit()
        flash("Firma eklendi.", "success")
        return redirect(url_for("firma_page"))
    
    firmalar = Firma.query.order_by(Firma.name.asc()).all()
    return render_template("firma.html", firmalar=firmalar)


@app.post("/tanimlar/firma/<int:firma_id>/delete")
@login_required
@observer_required
def firma_delete(firma_id: int):
    f = Firma.query.get_or_404(firma_id)
    # Check if firma is used by any person
    if Person.query.filter_by(firma_id=firma_id).count() > 0:
        flash("Bu firma personeller tarafından kullanılıyor, silinemez.", "danger")
        if request.referrer and 'people' in request.referrer:
            return redirect(url_for("people_page") + "?tab=firma")
        return redirect(url_for("firma_page"))
    db.session.delete(f)
    db.session.commit()
    flash("Firma silindi.", "success")
    # Eğer people sayfasından geliyorsa oraya dön
    if request.referrer and 'people' in request.referrer:
        return redirect(url_for("people_page") + "?tab=firma")
    return redirect(url_for("firma_page"))


# ---------- TANIMLAR: SEVIYE ----------
@app.route("/tanimlar/seviye", methods=["GET", "POST"])
@login_required
@observer_required
def seviye_page():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Seviye adı zorunlu.", "danger")
            return redirect(url_for("people_page", tab="seviye"))
        
        is_active = (request.form.get("is_active") == "1")
        db.session.add(Seviye(name=name, is_active=is_active))
        db.session.commit()
        flash("Seviye eklendi.", "success")
        return redirect(url_for("people_page") + "?tab=seviye")
    
    seviyeler = Seviye.query.order_by(Seviye.name.asc()).all()
    return render_template("seviye.html", seviyeler=seviyeler)


@app.post("/tanimlar/seviye/<int:seviye_id>/delete")
@login_required
@observer_required
def seviye_delete(seviye_id: int):
    s = Seviye.query.get_or_404(seviye_id)
    # Check if seviye is used by any person
    if Person.query.filter_by(seviye_id=seviye_id).count() > 0:
        flash("Bu seviye personeller tarafından kullanılıyor, silinemez.", "danger")
        if request.referrer and 'people' in request.referrer:
            return redirect(url_for("people_page") + "?tab=seviye")
        return redirect(url_for("seviye_page"))
    db.session.delete(s)
    db.session.commit()
    flash("Seviye silindi.", "success")
    # Eğer people sayfasından geliyorsa oraya dön
    if request.referrer and 'people' in request.referrer:
        return redirect(url_for("people_page") + "?tab=seviye")
    return redirect(url_for("seviye_page"))


# ---------- VEHICLES (ARAÇLAR) ----------
@app.route("/tools", methods=["GET", "POST"])
@login_required
@observer_required
def tools_page():
    if request.method == "POST":
        plate = request.form.get("plate", "").strip().upper()
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        year_str = request.form.get("year", "").strip()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        status = request.form.get("status", "available").strip()
        notes = request.form.get("notes", "").strip()
        
        if not plate or not brand:
            flash("Plaka ve marka zorunlu.", "danger")
            return redirect(url_for("tools_page"))
        
        # Check if plate already exists
        existing = Vehicle.query.filter_by(plate=plate).first()
        if existing:
            flash("Bu plaka zaten kayıtlı.", "danger")
            return redirect(url_for("tools_page"))
        
        year = None
        if year_str:
            try:
                year = int(year_str)
            except ValueError:
                pass
        
        db.session.add(Vehicle(
            plate=plate,
            brand=brand,
            model=model if model else None,
            year=year,
            vehicle_type=vehicle_type if vehicle_type else None,
            status=status if status else "available",
            notes=notes if notes else None,
            created_at=datetime.now()
        ))
        db.session.commit()
        flash("Araç eklendi.", "success")
        return redirect(url_for("tools_page"))
    
    vehicles = Vehicle.query.order_by(Vehicle.plate.asc()).all()
    return render_template("tools.html", vehicles=vehicles)


@app.post("/tools/<int:vehicle_id>/delete")
@login_required
@observer_required
def vehicle_delete(vehicle_id: int):
    v = Vehicle.query.get_or_404(vehicle_id)
    db.session.delete(v)
    db.session.commit()
    flash("Araç silindi.", "success")
    return redirect(url_for("tools_page"))


@app.route("/tools/<int:vehicle_id>/edit", methods=["GET", "POST"])
@login_required
@observer_required
def vehicle_edit(vehicle_id: int):
    v = Vehicle.query.get_or_404(vehicle_id)
    if request.method == "POST":
        plate = request.form.get("plate", "").strip().upper()
        brand = request.form.get("brand", "").strip()
        model = request.form.get("model", "").strip()
        year_str = request.form.get("year", "").strip()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        status = request.form.get("status", "available").strip()
        notes = request.form.get("notes", "").strip()
        
        if not plate or not brand:
            flash("Plaka ve marka zorunlu.", "danger")
            return redirect(url_for("vehicle_edit", vehicle_id=vehicle_id))
        
        # Check if plate already exists for another vehicle
        existing = Vehicle.query.filter(Vehicle.plate == plate, Vehicle.id != vehicle_id).first()
        if existing:
            flash("Bu plaka başka bir araçta kullanılıyor.", "danger")
            return redirect(url_for("vehicle_edit", vehicle_id=vehicle_id))
        
        v.plate = plate
        v.brand = brand
        v.model = model if model else None
        v.vehicle_type = vehicle_type if vehicle_type else None
        v.status = status if status else "available"
        v.notes = notes if notes else None
        
        if year_str:
            try:
                v.year = int(year_str)
            except ValueError:
                v.year = None
        else:
            v.year = None
        
        db.session.commit()
        flash("Araç güncellendi.", "success")
        return redirect(url_for("tools_page"))
    
    return render_template("vehicle_edit.html", v=v)


# ---------- API: CELL GET/SET/CLEAR ----------
@app.get("/api/cell")
def api_cell_get():
    project_id = int(request.args.get("project_id", 0))
    d = parse_date(request.args.get("date", "")) or date.today()

    cell = PlanCell.query.filter_by(project_id=project_id, work_date=d).first()
    if not cell:
        return jsonify({"exists": False, "cell": None, "assigned": []})

    assigned = [a.person_id for a in cell.assignments]
    return jsonify({
        "exists": True,
        "cell": {
            "id": cell.id,
            "project_id": cell.project_id,
            "work_date": iso(cell.work_date),
            "shift": cell.shift or "",
            "vehicle_info": cell.vehicle_info or "",
            "note": cell.note or "",
            "isdp_info": getattr(cell, "isdp_info", "") or "",
            "po_info": getattr(cell, "po_info", "") or "",
            "important_note": getattr(cell, "important_note", "") or "",
            "team_id": cell.team_id or None,
            "team_name": cell.team_name or "",
            "job_mail_body": getattr(cell, "job_mail_body", "") or "",
            "lld_hhd_files": _parse_files(getattr(cell, "lld_hhd_files", None)) or ([cell.lld_hhd_path] if getattr(cell, "lld_hhd_path", None) else []),
            "tutanak_files": _parse_files(getattr(cell, "tutanak_files", None)) or ([cell.tutanak_path] if getattr(cell, "tutanak_path", None) else []),
        },
        "assigned": assigned
    })


@app.get("/api/assignments_week")
@login_required
def api_assignments_week():
    ws = parse_date(request.args.get("week_start", "")) or week_start(date.today())
    start = ws
    end = ws + timedelta(days=6)

    assignments = {}
    cells = PlanCell.query.filter(PlanCell.work_date >= start, PlanCell.work_date <= end).all()
    for cell in cells:
        d = iso(cell.work_date)
        if d not in assignments:
            assignments[d] = set()
        # assignments ilişkisi CellAssignment objeleri döner; person_id'leri ekleyelim
        for ass in cell.assignments:
            if ass and ass.person_id:
                assignments[d].add(int(ass.person_id))

    # dict values set'ten list'e çevir
    for d in assignments:
        assignments[d] = list(assignments[d])

    return jsonify({"ok": True, "assignments": assignments})


@app.post("/api/cell")
@login_required
@observer_required
def api_cell_set():
    try:
        data = request.get_json(force=True, silent=True) or {}
        project_id = int(data.get("project_id", 0))
        d = parse_date(data.get("work_date", "")) or date.today()

        shift = (data.get("shift") or "").strip()
        vehicle_info = (data.get("vehicle_info") or "").strip()
        note = (data.get("note") or "").strip()
        isdp_info = (data.get("isdp_info") or "").strip()
        po_info = (data.get("po_info") or "").strip()
        important_note = (data.get("important_note") or "").strip()
        team_name = (data.get("team_name") or "").strip()
        job_mail_body = (data.get("job_mail_body") or "").strip()
        remove_lld_names = _parse_files(data.get("remove_lld_list"))
        remove_tutanak_names = _parse_files(data.get("remove_tutanak_list"))
        person_ids = [int(pid) for pid in data.get("person_ids", []) if pid]

        cell = ensure_cell(project_id, d)
        cell.shift = shift if shift else None
        cell.vehicle_info = vehicle_info if vehicle_info else None
        cell.note = note if note else None
        cell.isdp_info = isdp_info if isdp_info else None
        cell.po_info = po_info if po_info else None
        cell.important_note = important_note if important_note else None
        cell.job_mail_body = job_mail_body if job_mail_body else None

        # Personel durum kontrolü (izinli / ofis / üretimde ise işe yazma)
        blocked = []
        if person_ids:
            rows = PersonDayStatus.query.filter(
                PersonDayStatus.work_date == d,
                PersonDayStatus.person_id.in_(person_ids)
            ).all()
            st_map = {r.person_id: r.status for r in rows}
            for pid in person_ids:
                st = st_map.get(pid)
                if st in ("leave", "office", "production"):
                    p = Person.query.get(pid)
                    blocked.append({
                        "person_id": pid,
                        "full_name": p.full_name if p else str(pid),
                        "status": st
                    })

        if blocked:
            return jsonify({
                "ok": False,
                "error": "İzinli / Ofis / Üretimde olan personel işe yazılamaz.",
                "blocked": blocked
            }), 400

        # Ekip çakışması kontrolü: Aynı gün başka bir projede çalışan ekip kontrolü
        # "Başka işte olanları göster" işaretliyse bu kontrolü atla
        allow_conflicting_team = data.get("allow_conflicting_team", False)
        if person_ids and not allow_conflicting_team:
            # Tüm personellerin aynı gün atandığı hücreleri bul
            cells_with_all_people = (
                db.session.query(PlanCell.id)
                .join(CellAssignment, CellAssignment.cell_id == PlanCell.id)
                .filter(PlanCell.work_date == d)
                .filter(PlanCell.project_id != project_id)  # Mevcut proje hariç
                .filter(CellAssignment.person_id.in_(person_ids))
                .group_by(PlanCell.id)
                .having(db.func.count(db.func.distinct(CellAssignment.person_id)) == len(person_ids))
                .all()
            )
            
            # Bu hücrelerde sadece bu personeller mi var kontrol et
            for (cell_id,) in cells_with_all_people:
                cell_person_ids = [
                    a.person_id for a in CellAssignment.query.filter_by(cell_id=cell_id).all()
                ]
                if sorted(cell_person_ids) == sorted(person_ids):
                    conflicting_cell = PlanCell.query.get(cell_id)
                    if conflicting_cell:
                        conflicting_project = Project.query.get(conflicting_cell.project_id)
                        return jsonify({
                            "ok": False,
                            "error": f"Bu ekip aynı gün başka bir projede çalışıyor: {conflicting_project.project_code if conflicting_project else 'Bilinmeyen Proje'}",
                            "conflicting_project": conflicting_project.project_code if conflicting_project else None
                        }), 400

        # assignment + ekip (team_id)
        set_assignments_and_team(cell, person_ids)

        # ekip adı (rapor için)
        if team_name:
            cell.team_name = team_name
        else:
            if cell.team_id:
                t = Team.query.get(cell.team_id)
                cell.team_name = (t.name if t else None)
            else:
                cell.team_name = None

        # remove attachments if requested
        # remove selected attachments
        if remove_lld_names:
            current = _parse_files(cell.lld_hhd_files)
            remaining = [f for f in current if f not in remove_lld_names]
            for fname in current:
                if fname in remove_lld_names:
                    delete_upload(fname)
            cell.lld_hhd_files = _dump_files(remaining) if remaining else None
            if cell.lld_hhd_path and cell.lld_hhd_path in remove_lld_names:
                delete_upload(cell.lld_hhd_path)
                cell.lld_hhd_path = None
        if remove_tutanak_names:
            current = _parse_files(cell.tutanak_files)
            remaining = [f for f in current if f not in remove_tutanak_names]
            for fname in current:
                if fname in remove_tutanak_names:
                    delete_upload(fname)
            cell.tutanak_files = _dump_files(remaining) if remaining else None
            if cell.tutanak_path and cell.tutanak_path in remove_tutanak_names:
                delete_upload(cell.tutanak_path)
                cell.tutanak_path = None

        # updated_at'i güncelle
        cell.updated_at = datetime.now()

        db.session.commit()
        socketio.emit('update_table', namespace='/')
        return jsonify({"ok": True, "cell_id": cell.id, "team_id": cell.team_id, "team_name": cell.team_name or ""})
    except Exception as e:
        db.session.rollback()
        print(f"api_cell_set error: {str(e)}")  # Debug için
        return jsonify({"ok": False, "error": f"Kaydetme hatası: {str(e)}"}), 500


@app.post("/api/cell/upload_attachments")
@login_required
@observer_required
def api_cell_upload_attachments():
    try:
        project_id = int(request.form.get("project_id", 0))
        d = parse_date(request.form.get("work_date", "")) or date.today()
        if not project_id:
            return jsonify({"ok": False, "error": "Geçersiz proje"}), 400

        cell = ensure_cell(project_id, d)
        prefix = f"{project_id}-{iso(d)}"
        updated = {}

        lld_files = request.files.getlist("lld_hhd")
        if lld_files:
            cur = _parse_files(cell.lld_hhd_files)
            for fs in lld_files:
                if fs and fs.filename:
                    fname = save_uploaded_file(fs, f"lldhhd-{prefix}")
                    cur.append(fname)
            if cur:
                cell.lld_hhd_files = _dump_files(cur)
                updated["lld_hhd_files"] = cur

        tutanak_files = request.files.getlist("tutanak")
        if tutanak_files:
            cur = _parse_files(cell.tutanak_files)
            for fs in tutanak_files:
                if fs and fs.filename:
                    fname = save_uploaded_file(fs, f"tutanak-{prefix}")
                    cur.append(fname)
            if cur:
                cell.tutanak_files = _dump_files(cur)
                updated["tutanak_files"] = cur

        cell.updated_at = datetime.now()
        db.session.commit()
        socketio.emit('update_table', namespace='/')
        return jsonify({"ok": True, **updated})
    except ValueError as ve:
        return jsonify({"ok": False, "error": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"Yükleme hatası: {str(e)}"}), 500
@login_required
@observer_required
def api_cell_clear():
    data = request.get_json(force=True, silent=True) or {}
    project_id = int(data.get("project_id", 0))
    d = parse_date(data.get("work_date", "")) or date.today()

    cell = PlanCell.query.filter_by(project_id=project_id, work_date=d).first()
    if not cell:
        return jsonify({"ok": True, "cleared": False})

    apply_snapshot(cell, {"exists": False})
    cell.updated_at = datetime.now()
    db.session.commit()
    socketio.emit('update_table', namespace='/')
    return jsonify({"ok": True, "cleared": True})


# ---------- API: PLAN SYNC (Eş zamanlı güncelleme) ----------
@app.get("/api/plan_sync")
@login_required
def api_plan_sync():
    """Hafta için son güncelleme zamanını döndürür"""
    d = parse_date(request.args.get("date", "")) or date.today()
    start = week_start(d)
    end = start + timedelta(days=6)
    
    # Bu hafta için en son güncellenen cell'in updated_at'ini bul
    last_update = db.session.query(db.func.max(PlanCell.updated_at)).filter(
        PlanCell.work_date >= start,
        PlanCell.work_date <= end
    ).scalar()
    
    # En son güncelleme zamanını hesapla
    max_timestamp = None
    if last_update:
        max_timestamp = last_update.timestamp()
    
    return jsonify({
        "ok": True,
        "last_update": max_timestamp,
        "last_update_str": last_update.isoformat() if last_update else None
    })


# ---------- API: CELL TEAM REPORT (Modal tablo) ----------
@app.get("/api/cell_team_report")
def api_cell_team_report():
    project_id = int(request.args.get("project_id", 0))
    d = parse_date(request.args.get("date", "")) or date.today()

    cell = PlanCell.query.filter_by(project_id=project_id, work_date=d).first()
    if not cell:
        return jsonify({"ok": False, "error": "Bu hücrede kayıt yok."}), 404

    project = Project.query.get(project_id)
    persons = (
        db.session.query(Person.full_name, Person.phone, Person.tc_no)
        .join(CellAssignment, CellAssignment.person_id == Person.id)
        .filter(CellAssignment.cell_id == cell.id)
        .order_by(Person.full_name.asc())
        .all()
    )

    rows = [{"full_name": n, "phone": ph or "", "tc": tc or ""} for (n, ph, tc) in persons]

    return jsonify({
        "ok": True,
        "date": iso(d),
        "city": project.region if project else "",
        "project_code": project.project_code if project else "",
        "project_name": project.project_name if project else "",
        "shift": cell.shift or "",
        "vehicle": cell.vehicle_info or "",
        "note": cell.note or "",
        "people": rows
    })


# ---------- API: TEAM MEMBERS (Ekip kiYileri) ----------
@app.get("/api/team_members")
@login_required
def api_team_members():
    """Ekip adŽñ veya ID'ye gAre kiYileri dAnderir (imza veya haftalŽñk kayŽñtlar A¬zerinden)."""
    team_name = (request.args.get("name") or request.args.get("team_name") or "").strip()
    team_id = int(request.args.get("team_id", 0) or 0)
    ws = parse_date(request.args.get("week_start", ""))
    start = ws if ws else None
    end = (ws + timedelta(days=6)) if ws else None

    if team_id and not team_name:
        t = Team.query.get(team_id)
        if t:
            team_name = t.name or ""

    people_rows = []
    source = None

    # 1) Team tablosundaki imzadan oku
    if team_id:
        t = Team.query.get(team_id)
        if t and t.signature:
            try:
                ids = [int(x) for x in t.signature.split(",") if x.strip()]
            except Exception:
                ids = []
            if ids:
                people_rows = Person.query.filter(Person.id.in_(ids)).order_by(Person.full_name.asc()).all()
                source = "team_signature"

    # 2) İmza bulunamazsa, o isimle planlanan kayŽñtlardan kiYileri topla
    if (not people_rows) and team_name:
        q = (
            db.session.query(
                Person.id, Person.full_name, Person.phone, Person.tc_no,
                Firma.name.label("firma_name"),
                Seviye.name.label("seviye_name")
            )
            .join(CellAssignment, CellAssignment.person_id == Person.id)
            .join(PlanCell, PlanCell.id == CellAssignment.cell_id)
            .outerjoin(Team, Team.id == PlanCell.team_id)
            .outerjoin(Firma, Firma.id == Person.firma_id)
            .outerjoin(Seviye, Seviye.id == Person.seviye_id)
            .filter(or_(Team.name == team_name, PlanCell.team_name == team_name))
        )
        if start and end:
            q = q.filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        people_rows = q.distinct().order_by(Person.full_name.asc()).all()
        source = "week_cells"

    if not people_rows:
        return jsonify({"ok": False, "error": "Ekip bulunamadŽñ"}), 404

    def _row_to_dict(row):
        if isinstance(row, Person):
            return {
                "id": row.id,
                "full_name": row.full_name,
                "phone": row.phone or "",
                "tc": row.tc_no or "",
                "firma": row.firma.name if row.firma else "",
                "seviye": row.seviye.name if row.seviye else ""
            }
        pid, fullname, phone, tc, fname, sname = row
        return {
            "id": pid,
            "full_name": fullname,
            "phone": phone or "",
            "tc": tc or "",
            "firma": fname or "",
            "seviye": sname or ""
        }

    resolved_name = team_name
    if not resolved_name and team_id:
        t = Team.query.get(team_id)
        resolved_name = t.name if t else ""

    return jsonify({
        "ok": True,
        "team_name": resolved_name,
        "source": source or "",
        "people": [_row_to_dict(r) for r in people_rows]
    })


# ---------- API: Person Assigned Check (Personel atama kontrolü) ----------
@app.get("/api/person_assigned")
@login_required
def api_person_assigned():
    """Belirli bir günde personelin başka bir projede çalışıp çalışmadığını kontrol et"""
    d = parse_date(request.args.get("date", "")) or date.today()
    current_project_id = int(request.args.get("current_project_id", 0) or 0)
    
    # O gün başka bir projede çalışan personelleri bul
    assigned_person_ids = (
        db.session.query(CellAssignment.person_id)
        .join(PlanCell, PlanCell.id == CellAssignment.cell_id)
        .filter(PlanCell.work_date == d)
        .filter(PlanCell.project_id != current_project_id)  # Mevcut proje hariç
        .distinct()
        .all()
    )
    
    assigned_ids = [row[0] for row in assigned_person_ids]
    
    # Personel bilgilerini de al
    assigned_people = []
    if assigned_ids:
        people = Person.query.filter(Person.id.in_(assigned_ids)).all()
        for p in people:
            # Hangi projede çalıştığını bul
            cells = (
                db.session.query(PlanCell.project_id, Project.project_code)
                .join(Project, Project.id == PlanCell.project_id)
                .join(CellAssignment, CellAssignment.cell_id == PlanCell.id)
                .filter(PlanCell.work_date == d)
                .filter(PlanCell.project_id != current_project_id)
                .filter(CellAssignment.person_id == p.id)
                .first()
            )
            project_code = cells[1] if cells else "Bilinmeyen"
            assigned_people.append({
                "person_id": p.id,
                "full_name": p.full_name,
                "project_code": project_code
            })
    
    return jsonify({
        "ok": True,
        "assigned_person_ids": assigned_ids,
        "assigned_people": assigned_people
    })


# ---------- API: Team Conflict Check (Ekip çakışması kontrolü) ----------
@app.get("/api/team_conflict")
@login_required
def api_team_conflict():
    """Seçilen personellerden oluşan ekibin aynı gün başka bir projede çalışıp çalışmadığını kontrol et"""
    d = parse_date(request.args.get("date", "")) or date.today()
    person_ids_str = request.args.get("person_ids", "")
    current_project_id = int(request.args.get("current_project_id", 0) or 0)
    
    if not person_ids_str:
        return jsonify({"ok": True, "has_conflict": False})
    
    try:
        person_ids = [int(pid.strip()) for pid in person_ids_str.split(",") if pid.strip()]
    except:
        return jsonify({"ok": False, "error": "Geçersiz person_ids"}), 400
    
    if not person_ids:
        return jsonify({"ok": True, "has_conflict": False})
    
    # Tüm personellerin aynı gün atandığı hücreleri bul
    cells_with_all_people = (
        db.session.query(PlanCell.id, PlanCell.project_id)
        .join(CellAssignment, CellAssignment.cell_id == PlanCell.id)
        .filter(PlanCell.work_date == d)
        .filter(PlanCell.project_id != current_project_id)  # Mevcut proje hariç
        .filter(CellAssignment.person_id.in_(person_ids))
        .group_by(PlanCell.id)
        .having(db.func.count(db.func.distinct(CellAssignment.person_id)) == len(person_ids))
        .all()
    )
    
    # Bu hücrelerde sadece bu personeller mi var kontrol et
    conflicting_projects = []
    for cell_id, project_id in cells_with_all_people:
        cell_person_ids = [
            a.person_id for a in CellAssignment.query.filter_by(cell_id=cell_id).all()
        ]
        if sorted(cell_person_ids) == sorted(person_ids):
            conflicting_cell = PlanCell.query.get(cell_id)
            if conflicting_cell:
                conflicting_project = Project.query.get(conflicting_cell.project_id)
                if conflicting_project:
                    conflicting_projects.append({
                        "project_id": conflicting_cell.project_id,
                        "project_code": conflicting_project.project_code,
                        "project_name": conflicting_project.project_name
                    })
    
    has_conflict = len(conflicting_projects) > 0
    return jsonify({
        "ok": True,
        "has_conflict": has_conflict,
        "conflicting_projects": conflicting_projects
    })


# ---------- API: Availability (plan ekranında) ----------
@app.get("/api/availability")
def api_availability():
    d = parse_date(request.args.get("date", "")) or date.today()
    shift = (request.args.get("shift") or "").strip()

    # izinli/üretimde olanları çek
    st_rows = PersonDayStatus.query.filter_by(work_date=d).all()
    status_by_person = {r.person_id: r.status for r in st_rows}

    # çalışanlar
    q = db.session.query(CellAssignment.person_id).join(PlanCell, PlanCell.id == CellAssignment.cell_id)\
        .filter(PlanCell.work_date == d)
    if shift:
        # Hem yeni hem eski formatı kontrol et
        normalized_shift = normalize_shift(shift)
        q = q.filter(db.or_(PlanCell.shift == shift, PlanCell.shift == normalized_shift))
    busy_ids = {r[0] for r in q.distinct().all()}

    people = Person.query.order_by(Person.full_name.asc()).all()

    # “boşta” = çalışmıyor + status available (default)
    available = []
    busy = []
    leave = []
    production = []

    for p in people:
        st = status_by_person.get(p.id, "available")
        if st == "leave":
            leave.append({"id": p.id, "name": p.full_name})
            continue
        if st == "production":
            production.append({"id": p.id, "name": p.full_name})
            continue

        if p.id in busy_ids:
            busy.append({"id": p.id, "name": p.full_name})
        else:
            available.append({"id": p.id, "name": p.full_name})

    return jsonify({
        "date": iso(d),
        "shift": shift,
        "available": available,
        "busy": busy,
        "leave": leave,
        "production": production
    })


# ---------- API: Person day status set ----------
@app.get("/api/person_status_day")
def api_person_status_day():
    d = parse_date(request.args.get("date", "")) or date.today()
    rows = PersonDayStatus.query.filter_by(work_date=d).all()
    status_by_person = {str(r.person_id): {"status": r.status, "note": r.note or ""} for r in rows}
    return jsonify({"ok": True, "date": iso(d), "status_by_person": status_by_person})

@app.get("/api/person_status_week")
def api_person_status_week():
    ws = parse_date(request.args.get("week_start", "")) or week_start(date.today())
    start = ws
    end = ws + timedelta(days=6)
    rows = PersonDayStatus.query.filter(PersonDayStatus.work_date >= start,
                                        PersonDayStatus.work_date <= end).all()
    out = {}
    for r in rows:
        pid = str(r.person_id)
        out.setdefault(pid, {})[iso(r.work_date)] = {"status": r.status, "note": r.note or ""}
    return jsonify({"ok": True, "week_start": iso(ws), "status_by_person": out})

@app.get("/api/person_week")
def api_person_week():
    ws = parse_date(request.args.get("week_start", "")) or week_start(date.today())
    person_id = int(request.args.get("person_id", 0) or 0)
    if not person_id:
        return jsonify({"ok": False, "error": "person_id eksik"}), 400

    start = ws
    end = ws + timedelta(days=6)

    rows = (
        db.session.query(PlanCell.work_date, PlanCell.shift, PlanCell.vehicle_info, PlanCell.note,
                         Project.project_code, Project.region, Project.project_name)
        .join(Project, Project.id == PlanCell.project_id)
        .join(CellAssignment, CellAssignment.cell_id == PlanCell.id)
        .filter(CellAssignment.person_id == person_id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        .order_by(PlanCell.work_date.asc(),
                  db.case((PlanCell.shift == "Gündüz", 1),
                          (PlanCell.shift == "Gündüz Yol", 2),
                          (PlanCell.shift == "Gece", 3),
                          else_=9).asc(),
                  Project.project_code.asc())
        .all()
    )

    items = []
    for wd, shift, vehicle, note, pcode, city, pname in rows:
        items.append({
            "date": iso(wd),
            "shift": shift or "",
            "vehicle": vehicle or "",
            "note": note or "",
            "project_code": pcode or "",
            "city": (city or "").strip(),
            "project_name": pname or "",
        })

    p = Person.query.get(person_id)
    return jsonify({
        "ok": True,
        "week_start": iso(ws),
        "person": {
            "id": person_id,
            "full_name": p.full_name if p else f"#{person_id}",
            "team": p.team or ""
        },
        "items": items
    })

@app.post("/api/person_status")
@login_required
@observer_required
def api_person_status():
    data = request.get_json(force=True, silent=True) or {}
    person_id = int(data.get("person_id", 0))
    d = parse_date(data.get("work_date", "")) or date.today()
    status = (data.get("status") or "available").strip()
    note = (data.get("note") or "").strip()
    isdp_info = (data.get("isdp_info") or "").strip()
    po_info = (data.get("po_info") or "").strip()

    if status not in ("available", "leave", "office", "production"):
        return jsonify({"ok": False, "error": "status geçersiz"}), 400

    row = PersonDayStatus.query.filter_by(person_id=person_id, work_date=d).first()
    if not row:
        row = PersonDayStatus(person_id=person_id, work_date=d, status=status, note=note or None)
        db.session.add(row)
    else:
        row.status = status
        row.note = note or None

    # available seçildiyse satırı silelim (db şişmesin)
    if status == "available":
        db.session.delete(row)

    db.session.commit()
    return jsonify({"ok": True})


# ---------- COPY ----------
@app.post("/api/copy_monday_to_week")
@login_required
@observer_required
def api_copy_monday_to_week():
    data = request.get_json(force=True, silent=True) or {}
    project_id = int(data.get("project_id", 0))
    ws = parse_date(data.get("week_start", ""))

    if not project_id or not ws:
        return jsonify({"ok": False, "error": "project_id / week_start eksik"}), 400

    src = PlanCell.query.filter_by(project_id=project_id, work_date=ws).first()
    snap = snapshot_cell(src)

    for i in range(1, 7):
        dst = ensure_cell(project_id, ws + timedelta(days=i))
        apply_snapshot(dst, snap)

    db.session.commit()
    socketio.emit('update_table', namespace='/')
    return jsonify({"ok": True})


@app.post("/api/copy_week_to_next")
@login_required
@observer_required
def api_copy_week_to_next():
    data = request.get_json(force=True, silent=True) or {}
    ws = parse_date(data.get("week_start", ""))
    if not ws:
        return jsonify({"ok": False, "error": "week_start eksik"}), 400

    src_start = ws
    src_end = ws + timedelta(days=6)
    dst_start = ws + timedelta(days=7)

    src_cells = PlanCell.query.filter(PlanCell.work_date >= src_start, PlanCell.work_date <= src_end).all()
    src_map: Dict[Tuple[int, date], PlanCell] = {(c.project_id, c.work_date): c for c in src_cells}

    for p in Project.query.all():
        for i in range(7):
            dst = ensure_cell(p.id, dst_start + timedelta(days=i))
            apply_snapshot(dst, snapshot_cell(src_map.get((p.id, src_start + timedelta(days=i)))))

    db.session.commit()
    socketio.emit('update_table', namespace='/')
    return jsonify({"ok": True})


@app.post("/api/copy_week_from_previous")
@login_required
@observer_required
def api_copy_week_from_previous():
    """Önceki haftayı mevcut haftaya kopyala - Tüm projeler ve hücreler"""
    data = request.get_json(force=True, silent=True) or {}
    ws = parse_date(data.get("week_start", ""))
    if not ws:
        return jsonify({"ok": False, "error": "week_start eksik"}), 400

    # Önceki hafta (kaynak)
    src_start = ws - timedelta(days=7)
    src_end = src_start + timedelta(days=6)
    # Mevcut hafta (hedef)
    dst_start = ws
    dst_end = ws + timedelta(days=6)

    # Önceki haftanın mevcut hafta olup olmadığını kontrol et
    today = date.today()
    today_week_start = week_start(today)
    src_is_current_week = (src_start == today_week_start)

    # Önceki haftada hangi projeler var (hem dolu hem boş hücreler için)
    src_cells = PlanCell.query.filter(PlanCell.work_date >= src_start, PlanCell.work_date <= src_end).all()
    src_project_ids_with_work = {c.project_id for c in src_cells}
    
    # Önceki haftada görünen tüm projeleri al
    # plan_week() mantığına göre: mevcut hafta ise tüm aktif projeler, değilse sadece iş eklenmiş projeler
    if src_is_current_week:
        # Önceki hafta mevcut hafta ise: TÜM aktif projeleri kopyala
        src_projects = Project.query.filter(
            Project.is_active == True,
            Project.region != '-'
        ).order_by(Project.region.asc(), Project.project_code.asc()).all()
    else:
        # Önceki hafta geçmiş/gelecek hafta ise: Sadece o haftada iş eklenmiş projeleri kopyala
        if not src_project_ids_with_work:
            return jsonify({"ok": False, "error": "Önceki haftada kopyalanacak veri bulunamadı."}), 400
        
        src_projects = Project.query.filter(
            Project.is_active == True,
            Project.region != '-',
            Project.id.in_(src_project_ids_with_work)
        ).order_by(Project.region.asc(), Project.project_code.asc()).all()
    
    if not src_projects:
        return jsonify({"ok": False, "error": "Önceki haftada kopyalanacak proje bulunamadı."}), 400
    
    src_map: Dict[Tuple[int, date], PlanCell] = {(c.project_id, c.work_date): c for c in src_cells}
    copied_count = 0
    projects_copied = 0

    # Önceki haftada görünen her proje için
    for project in src_projects:
        project_id = project.id
        projects_copied += 1
        
        # 7 günün tamamını kopyala (dolu olsun boş olsun)
        for i in range(7):
            src_date = src_start + timedelta(days=i)
            dst_date = dst_start + timedelta(days=i)
            src_cell = src_map.get((project_id, src_date))
            
            # Hücre oluştur (boş bile olsa)
            dst = ensure_cell(project_id, dst_date)
            
            if src_cell:
                # Dolu hücre varsa içeriğini kopyala
                apply_snapshot(dst, snapshot_cell(src_cell))
                copied_count += 1
            # Boş hücre de oluşturuldu, böylece proje görünecek

    db.session.commit()
    socketio.emit('update_table', namespace='/')
    return jsonify({
        "ok": True, 
        "copied_count": copied_count,
        "projects_copied": projects_copied,
        "message": f"{projects_copied} proje ve {copied_count} hücre kopyalandı."
    })


@app.post("/api/project_create_from_plan")
@login_required
@observer_required
def api_project_create_from_plan():
    data = request.get_json(force=True, silent=True) or {}
    region = (data.get("city") or "").strip()  # city stored in legacy region column
    project_id = int(data.get("template_project_id") or 0)
    week_start_str = data.get("week_start", "")

    if not region:
        return jsonify({"ok": False, "error": "Şehir seçin."}), 400

    if not project_id:
        return jsonify({"ok": False, "error": "Proje seçin."}), 400

    t = Project.query.get(project_id)
    if not t or t.region != "-":
        return jsonify({"ok": False, "error": "Proje şablonu bulunamadı."}), 404

    p = Project(region=region, project_code=t.project_code, project_name=t.project_name,
                responsible=t.responsible, karsi_firma_sorumlusu=t.karsi_firma_sorumlusu, is_active=True)
    db.session.add(p)
    db.session.flush()  # ID'yi almak için
    
    # Eğer week_start belirtilmişse, o hafta için bir PlanCell oluştur (projenin o haftada görünmesi için)
    if week_start_str:
        ws = parse_date(week_start_str)
        if ws:
            # Haftanın ilk günü için boş bir hücre oluştur (projenin o haftada görünmesi için)
            ensure_cell(p.id, ws)
            db.session.commit()
            socketio.emit('update_table')
        else:
            db.session.commit()
            socketio.emit('update_table')
    else:
        db.session.commit()
        socketio.emit('update_table')
    
    return jsonify({"ok": True, "project_id": p.id, "existed": False})


@app.get("/api/project_codes_by_template")
@login_required
def api_project_codes_by_template():
    """Seçilen proje şablonuna göre alt proje kodlarını getir (aynı proje koduna sahip farklı şehirlerdeki projeler)"""
    template_id = int(request.args.get("template_id", 0))
    if not template_id:
        return jsonify({"ok": False, "error": "Template ID gerekli"}), 400
    
    template = Project.query.get(template_id)
    if not template or template.region != "-":
        return jsonify({"ok": False, "error": "Proje şablonu bulunamadı"}), 404
    
    # Aynı proje koduna sahip tüm projeleri bul (şablon hariç, sadece region != "-" olanlar)
    similar_projects = Project.query.filter(
        Project.project_code == template.project_code,
        Project.region != "-",
        Project.is_active == True
    ).order_by(Project.region.asc()).all()
    
    codes = [{"region": p.region, "project_code": p.project_code, "project_name": p.project_name} for p in similar_projects]
    
    return jsonify({"ok": True, "codes": codes, "base_code": template.project_code})


@app.get("/api/project_codes_by_code")
@login_required
def api_project_codes_by_code():
    """Proje koduna göre alt proje kodlarını getir (aynı proje koduna sahip farklı şehirlerdeki projeler)"""
    project_code = request.args.get("project_code", "").strip()
    if not project_code:
        return jsonify({"ok": False, "error": "Proje kodu gerekli"}), 400
    
    # Aynı proje koduna sahip tüm projeleri bul (sadece region != "-" olanlar)
    similar_projects = Project.query.filter(
        Project.project_code == project_code,
        Project.region != "-",
        Project.is_active == True
    ).order_by(Project.region.asc()).all()
    
    codes = [{"region": p.region, "project_code": p.project_code, "project_name": p.project_name, "project_id": p.id} for p in similar_projects]
    
    return jsonify({"ok": True, "codes": codes, "base_code": project_code})


@app.post("/api/plan_row_update")
@login_required
@observer_required
def api_plan_row_update():
    """Plan satırını güncelle: şehir ve proje şablonu değiştir."""
    data = request.get_json(force=True, silent=True) or {}
    row_project_id = int(data.get("project_id") or 0)
    region = (data.get("city") or "").strip()
    template_project_id = int(data.get("template_project_id") or 0)

    if not row_project_id or not region or not template_project_id:
        return jsonify({"ok": False, "error": "project_id/city/template_project_id eksik"}), 400

    row_p = Project.query.get(row_project_id)
    if not row_p or row_p.region == "-":
        return jsonify({"ok": False, "error": "Satır bulunamadı."}), 404

    t = Project.query.get(template_project_id)
    if not t or t.region != "-":
        return jsonify({"ok": False, "error": "Proje şablonu bulunamadı."}), 404

    dup = Project.query.filter(Project.id != row_project_id, Project.region == region, Project.project_code == t.project_code).first()
    if dup:
        return jsonify({"ok": False, "error": "Bu il + proje zaten var."}), 400

    row_p.region = region
    row_p.project_code = t.project_code
    row_p.project_name = t.project_name
    row_p.responsible = t.responsible
    row_p.karsi_firma_sorumlusu = t.karsi_firma_sorumlusu
    row_p.is_active = True
    db.session.commit()
    socketio.emit('update_table', namespace='/')
    return jsonify({"ok": True})


@app.post("/api/plan_row_delete")
@login_required
@observer_required
def api_plan_row_delete():
    """Plan satırını sil: satırın proje kaydı (region != '-') ve tüm hücreleri/atamaları silinir."""
    data = request.get_json(force=True, silent=True) or {}
    row_project_id = int(data.get("project_id") or 0)
    if not row_project_id:
        return jsonify({"ok": False, "error": "project_id eksik"}), 400

    p = Project.query.get(row_project_id)
    if not p or p.region == "-":
        return jsonify({"ok": False, "error": "Satır bulunamadı."}), 404

    cells = PlanCell.query.filter_by(project_id=row_project_id).all()
    cell_ids = [c.id for c in cells]
    if cell_ids:
        CellAssignment.query.filter(CellAssignment.cell_id.in_(cell_ids)).delete(synchronize_session=False)
        PlanCell.query.filter(PlanCell.id.in_(cell_ids)).delete(synchronize_session=False)

    db.session.delete(p)
    db.session.commit()
    socketio.emit('update_table')
    return jsonify({"ok": True})


# ---------- DRAG DROP ----------
@app.post("/api/move_cell")
@login_required
@observer_required
def api_move_cell():
    """
    Hücre içeriğini sürükle-bırak ile taşı / yer değiştir.
    - Aynı proje satırı içinde veya farklı projeler arasında çalışır.
    - mode: "swap" (varsayılan) veya "move"
    """
    data = request.get_json(force=True, silent=True) or {}
    from_project_id = int(data.get("from_project_id") or data.get("project_id") or 0)
    to_project_id = int(data.get("to_project_id") or data.get("project_id") or 0)
    from_d = parse_date(data.get("from_date", ""))
    to_d = parse_date(data.get("to_date", ""))
    mode = (data.get("mode") or "swap").strip().lower()

    if not from_project_id or not to_project_id or not from_d or not to_d:
        return jsonify({"ok": False, "error": "from/to project_id veya from/to_date eksik"}), 400
    if from_project_id == to_project_id and from_d == to_d:
        return jsonify({"ok": True})

    src = PlanCell.query.filter_by(project_id=from_project_id, work_date=from_d).first()
    dst = PlanCell.query.filter_by(project_id=to_project_id, work_date=to_d).first()

    src_snap = snapshot_cell(src)
    dst_snap = snapshot_cell(dst)

    # hücreleri garanti altına al (boş hücreye bırakınca da oluşsun)
    src = src or ensure_cell(from_project_id, from_d)
    dst = dst or ensure_cell(to_project_id, to_d)

    if mode == "move":
        apply_snapshot(dst, src_snap)
        apply_snapshot(src, {"exists": False})
    else:
        apply_snapshot(dst, src_snap)
        apply_snapshot(src, dst_snap)

    db.session.commit()
    socketio.emit('update_table', namespace='/')
    return jsonify({"ok": True})


# ---------- MAP ----------
@app.get("/map")
@login_required
def map_page():
    d = parse_date(request.args.get("date", "")) or date.today()
    start = week_start(d)
    return render_template("map.html", selected_week=iso(start))


@app.get("/api/map_markers")
def api_map_markers():
    d = parse_date(request.args.get("date", "")) or date.today()
    start = week_start(d)
    days = [start + timedelta(days=i) for i in range(7)]

    cells = PlanCell.query.filter(PlanCell.work_date >= days[0], PlanCell.work_date <= days[-1]).all()
    active_project_ids = {c.project_id for c in cells if len(c.assignments) > 0}

    by_city = {}
    for p in Project.query.order_by(Project.region.asc(), Project.project_code.asc()).all():
        city = (p.region or "").strip()
        if not city:
            continue
        key = city.lower()
        if key not in by_city:
            lat, lon = geocode_city(city)
            by_city[key] = {"city": city, "lat": lat, "lon": lon, "active": False, "projects": []}
        if p.id in active_project_ids:
            by_city[key]["active"] = True
        by_city[key]["projects"].append({"code": p.project_code, "name": p.project_name, "responsible": p.responsible})

    return jsonify({"week_start": iso(start), "markers": list(by_city.values())})


@app.get("/api/routes_all")
def api_routes_all():
    ws = parse_date(request.args.get("week_start", "")) or week_start(date.today())
    start = ws
    end = ws + timedelta(days=6)

    # team_id'leri bul
    team_ids = (
        db.session.query(PlanCell.team_id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        .filter(PlanCell.team_id.isnot(None))
        .distinct()
        .all()
    )
    team_ids = [t[0] for t in team_ids if t[0]]
    if not team_ids:
        return jsonify({"ok": True, "routes": []})

    # her ekip için sıralı şehir listesi
    routes = []
    for tid in sorted(team_ids):
        rows = (
            db.session.query(PlanCell.work_date, Project.region, Project.project_code)
            .join(Project, Project.id == PlanCell.project_id)
            .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
            .filter(PlanCell.team_id == tid)
            .order_by(PlanCell.work_date.asc(), db.case((PlanCell.shift == "Gündüz", 1),
                                                       (PlanCell.shift == "Gündüz Yol", 2),
                                                       (PlanCell.shift == "Gece", 3),
                                                       else_=9).asc(),
                      Project.project_code.asc())
            .all()
        )

        seen = set()
        pts = []
        for wd, city, pcode in rows:
            city = (city or "").strip()
            if not city:
                continue
            key = (wd, city.lower())
            if key in seen:
                continue
            seen.add(key)
            lat, lon = geocode_city(city)
            if lat is None or lon is None:
                continue
            pts.append({"date": iso(wd), "city": city, "project_code": pcode, "lat": lat, "lon": lon})

        routes.append({
            "team_id": tid,
            "team_name": Team.query.get(tid).name if Team.query.get(tid) else f"Ekip #{tid}",
            "color": team_color(tid),
            "points": pts
        })

    return jsonify({"ok": True, "week_start": iso(ws), "routes": routes})


@app.get("/api/route")
def api_route_alias():
    # Backward compatible: single team route
    ws = parse_date(request.args.get("week_start", "")) or week_start(date.today())
    team_id = int(request.args.get("team_id", 0) or 0)
    if not team_id:
        return jsonify({"ok": False, "error": "team_id eksik"}), 400
    # reuse routes_team logic
    with app.test_request_context():
        pass
    # call same code as api_routes_team
    start = ws
    end = ws + timedelta(days=6)
    rows = (
        db.session.query(PlanCell.work_date, Project.region, Project.project_code)
        .join(Project, Project.id == PlanCell.project_id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        .filter(PlanCell.team_id == team_id)
        .order_by(PlanCell.work_date.asc(),
                  db.case((PlanCell.shift == "Gündüz", 1),
                          (PlanCell.shift == "Gündüz Yol", 2),
                          (PlanCell.shift == "Gece", 3),
                          else_=9).asc(),
                  Project.project_code.asc())
        .all()
    )
    seen = set()
    pts = []
    for wd, city, pcode in rows:
        city = (city or "").strip()
        if not city:
            continue
        key = (wd, city.lower())
        if key in seen:
            continue
        seen.add(key)
        lat, lon = geocode_city(city)
        if lat is None or lon is None:
            continue
        pts.append({"date": iso(wd), "city": city, "project_code": pcode, "lat": lat, "lon": lon})
    t = Team.query.get(team_id)
    return jsonify({
        "ok": True,
        "week_start": iso(ws),
        "team_id": team_id,
        "team_name": (t.name if t else f"Ekip #{team_id}"),
        "color": team_color(team_id),
        "points": pts
    })

@app.get("/api/routes_team")
def api_routes_team():
    ws = parse_date(request.args.get("week_start", "")) or week_start(date.today())
    team_id = int(request.args.get("team_id", 0) or 0)
    start = ws
    end = ws + timedelta(days=6)

    if not team_id:
        return jsonify({"ok": False, "error": "team_id eksik"}), 400

    rows = (
        db.session.query(PlanCell.work_date, Project.region, Project.project_code)
        .join(Project, Project.id == PlanCell.project_id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        .filter(PlanCell.team_id == team_id)
        .order_by(PlanCell.work_date.asc(),
                  db.case((PlanCell.shift == "Gündüz", 1),
                          (PlanCell.shift == "Gündüz Yol", 2),
                          (PlanCell.shift == "Gece", 3),
                          else_=9).asc(),
                  Project.project_code.asc())
        .all()
    )

    seen = set()
    pts = []
    for wd, city, pcode in rows:
        city = (city or "").strip()
        if not city:
            continue
        key = (wd, city.lower())
        if key in seen:
            continue
        seen.add(key)
        lat, lon = geocode_city(city)
        if lat is None or lon is None:
            continue
        pts.append({"date": iso(wd), "city": city, "project_code": pcode, "lat": lat, "lon": lon})

    return jsonify({
        "ok": True,
        "week_start": iso(ws),
        "route": {
            "team_id": team_id,
            "team_name": Team.query.get(team_id).name if Team.query.get(team_id) else f"Ekip #{team_id}",
            "color": team_color(team_id),
            "points": pts
        }
    })


# ---------- REPORTS ----------
@app.get("/reports")
@login_required
def reports_page():
    ensure_schema()  # ensure DB columns exist before report queries
    d = parse_date(request.args.get("date", "")) or date.today()
    ws = week_start(d)
    start = ws
    end = ws + timedelta(days=6)

    short_rows = (
        db.session.query(
            PlanCell.work_date,
            Project.region,
            Project.project_code,
            Person.full_name,
            Person.tc_no,
            Person.phone,
            PlanCell.shift,
            PlanCell.vehicle_info
        )
        .join(CellAssignment, CellAssignment.cell_id == PlanCell.id)
        .join(Person, Person.id == CellAssignment.person_id)
        .join(Project, Project.id == PlanCell.project_id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        .order_by(PlanCell.work_date.asc(), Project.region.asc(), Person.full_name.asc())
        .all()
    )

    detailed_rows = (
        db.session.query(
            PlanCell.work_date,
            Project.region,
            Project.project_code,
            Project.project_name,
            PlanCell.shift,
            PlanCell.vehicle_info,
            PlanCell.note,
            Person.full_name,
            Person.tc_no,
            Person.phone,
            Team.name
        )
        .join(CellAssignment, CellAssignment.cell_id == PlanCell.id)
        .join(Person, Person.id == CellAssignment.person_id)
        .join(Project, Project.id == PlanCell.project_id)
        .outerjoin(Team, Team.id == PlanCell.team_id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        .order_by(PlanCell.work_date.asc(), Project.region.asc(), Project.project_code.asc(), Person.full_name.asc())
        .all()
    )

    return render_template(
        "reports.html",
        selected_week=iso(ws),
        prev_week=iso(ws - timedelta(days=7)),
        next_week=iso(ws + timedelta(days=7)),
        short_rows=short_rows,
        detailed_rows=detailed_rows
    )


@app.get("/mail")
@login_required
def mail_page():
    d = parse_date(request.args.get("date", "")) or date.today()
    ws = week_start(d)
    start = ws
    end = ws + timedelta(days=6)

    team_names = [
        r[0] for r in db.session.query(Team.name).join(PlanCell, PlanCell.team_id == Team.id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end, Team.name != None).distinct().all()
    ]
    extra = [
        r[0] for r in db.session.query(PlanCell.team_name).filter(
            PlanCell.work_date >= start, PlanCell.work_date <= end,
            PlanCell.team_name != None, PlanCell.team_name != ""
        ).distinct().all()
    ]
    for t in extra:
        if t not in team_names:
            team_names.append(t)

    return render_template(
        "mail.html",
        selected_week=iso(ws),
        prev_week=iso(ws - timedelta(days=7)),
        next_week=iso(ws + timedelta(days=7)),
        team_names=team_names
    )


@app.post("/api/send_weekly_emails")
@login_required
@observer_required
def api_send_weekly_emails():
    data = request.get_json(force=True, silent=True) or {}
    ws = parse_date(data.get("week_start", "")) or week_start(date.today())
    start = ws
    end = ws + timedelta(days=6)

    people = Person.query.order_by(Person.full_name.asc()).all()
    tasks: Dict[int, List[dict]] = {p.id: [] for p in people}

    rows = (
        db.session.query(
            Person.id, Person.full_name, Person.email,
            PlanCell.work_date,
            Project.region, Project.project_code, Project.project_name,
            PlanCell.shift, PlanCell.note, PlanCell.vehicle_info,
            PlanCell.job_mail_body, PlanCell.lld_hhd_files, PlanCell.tutanak_files, PlanCell.lld_hhd_path, PlanCell.tutanak_path,
            Team.name, PlanCell.team_name
        )
        .join(CellAssignment, CellAssignment.person_id == Person.id)
        .join(PlanCell, PlanCell.id == CellAssignment.cell_id)
        .join(Project, Project.id == PlanCell.project_id)
        .outerjoin(Team, Team.id == PlanCell.team_id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        .order_by(Person.full_name.asc(), PlanCell.work_date.asc())
        .all()
    )

    for pid, pname, pemail, wd, region, pcode, pname2, shift, note, vehicle, job_mail_body, lld_list_str, tut_list_str, lld_single, tut_single, tname in rows:
        lld_list = _parse_files(lld_list_str)
        tut_list = _parse_files(tut_list_str)
        if lld_single and not lld_list:
            lld_list = [lld_single]
        if tut_single and not tut_list:
            tut_list = [tut_single]
        tasks[pid].append({
            "date": iso(wd),
            "where": region,
            "project": f"{pcode} - {pname2}",
            "shift": shift or "",
            "note": note or "",
            "vehicle": vehicle or "",
            "team": tname or "",
            "job_mail_body": job_mail_body or "",
            "lld_hhd_files": lld_list,
            "tutanak_files": tut_list,
        })

    sent = 0
    skipped = 0
    errors = []

    for p in people:
        if not p.email:
            skipped += 1
            continue
        items = tasks.get(p.id, [])
        if not items:
            skipped += 1
            continue

        rows_html = ""
        attachments_paths = set()
        for it in items:
            for f in it.get("lld_hhd_files") or []:
                attachments_paths.add(f)
            for f in it.get("tutanak_files") or []:
                attachments_paths.add(f)

            job_mail_html = html.escape(it.get("job_mail_body") or "").replace("\n", "<br>")
            note_html = html.escape(it.get("note") or "").replace("\n", "<br>")
            where_html = html.escape(it.get("where") or "")
            project_html = html.escape(it.get("project") or "")
            shift_html = html.escape(it.get("shift") or "")
            vehicle_html = html.escape(it.get("vehicle") or "")
            team_html = html.escape(it.get("team") or "")
            lld_names = ", ".join([os.path.basename(x) for x in (it.get("lld_hhd_files") or [])])
            tutanak_names = ", ".join([os.path.basename(x) for x in (it.get("tutanak_files") or [])])
            rows_html += f"""
              <tr>
                <td>{it['date']}</td>
                <td>{where_html}</td>
                <td>{project_html}</td>
                <td>{shift_html}</td>
                <td>{vehicle_html}</td>
                <td>{team_html}</td>
                <td>{job_mail_html}</td>
                <td>{note_html}</td>
                <td>{lld_names}</td>
                <td>{tutanak_names}</td>
              </tr>
            """

        html = f"""
        <div style="font-family:Arial">
          <h3>Haftalık İş Planı (Hafta başlangıç: {iso(ws)})</h3>
          <p>Merhaba {p.full_name}, aşağıda bu haftaki planın yer alıyor.</p>
          <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
            <thead>
              <tr>
                <th>Tarih</th><th>İl</th><th>Proje</th><th>Vardiya</th><th>Araç</th><th>Ekip</th><th>İş Detay Maili</th><th>İş Detayı</th><th>LLD/HHD</th><th>Tutanak</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
        """

        attachments_payload = []
        for fname in attachments_paths:
            full_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
            if not fname or not os.path.exists(full_path):
                continue
            with open(full_path, "rb") as f:
                data = f.read()
            ctype = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
            attachments_payload.append({
                "filename": os.path.basename(full_path),
                "data": data,
                "content_type": ctype
            })

        try:
            send_email_smtp(p.email, f"Haftalık Plan - {iso(ws)}", html, attachments=attachments_payload)
            sent += 1
        except Exception as e:
            errors.append(f"{p.full_name}: {str(e)}")

    return jsonify({"ok": True, "sent": sent, "skipped": skipped, "errors": errors})


@app.post("/api/send_team_emails")
@login_required
@observer_required
def api_send_team_emails():
    data = request.get_json(force=True, silent=True) or {}
    ws = parse_date(data.get("week_start", "")) or week_start(date.today())
    start = ws
    end = ws + timedelta(days=6)
    team_name = (data.get("team_name") or "").strip()
    if not team_name:
        return jsonify({"ok": False, "error": "Ekip adı gerekli"}), 400

    people = Person.query.order_by(Person.full_name.asc()).all()
    tasks: Dict[int, List[dict]] = {p.id: [] for p in people}

    rows = (
        db.session.query(
            Person.id, Person.full_name, Person.email,
            PlanCell.work_date,
            Project.region, Project.project_code, Project.project_name,
            PlanCell.shift, PlanCell.note, PlanCell.vehicle_info,
            PlanCell.job_mail_body, PlanCell.lld_hhd_files, PlanCell.tutanak_files, PlanCell.lld_hhd_path, PlanCell.tutanak_path,
            Team.name
        )
        .join(CellAssignment, CellAssignment.person_id == Person.id)
        .join(PlanCell, PlanCell.id == CellAssignment.cell_id)
        .join(Project, Project.id == PlanCell.project_id)
        .outerjoin(Team, Team.id == PlanCell.team_id)
        .filter(PlanCell.work_date >= start, PlanCell.work_date <= end)
        .order_by(Person.full_name.asc(), PlanCell.work_date.asc())
        .all()
    )

    for pid, pname, pemail, wd, region, pcode, pname2, shift, note, vehicle, job_mail_body, lld_list_str, tut_list_str, lld_single, tut_single, tname, tname_alt in rows:
        effective_team = tname or tname_alt or ""
        if effective_team != team_name:
            continue

        lld_list = _parse_files(lld_list_str)
        tut_list = _parse_files(tut_list_str)
        if lld_single and not lld_list:
            lld_list = [lld_single]
        if tut_single and not tut_list:
            tut_list = [tut_single]

        tasks[pid].append({
            "date": iso(wd),
            "where": region,
            "project": f"{pcode} - {pname2}",
            "shift": shift or "",
            "note": note or "",
            "vehicle": vehicle or "",
            "team": tname or "",
            "job_mail_body": job_mail_body or "",
            "lld_hhd_files": lld_list,
            "tutanak_files": tut_list,
        })

    sent = 0
    skipped = 0
    errors = []

    for p in people:
        items = tasks.get(p.id, [])
        if not items:
            continue
        if not p.email:
            skipped += 1
            continue

        rows_html = ""
        attachments_paths = set()
        for it in items:
            for f in it.get("lld_hhd_files") or []:
                attachments_paths.add(f)
            for f in it.get("tutanak_files") or []:
                attachments_paths.add(f)

            job_mail_html = html.escape(it.get("job_mail_body") or "").replace("\n", "<br>")
            note_html = html.escape(it.get("note") or "").replace("\n", "<br>")
            where_html = html.escape(it.get("where") or "")
            project_html = html.escape(it.get("project") or "")
            shift_html = html.escape(it.get("shift") or "")
            vehicle_html = html.escape(it.get("vehicle") or "")
            team_html = html.escape(it.get("team") or "")
            lld_names = ", ".join([os.path.basename(x) for x in (it.get("lld_hhd_files") or [])])
            tutanak_names = ", ".join([os.path.basename(x) for x in (it.get("tutanak_files") or [])])
            rows_html += f"""
              <tr>
                <td>{it['date']}</td>
                <td>{where_html}</td>
                <td>{project_html}</td>
                <td>{shift_html}</td>
                <td>{vehicle_html}</td>
                <td>{team_html}</td>
                <td>{job_mail_html}</td>
                <td>{note_html}</td>
                <td>{lld_names}</td>
                <td>{tutanak_names}</td>
              </tr>
            """

        html_body = f"""
        <div style="font-family:Arial">
          <h3>Ekip: {html.escape(team_name)} (Hafta başlangıç: {iso(ws)})</h3>
          <p>Merhaba {html.escape(p.full_name or '')}, bu ekip için planın:</p>
          <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
            <thead>
              <tr>
                <th>Tarih</th><th>İl</th><th>Proje</th><th>Vardiya</th><th>Araç</th><th>Ekip</th><th>İş Detay Maili</th><th>İş Detayı</th><th>LLD/HHD</th><th>Tutanak</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
        """

        attachments_payload = []
        for fname in attachments_paths:
            full_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
            if not fname or not os.path.exists(full_path):
                continue
            with open(full_path, "rb") as f:
                data_blob = f.read()
            ctype = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
            attachments_payload.append({
                "filename": os.path.basename(full_path),
                "data": data_blob,
                "content_type": ctype
            })

        try:
            send_email_smtp(p.email, f"Ekip Planı ({team_name}) - {iso(ws)}", html_body, attachments=attachments_payload)
            sent += 1
        except Exception as e:
            errors.append(f"{p.full_name}: {str(e)}")

    return jsonify({"ok": True, "sent": sent, "skipped": skipped, "errors": errors})


# ---------- TIMESHEET EXCEL ----------
@app.get("/timesheet.xlsx")
@login_required
def timesheet_excel():
    ws = parse_date(request.args.get("week_start", "")) or week_start(date.today())
    start = ws
    days = [start + timedelta(days=i) for i in range(7)]

    people = Person.query.order_by(Person.full_name.asc()).all()

    # tüm assignmentları çek
    rows = (
        db.session.query(
            Person.id, Person.full_name,
            PlanCell.work_date,
            Project.region, Project.project_code, Project.project_name,
            PlanCell.shift, PlanCell.note
        )
        .join(CellAssignment, CellAssignment.person_id == Person.id)
        .join(PlanCell, PlanCell.id == CellAssignment.cell_id)
        .join(Project, Project.id == PlanCell.project_id)
        .filter(PlanCell.work_date >= days[0], PlanCell.work_date <= days[-1])
        .all()
    )

    # (person_id, date_iso) -> list of tasks (bir günde birden fazla olabilir)
    mp: Dict[Tuple[int, str], List[str]] = {}
    for pid, name, wd, city, pcode, pname, shift, note in rows:
        key = (pid, iso(wd))
        txt = f"{city} | {pcode} | {shift or ''} | {note or ''}".strip()
        mp.setdefault(key, []).append(txt)

    # statusları çek
    st = get_person_status_map(days)

    wb = Workbook()
    wsht = wb.active
    wsht.title = "Timesheet"

    header = ["Ad Soyad"]
    for i, dday in enumerate(days):
        header.append(f"{dday.strftime('%Y-%m-%d')} ({TR_DAYS[i]})")

    wsht.append(header)

    # header style
    for c in range(1, len(header)+1):
        cell = wsht.cell(row=1, column=c)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # rows
    r = 2
    for p in people:
        row = [p.full_name]
        for dday in days:
            k = iso(dday)
            items = mp.get((p.id, k), [])
            if items:
                row.append("\n---\n".join(items))
            else:
                # görev yoksa status göster
                stv = st.get((p.id, k), "available")
                if stv == "leave":
                    row.append("İZİNLİ")
                elif stv == "production":
                    row.append("ÜRETİMDE")
                else:
                    row.append("")
        wsht.append(row)
        r += 1

    # column widths + wrap
    wsht.column_dimensions["A"].width = 28
    for i in range(2, len(header)+1):
        wsht.column_dimensions[get_column_letter(i)].width = 34

    for rr in range(2, wsht.max_row+1):
        for cc in range(1, wsht.max_column+1):
            wsht.cell(row=rr, column=cc).alignment = Alignment(vertical="top", wrap_text=True)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"timesheet_{iso(ws)}.xlsx"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_schema()  # Ensure all columns exist - MUST be called first
        try:
            init_users()  # Initialize default users
        except Exception as e:
            print(f"[init_users] Error (will retry on first request): {e}")
        try:
            init_default_data()  # Initialize default firmalar and seviyeler
        except Exception as e:
            print(f"[init_default_data] Error (will retry on first request): {e}")
        socketio.run(app, debug=True)
