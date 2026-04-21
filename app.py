import os
import io
import hashlib
import smtplib
import mimetypes
import html
import logging
import re
import shutil
from logging.handlers import RotatingFileHandler
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Tuple, List, Any

import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, send_from_directory, session, abort
from flask import g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, join_room, leave_room
from sqlalchemy import event, inspect
from sqlite3 import Connection as SQLite3Connection
from werkzeug.utils import secure_filename

# Excel
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.styles.colors import Color

app = Flask(__name__)
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    _app_env = (os.getenv("FLASK_ENV") or os.getenv("ENV") or "").strip().lower()
    if _app_env in {"production", "prod"}:
        raise RuntimeError("SECRET_KEY must be set in production environment")
    _secret_key = "dev-secret"
app.secret_key = _secret_key
# Beni Hatırla: oturum 31 gün saklansın (sadece session.permanent=True iken geçerli)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=31)

# Varsayılan veritabanı: instance/planner.db (proje kökündeki planner.db 0 byte olunca "file is not a database" hatası önlenir)
_default_db_path = os.path.join(app.instance_path, "planner.db").replace("\\", "/")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DB_URL", f"sqlite:///{_default_db_path}")
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {
            "timeout": int(os.getenv("SQLITE_BUSY_TIMEOUT", "30") or 30),
            "check_same_thread": False,
        },
        "pool_pre_ping": True,
    }
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
try:
    max_upload_mb = int(os.getenv("MAX_CONTENT_LENGTH_MB", "100") or 100)
except Exception:
    max_upload_mb = 100
app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024
uploads_public_env = str(os.getenv("UPLOADS_PUBLIC", "0") or "").strip().lower()
app.config["UPLOADS_PUBLIC"] = uploads_public_env in ("1", "true", "yes", "on")
try:
    app.config["FEEDBACK_MAX_MB"] = int(os.getenv("FEEDBACK_MAX_MB", "50") or 50)
except Exception:
    app.config["FEEDBACK_MAX_MB"] = 50
app.config["FEEDBACK_MAX_BYTES"] = int(app.config["FEEDBACK_MAX_MB"]) * 1024 * 1024
from extensions import db, socketio
from models import User, Firma, Seviye, Person, Project, SubProject, ProjectComment, Team, TeamMailConfig, PlanCell, CellAssignment, PersonDayStatus, PersonnelStatusType, MailLog, Notification, Announcement, AnnouncementRead, ChatMessage, ChatUserMessage, Job, JobAssignment, JobFeedback, JobFeedbackMedia, JobReport, JobStatusHistory, Vehicle, VehicleAssignment, CellLock, CellCancellation, CellVersion, TeamOvertime, VoiceMessage, UserSettings, TableSnapshot


from utils import *
from utils import _touch_last_seen_before_request, _field_portal_guard, _rbac_guard_admin_api_paths, _csrf_protect_unsafe_methods, _csrf_token
# Explicit imports for linter
try:
    from utils import _sqlite_db_path, _create_sqlite_backup_file, _touch_user_activity, _can_access_chat_team, _publish_cell
except ImportError:
    pass

# Placeholder for _check_sla_notifications if not defined in utils
def _check_sla_notifications():
    """Placeholder for SLA notifications check"""
    pass
from routes.auth import auth_bp, init_users
from routes.api import api_bp
from routes.chat import chat_bp
from routes.admin import admin_bp
from routes.planner import planner_bp
from routes.analytics_routes import register_analytics_routes
from routes.realtime import realtime_bp
from routes.tasks import tasks_bp
from routes.arvento import arvento_bp
from routes.vehicle_routes import vehicle_bp
from routes.admin_mail_queue import admin_mq_bp
register_analytics_routes(planner_bp)

app.register_blueprint(auth_bp)
app.register_blueprint(api_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(planner_bp)
app.register_blueprint(realtime_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(arvento_bp)
app.register_blueprint(vehicle_bp)
app.register_blueprint(admin_mq_bp)
app.jinja_env.globals["csrf_token"] = _csrf_token

# Popup announcement (explicit import for type checker)
from utils import _fetch_popup_announcement

@app.context_processor
def _inject_popup_announcement():
    try:
        user = get_current_user()
        if not user:
            return {}
        popup = _fetch_popup_announcement(user)
        if not popup:
            return {}
        return {"popup_announcement": popup}
    except Exception:
        return {}

db.init_app(app)

def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.close()

with app.app_context():
    event.listen(db.engine, "connect", _set_sqlite_pragmas)

# Register global hooks from utils
app.before_request(_touch_last_seen_before_request)
app.before_request(_field_portal_guard)
app.before_request(_rbac_guard_admin_api_paths)
app.before_request(_csrf_protect_unsafe_methods)

# Python 3.13+ doesn't support eventlet well, use threading for development
# Production uses gunicorn + eventlet, so this only affects direct python app.py runs
import sys
_socketio_async_mode = os.getenv("SOCKETIO_ASYNC_MODE")
if not _socketio_async_mode:
    if sys.version_info >= (3, 13):
        _socketio_async_mode = "threading"
    else:
        _socketio_async_mode = "eventlet"

cors_env = str(os.getenv("SOCKETIO_CORS_ORIGINS", "") or "").strip()
if cors_env:
    cors_allowed_origins = [c.strip() for c in cors_env.split(",") if c.strip()]
else:
    public_base = str(os.getenv("PUBLIC_BASE_URL", "") or "").strip()
    cors_allowed_origins = [public_base] if public_base else "*"

socketio.init_app(
    app,
    async_mode=_socketio_async_mode,
    cors_allowed_origins=cors_allowed_origins,
    ping_interval=25,
    ping_timeout=60,
)

# Ensure upload dir exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ---------- LOGGING ----------
# ---------- LOGGING ----------
def _init_logging():
    try:
        log_dir = os.path.join(app.instance_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "app.log")
        
        # File Handler
        file_handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
        
        # Stream Handler (Console)
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
        
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if not any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == file_handler.baseFilename for h in root.handlers):
            root.addHandler(file_handler)
        
        if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
            root.addHandler(stream_handler)
            
    except Exception as e:
        print(f"Logging init failed: {e}")

_init_logging()
log = logging.getLogger("planner")

# ---------- HAFTALIK ARAÇ ATAMA ARŞİVLEME ----------
def _archive_expired_vehicle_assignments():
    """
    Geçmiş haftaların araç atamalarını arşivler (is_active=False).
    Uygulama her başlatıldığında çalışır.
    """
    try:
        from datetime import date, timedelta
        from models import VehicleAssignment
        if not inspect(db.engine).has_table("vehicle_assignment"):
            log.info("Arac atama arsivleme atlandi: vehicle_assignment tablosu yok.")
            return
        
        today = date.today()
        # Bu haftanın pazartesi'si
        current_week_start = today - timedelta(days=today.weekday())
        
        # Geçmiş hafta atamalarını pasif yap
        expired = VehicleAssignment.query.filter(
            VehicleAssignment.week_end < today,
            VehicleAssignment.is_active == True
        ).all()
        
        if expired:
            for assignment in expired:
                assignment.is_active = False
            db.session.commit()
            log.info(f"Araç ataması arşivlendi: {len(expired)} adet geçmiş atama pasif yapıldı")
    except Exception as e:
        log.error(f"Araç atama arşivleme hatası: {e}")

# Uygulama başlatılırken arşivleme yap
with app.app_context():
    _archive_expired_vehicle_assignments()

# Register webm MIME type for audio playback
mimetypes.add_type('audio/webm', '.webm')

# Uploads route - serve uploaded files (voice messages, attachments, etc.)
@app.route('/uploads/<path:filepath>')
def serve_uploads(filepath):
    if not app.config.get("UPLOADS_PUBLIC"):
        user = get_current_user()
        if not user:
            return abort(403)
    uploads_dir = os.path.join(app.instance_path, 'uploads')
    # Manually determine mimetype for webm files
    mimetype = None
    if filepath.endswith('.webm'):
        mimetype = 'audio/webm'
    return send_from_directory(uploads_dir, filepath, mimetype=mimetype)


# Favicon route - returns a simple SVG favicon to prevent 404 errors
@app.route('/favicon.ico')
def favicon():
    # Return existing favicon if available, otherwise generate a simple one
    favicon_path = os.path.join(app.static_folder, 'favicon.ico')
    if os.path.exists(favicon_path):
        return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/x-icon')
    
    # Fallback: Return a simple SVG as favicon
    svg_favicon = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
        <rect width="32" height="32" rx="6" fill="#3b82f6"/>
        <text x="16" y="22" font-size="18" font-family="Arial" fill="white" text-anchor="middle" font-weight="bold">S</text>
    </svg>'''
    from flask import Response
    return Response(svg_favicon, mimetype='image/svg+xml')


@app.get("/health")
def health():
    return jsonify({"ok": True, "status": "healthy"})


@app.before_request
def _request_context():
    try:
        g.request_id = _secrets.token_hex(8)
        g.started_at = _time.time()
    except Exception:
        pass

@app.after_request
def _log_request(response):
    try:
        dur_ms = None
        try:
            dur_ms = int((_time.time() - float(getattr(g, "started_at", _time.time()))) * 1000)
        except Exception:
            dur_ms = None
        payload = {
            "event": "http_request",
            "request_id": getattr(g, "request_id", None),
            "method": request.method,
            "path": request.path,
            "status": int(getattr(response, "status_code", 0) or 0),
            "duration_ms": dur_ms,
            "user_id": session.get("user_id"),
        }
        log.info(_json_dumps(payload))
    except Exception:
        pass
    return response

def _json_dumps(obj) -> str:
    import json as _json
    try:
        return _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        try:
            return str(obj)
        except Exception:
            return ""


# --- AUTO MIGRATION (SQLite) ---
# Robust migration: derive the *exact* sqlite file path from SQLAlchemy engine URL,
# then use sqlite3 directly to ALTER TABLE if needed. This avoids "wrong file" issues.

import sqlite3
from sqlalchemy import text as _sql_text, or_, cast
from jinja2 import Environment, BaseLoader, StrictUndefined, select_autoescape
import secrets as _secrets
import time as _time
import threading as _threading2



def _column_exists_sqlite(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols

def ensure_schema():
    '''Ensure missing columns are added (idempotent).'''
    try:
        # Ensure all tables exist first
        db.create_all()

        # SubProject: older DBs may have an incorrect UNIQUE constraint on (project_id) which
        # prevents adding multiple subprojects under the same project. If detected, rebuild
        # the table without that constraint.
        try:
            idx_rows = db.session.execute(_sql_text("PRAGMA index_list(sub_project)")).fetchall() or []
            unique_project_id_only = False
            for r in idx_rows:
                # PRAGMA index_list: seq, name, unique, origin, partial
                try:
                    idx_name = r[1]
                    is_unique = int(r[2] or 0) == 1
                except Exception:
                    continue
                if not is_unique or not idx_name:
                    continue
                try:
                    cols = db.session.execute(_sql_text(f"PRAGMA index_info({idx_name})")).fetchall() or []
                    col_names = [c[2] for c in cols if c and len(c) >= 3]
                except Exception:
                    col_names = []
                if [c for c in col_names if c] == ["project_id"]:
                    unique_project_id_only = True
                    break

            if unique_project_id_only:
                # Rebuild table to drop the bad UNIQUE(project_id) constraint.
                # Keep existing data (best-effort).
                old_cols = db.session.execute(_sql_text("PRAGMA table_info(sub_project)")).fetchall() or []
                old_col_names = {c[1] for c in old_cols if c and len(c) >= 2}

                def _col(expr: str, col: str) -> str:
                    return expr if col in old_col_names else "NULL"

                select_sql = ", ".join([
                    _col("id", "id"),
                    _col("project_id", "project_id"),
                    _col("name", "name"),
                    _col("code", "code"),
                    (_col("COALESCE(is_active, 1)", "is_active") if "is_active" in old_col_names else "1"),
                    (_col("COALESCE(created_at, CURRENT_TIMESTAMP)", "created_at") if "created_at" in old_col_names else "CURRENT_TIMESTAMP"),
                ])

                db.session.execute(_sql_text("ALTER TABLE sub_project RENAME TO sub_project__old"))
                db.session.execute(_sql_text("""
                    CREATE TABLE sub_project (
                        id INTEGER PRIMARY KEY,
                        project_id INTEGER NOT NULL,
                        name VARCHAR(180) NOT NULL,
                        code VARCHAR(80),
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL
                    )
                """))
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_sub_project_project_id ON sub_project (project_id)"))
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_sub_project_is_active ON sub_project (is_active)"))
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_sub_project_created_at ON sub_project (created_at)"))
                db.session.execute(_sql_text("CREATE UNIQUE INDEX IF NOT EXISTS uq_subproject_project_code ON sub_project (project_id, code)"))
                db.session.execute(_sql_text(f"""
                    INSERT INTO sub_project (id, project_id, name, code, is_active, created_at)
                    SELECT {select_sql} FROM sub_project__old
                """))
                db.session.execute(_sql_text("DROP TABLE sub_project__old"))
                db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        
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

        # plan_cell photos + QC
        if "photo_files" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN photo_files TEXT"))
            db.session.commit()
            cols.append("photo_files")
        if "qc_result" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN qc_result TEXT"))
            db.session.commit()
            cols.append("qc_result")

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

        # plan_cell.assigned_user_id (field portal assignment)
        if "assigned_user_id" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN assigned_user_id INTEGER"))
            db.session.commit()
            cols.append("assigned_user_id")

        # plan_cell.subproject_id (optional)
        if "subproject_id" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN subproject_id INTEGER"))
            db.session.commit()
            cols.append("subproject_id")
            try:
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_plan_cell_subproject_id ON plan_cell (subproject_id)"))
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass

        # plan_cell: Realtime features - status, cancelled_at, cancelled_by_user_id, cancellation_reason, version
        if "status" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"))
            db.session.commit()
            cols.append("status")
            try:
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_plan_cell_status ON plan_cell (status)"))
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        if "cancelled_at" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN cancelled_at DATETIME"))
            db.session.commit()
            cols.append("cancelled_at")
        if "cancelled_by_user_id" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN cancelled_by_user_id INTEGER"))
            db.session.commit()
            cols.append("cancelled_by_user_id")
            try:
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_plan_cell_cancelled_by ON plan_cell (cancelled_by_user_id)"))
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        if "cancellation_reason" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN cancellation_reason TEXT"))
            db.session.commit()
            cols.append("cancellation_reason")
        if "version" not in cols:
            db.session.execute(_sql_text("ALTER TABLE plan_cell ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))
            db.session.commit()
            cols.append("version")


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
            # project.notification_enabled
            if "notification_enabled" not in pcols:
                db.session.execute(_sql_text("ALTER TABLE project ADD COLUMN notification_enabled INTEGER NOT NULL DEFAULT 1"))
                db.session.commit()
            # project initiation file fields
            if "initiation_file_path" not in pcols:
                db.session.execute(_sql_text("ALTER TABLE project ADD COLUMN initiation_file_path TEXT"))
                db.session.commit()
            if "initiation_file_type" not in pcols:
                db.session.execute(_sql_text("ALTER TABLE project ADD COLUMN initiation_file_type TEXT"))
                db.session.commit()
            if "initiation_file_name" not in pcols:
                db.session.execute(_sql_text("ALTER TABLE project ADD COLUMN initiation_file_name TEXT"))
                db.session.commit()
            if "no_initiation_file" not in pcols:
                db.session.execute(_sql_text("ALTER TABLE project ADD COLUMN no_initiation_file INTEGER NOT NULL DEFAULT 0"))
                db.session.commit()
            if "no_file_reason" not in pcols:
                db.session.execute(_sql_text("ALTER TABLE project ADD COLUMN no_file_reason TEXT"))
                db.session.commit()
        
        # person.firma_id, seviye_id, durum
        pcols = [r[1] for r in db.session.execute(_sql_text("PRAGMA table_info(person)")).fetchall()]
        if "firma_id" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN firma_id INTEGER"))
            db.session.commit()
        if "seviye_id" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN seviye_id INTEGER"))
            db.session.commit()
        if "user_id" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN user_id INTEGER"))
            db.session.commit()
            try:
                db.session.execute(_sql_text("CREATE UNIQUE INDEX IF NOT EXISTS ux_person_user_id ON person (user_id) WHERE user_id IS NOT NULL"))
                db.session.commit()
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        if "durum" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN durum TEXT NOT NULL DEFAULT 'Aktif'"))
            db.session.commit()
        if "karsi_firma_sorumlusu" not in pcols:
            db.session.execute(_sql_text("ALTER TABLE person ADD COLUMN karsi_firma_sorumlusu TEXT"))
            db.session.commit()
        
        # user.email, full_name, is_active, team_id
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
                if "team_id" not in ucols:
                    db.session.execute(_sql_text("ALTER TABLE user ADD COLUMN team_id INTEGER"))
                    db.session.commit()
                if "last_seen" not in ucols:
                    db.session.execute(_sql_text("ALTER TABLE user ADD COLUMN last_seen DATETIME"))
                    db.session.commit()
                if "online_since" not in ucols:
                    db.session.execute(_sql_text("ALTER TABLE user ADD COLUMN online_since DATETIME"))
                    db.session.commit()
                if "is_super_admin" not in ucols:
                    db.session.execute(_sql_text("ALTER TABLE user ADD COLUMN is_super_admin INTEGER NOT NULL DEFAULT 0"))
                    db.session.commit()
                    # Kıvanc'ı super admin yap, diğerlerini normal yap
                    db.session.execute(_sql_text("UPDATE user SET is_super_admin = 0 WHERE username != 'kivanc' AND email != 'kivancozcan@netmon.com.tr'"))
                    db.session.execute(_sql_text("UPDATE user SET is_super_admin = 1 WHERE username = 'kivanc' OR email = 'kivancozcan@netmon.com.tr'"))
                    db.session.commit()

                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_user_last_seen ON user (last_seen)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_user_online_since ON user (online_since)"))
                db.session.commit()
        except Exception:
            pass  # Table might not exist yet
        
        # firma.gender, email, mail_recipient_name
        try:
            frows = db.session.execute(_sql_text("PRAGMA table_info(firma)")).fetchall()
            if frows:
                fcols = [r[1] for r in frows]
                if "gender" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE firma ADD COLUMN gender TEXT"))
                    db.session.commit()
                if "email" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE firma ADD COLUMN email TEXT"))
                    db.session.commit()
                if "mail_recipient_name" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE firma ADD COLUMN mail_recipient_name TEXT"))
                    db.session.commit()
        except Exception:
            pass  # Table might not exist yet
        
        # job.kanban_status
        try:
            jrows = db.session.execute(_sql_text("PRAGMA table_info(job)")).fetchall()
            if jrows:
                jcols = [r[1] for r in jrows]
                if "kanban_status" not in jcols:
                    db.session.execute(_sql_text("ALTER TABLE job ADD COLUMN kanban_status TEXT NOT NULL DEFAULT 'PLANNED'"))
                    db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_kanban_status ON job (kanban_status)"))
                db.session.commit()
                if "assigned_user_id" not in jcols:
                    db.session.execute(_sql_text("ALTER TABLE job ADD COLUMN assigned_user_id INTEGER"))
                    db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_assigned_user_id ON job (assigned_user_id)"))
                db.session.commit()
                if "subproject_id" not in jcols:
                    db.session.execute(_sql_text("ALTER TABLE job ADD COLUMN subproject_id INTEGER"))
                    db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_subproject_id ON job (subproject_id)"))
                db.session.commit()
                if "team_id" not in jcols:
                    db.session.execute(_sql_text("ALTER TABLE job ADD COLUMN team_id INTEGER"))
                    db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_team_id ON job (team_id)"))
                db.session.commit()
                if "is_published" not in jcols:
                    db.session.execute(_sql_text("ALTER TABLE job ADD COLUMN is_published INTEGER NOT NULL DEFAULT 0"))
                    db.session.commit()
                if "published_at" not in jcols:
                    db.session.execute(_sql_text("ALTER TABLE job ADD COLUMN published_at DATETIME"))
                    db.session.commit()
                if "published_by_user_id" not in jcols:
                    db.session.execute(_sql_text("ALTER TABLE job ADD COLUMN published_by_user_id INTEGER"))
                    db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_is_published ON job (is_published)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_published_at ON job (published_at)"))
                db.session.commit()

                # Board performance indexes (idempotent)
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_work_date ON job (work_date)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_work_date_kanban ON job (work_date, kanban_status)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_project_work_date ON job (project_id, work_date)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_subproject_work_date ON job (subproject_id, work_date)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_assigned_work_date ON job (assigned_user_id, work_date)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_team_work_date ON job (team_id, work_date)"))
                db.session.commit()

                vrows = db.session.execute(_sql_text("PRAGMA table_info(vehicle)")).fetchall()
                if vrows:
                    vcols = [r[1] for r in vrows]
                    if "capacity" not in vcols:
                        db.session.execute(_sql_text("ALTER TABLE vehicle ADD COLUMN capacity INTEGER"))
                        db.session.commit()
                    if "vodafone_approval" not in vcols:
                        db.session.execute(_sql_text("ALTER TABLE vehicle ADD COLUMN vodafone_approval INTEGER NOT NULL DEFAULT 0"))
                        db.session.commit()

                trows = db.session.execute(_sql_text("PRAGMA table_info(team)")).fetchall()
                if trows:
                    tcols = [r[1] for r in trows]
                    if "vehicle_id" not in tcols:
                        db.session.execute(_sql_text("ALTER TABLE team ADD COLUMN vehicle_id INTEGER"))
                        db.session.commit()
                        try:
                            db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_team_vehicle_id ON team (vehicle_id)"))
                            db.session.commit()
                        except Exception:
                            try:
                                db.session.rollback()
                            except Exception:
                                pass
                    try:
                        db.session.execute(_sql_text("CREATE UNIQUE INDEX IF NOT EXISTS uq_team_vehicle_id ON team (vehicle_id) WHERE vehicle_id IS NOT NULL"))
                        db.session.commit()
                    except Exception:
                        try:
                            db.session.rollback()
                        except Exception:
                            pass

                # One-time migrate Turkish kanban values -> lifecycle values (idempotent)
                try:
                    db.session.execute(_sql_text("UPDATE job SET kanban_status='PLANNED' WHERE kanban_status IS NULL OR TRIM(kanban_status)='' OR kanban_status='PLANLANDI'"))
                    db.session.execute(_sql_text("UPDATE job SET kanban_status='ASSIGNED' WHERE kanban_status='ATANDI'"))
                    db.session.execute(_sql_text("UPDATE job SET kanban_status='PUBLISHED' WHERE kanban_status='SAHADA'"))
                    db.session.execute(_sql_text("UPDATE job SET kanban_status='REPORTED' WHERE kanban_status IN ('GERİ_BİLDİRİM','GERI_BILDIRIM','GERI_BİLDİRİM','KONTROLDE')"))
                    db.session.execute(_sql_text("UPDATE job SET kanban_status='CLOSED' WHERE kanban_status='KAPALI'"))
                    db.session.commit()
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
        except Exception:
            pass

        # job_status_history.note
        try:
            hrows = db.session.execute(_sql_text("PRAGMA table_info(job_status_history)")).fetchall()
            if hrows:
                hcols = [r[1] for r in hrows]
                if "note" not in hcols:
                    db.session.execute(_sql_text("ALTER TABLE job_status_history ADD COLUMN note TEXT"))
                    db.session.commit()
        except Exception:
            pass

        # job_feedback (field feedback submission columns)
        try:
            frows = db.session.execute(_sql_text("PRAGMA table_info(job_feedback)")).fetchall()
            if frows:
                fcols = [r[1] for r in frows]
                if "user_id" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN user_id INTEGER"))
                    db.session.commit()
                if "submitted_at" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN submitted_at DATETIME"))
                    db.session.commit()
                if "outcome" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN outcome TEXT"))
                    db.session.commit()
                if "isdp_status" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN isdp_status TEXT"))
                    db.session.commit()
                if "extra_work_text" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN extra_work_text TEXT"))
                    db.session.commit()
                if "notes_text" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN notes_text TEXT"))
                    db.session.commit()
                if "reviewed_at" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN reviewed_at DATETIME"))
                    db.session.commit()
                if "reviewed_by_user_id" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN reviewed_by_user_id INTEGER"))
                    db.session.commit()
                if "review_status" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'"))
                    db.session.commit()
                if "review_note" not in fcols:
                    db.session.execute(_sql_text("ALTER TABLE job_feedback ADD COLUMN review_note TEXT"))
                    db.session.commit()

                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_feedback_submitted_at ON job_feedback (submitted_at)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_feedback_outcome ON job_feedback (outcome)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_feedback_user_id ON job_feedback (user_id)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_feedback_reviewed_at ON job_feedback (reviewed_at)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_feedback_review_status ON job_feedback (review_status)"))
                db.session.commit()
                db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_job_feedback_job_submitted ON job_feedback (job_id, submitted_at)"))
                db.session.commit()
        except Exception:
            pass

        # task tablosu (mail reminders)
        try:
            trows = db.session.execute(_sql_text("PRAGMA table_info(task)")).fetchall()
            if trows:
                tcols = [r[1] for r in trows]
                if "reminder_days_before" not in tcols:
                    db.session.execute(_sql_text("ALTER TABLE task ADD COLUMN reminder_days_before INTEGER NOT NULL DEFAULT 0"))
                    db.session.commit()
                if "reminder_count" not in tcols:
                    db.session.execute(_sql_text("ALTER TABLE task ADD COLUMN reminder_count INTEGER NOT NULL DEFAULT 0"))
                    db.session.commit()
                if "last_reminder_at" not in tcols:
                    db.session.execute(_sql_text("ALTER TABLE task ADD COLUMN last_reminder_at DATETIME"))
                    db.session.commit()
                if "reminder_sent_count" not in tcols:
                    db.session.execute(_sql_text("ALTER TABLE task ADD COLUMN reminder_sent_count INTEGER NOT NULL DEFAULT 0"))
                    db.session.commit()
        except Exception:
            pass

        # person_day_status.status_type_id
        try:
            pdrows = db.session.execute(_sql_text("PRAGMA table_info(person_day_status)")).fetchall()
            if pdrows:
                pdcols = [r[1] for r in pdrows]
                if "status_type_id" not in pdcols:
                    db.session.execute(_sql_text("ALTER TABLE person_day_status ADD COLUMN status_type_id INTEGER"))
                    db.session.commit()
                    try:
                        db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_person_day_status_type_id ON person_day_status (status_type_id)"))
                        db.session.commit()
                    except Exception:
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
        except Exception:
            pass

        # mail_template columns (heading/intro)
        try:
            mtrows = db.session.execute(_sql_text("PRAGMA table_info(mail_template)")).fetchall()
            if mtrows:
                mtcols = [r[1] for r in mtrows]
                if "heading_template" not in mtcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_template ADD COLUMN heading_template TEXT"))
                    db.session.commit()
                if "intro_template" not in mtcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_template ADD COLUMN intro_template TEXT"))
                    db.session.commit()
        except Exception:
            pass
            
        # mail_log columns (V2 updates)
        try:
            mlrows = db.session.execute(_sql_text("PRAGMA table_info(mail_log)")).fetchall()
            if mlrows:
                mlcols = [r[1] for r in mlrows]
                # Relationships
                if "user_id" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN user_id INTEGER"))
                    db.session.commit()
                if "team_id" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN team_id INTEGER"))
                    db.session.commit()
                if "project_id" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN project_id INTEGER"))
                    db.session.commit()
                if "job_id" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN job_id INTEGER"))
                    db.session.commit()
                if "task_id" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN task_id INTEGER"))
                    db.session.commit()
                if "week_start" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN week_start DATE"))
                    db.session.commit()
                
                # Content & Meta
                if "cc_addr" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN cc_addr TEXT"))
                    db.session.commit()
                if "bcc_addr" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN bcc_addr TEXT"))
                    db.session.commit()
                if "body_preview" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN body_preview TEXT"))
                    db.session.commit()
                if "body_html" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN body_html TEXT"))
                    db.session.commit()
                if "sent_at" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN sent_at DATETIME"))
                    db.session.commit()
                # Missing critical columns
                if "mail_type" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN mail_type VARCHAR(50)"))
                    db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_mail_log_mail_type ON mail_log (mail_type)"))
                    db.session.commit()
                if "error_code" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN error_code VARCHAR(50)"))
                    db.session.commit()
                if "attachments_count" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN attachments_count INTEGER DEFAULT 0"))
                    db.session.commit()
                if "body_size_bytes" not in mlcols:
                    db.session.execute(_sql_text("ALTER TABLE mail_log ADD COLUMN body_size_bytes INTEGER DEFAULT 0"))
                    db.session.commit()
                    
                # Indexes
                try:

                    db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_mail_log_user_id ON mail_log (user_id)"))
                    db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_mail_log_job_id ON mail_log (job_id)"))
                    db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_mail_log_project_id ON mail_log (project_id)"))
                    db.session.commit()
                except: pass
                
                # mail_queue table (after mail_log columns)
                # Tablonun veritabanında var olduğundan emin ol (SQLAlchemy create_all bazen atlayabilir)
                try:
                    mqrows = db.session.execute(_sql_text("PRAGMA table_info(mail_queue)")).fetchall()
                    if not mqrows:
                        db.session.execute(_sql_text("""
                            CREATE TABLE mail_queue (
                                id INTEGER PRIMARY KEY,
                                mail_type VARCHAR(50) NOT NULL,
                                recipients TEXT NOT NULL,
                                subject VARCHAR(255) NOT NULL,
                                html_content TEXT NOT NULL,
                                cc TEXT,
                                bcc TEXT,
                                meta_json TEXT,
                                user_id INTEGER,
                                project_id INTEGER,
                                job_id INTEGER,
                                task_id INTEGER,
                                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                                created_at DATETIME NOT NULL,
                                processed_at DATETIME,
                                error_message TEXT,
                                retry_count INTEGER NOT NULL DEFAULT 0,
                                priority INTEGER NOT NULL DEFAULT 0,
                                sent_at DATETIME
                            )
                        """))
                        db.session.commit()
                        # Indexes
                        db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_mail_queue_status ON mail_queue (status)"))
                        db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_mail_queue_mail_type ON mail_queue (mail_type)"))
                        db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_mail_queue_priority ON mail_queue (priority)"))
                        db.session.execute(_sql_text("CREATE INDEX IF NOT EXISTS ix_mail_queue_created_at ON mail_queue (created_at)"))
                        db.session.commit()
                except Exception:
                    pass

        except Exception:
            pass

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
        log.exception("[ensure_schema] migration skipped/failed: %s", str(e))

# Initialize default data
def init_default_data():
    try:
        # Mail template sistemi kaldırıldı (09.02.2026)
        # MailTemplate seed kodları artık kullanılmıyor

        # Initialize default firmalar - always ensure they exist
        firma_names = ["Netmon", "Final", "Hytech"]
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
        
        # Initialize default personnel status types - always ensure they exist
        default_status_types = [
            {"name": "Senelik İzin", "code": "leave", "color": "#be123c", "icon": "🏖️", "display_order": 1},
            {"name": "Raporlu", "code": "sick", "color": "#dc2626", "icon": "🏥", "display_order": 2},
            {"name": "Home Ofis", "code": "home_office", "color": "#0284c7", "icon": "🏠", "display_order": 3},
            {"name": "Ofis", "code": "office", "color": "#0891b2", "icon": "🏢", "display_order": 4},
            {"name": "Mazeret İzni", "code": "excuse", "color": "#d97706", "icon": "📋", "display_order": 5},
            {"name": "Ücretsiz İzin", "code": "unpaid_leave", "color": "#7c3aed", "icon": "💰", "display_order": 6},
        ]
        for st_data in default_status_types:
            existing = PersonnelStatusType.query.filter_by(code=st_data["code"]).first()
            if not existing:
                db.session.add(PersonnelStatusType(
                    name=st_data["name"],
                    code=st_data["code"],
                    color=st_data["color"],
                    icon=st_data["icon"],
                    display_order=st_data["display_order"],
                    is_active=True
                ))
        
        # Initialize default role permissions - always ensure they exist
        try:
            from models import RolePermission, init_role_permissions as _init_role_perms
            _init_role_perms()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        log.error(f"init_default_data failed: {e}")
        # will retry on next request





# --- ONE-TIME STARTUP INIT (per process) ---
# Running schema migrations and seed-data on *every* request can cause serious
# contention with SQLite (especially under gunicorn with multiple workers/threads).
# We guard it to run only once per process.
import threading as _threading
__startup_lock = _threading.Lock()
__startup_done = False
__backup_thread_started = False

def _run_startup_tasks_once():
    global __startup_done
    global __backup_thread_started
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

        # Optional scheduled SQLite backups
        try:
            if not __backup_thread_started:
                interval_min = int(os.getenv("BACKUP_INTERVAL_MINUTES", "0") or 0)
                keep_n = int(os.getenv("BACKUP_KEEP", "14") or 14)
                if interval_min > 0:
                    __backup_thread_started = True

                    def _backup_loop():
                        while True:
                            try:
                                _time.sleep(max(10, interval_min * 60))
                                with app.app_context():
                                    src = _sqlite_db_path()
                                    if not src:
                                        continue
                                    backups_dir = os.path.join(app.instance_path, "backups")
                                    os.makedirs(backups_dir, exist_ok=True)
                                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    dest = os.path.join(backups_dir, f"backup_{stamp}.db")
                                    if _create_sqlite_backup_file(dest):
                                        try:
                                            files = sorted(
                                                [os.path.join(backups_dir, f) for f in os.listdir(backups_dir) if f.lower().endswith(".db")],
                                                key=lambda p: os.path.getmtime(p),
                                                reverse=True,
                                            )
                                            for old in files[keep_n:]:
                                                try:
                                                    os.remove(old)
                                                except Exception:
                                                    pass
                                        except Exception:
                                            pass
                            except Exception:
                                pass

                    t = _threading2.Thread(target=_backup_loop, daemon=True)
                    t.start()
        except Exception:
            pass
        
        # Voice message cleanup (delete records and files older than 7 days)
        try:
            __voice_cleanup_started = False
            if not __voice_cleanup_started:
                __voice_cleanup_started = True
                
                def _voice_cleanup_loop():
                    while True:
                        try:
                            _time.sleep(24 * 60 * 60)  # Her 24 saatte bir
                            with app.app_context():
                                try:
                                    cutoff = datetime.now() - timedelta(days=7)
                                    old_messages = VoiceMessage.query.filter(VoiceMessage.created_at < cutoff).all()
                                    
                                    upload_dir = app.config.get("UPLOAD_FOLDER", "uploads")
                                    deleted_count = 0
                                    
                                    for msg in old_messages:
                                        # Dosyayı sil
                                        if msg.audio_path:
                                            try:
                                                file_path = os.path.join(upload_dir, msg.audio_path)
                                                if os.path.exists(file_path):
                                                    os.remove(file_path)
                                            except Exception:
                                                pass
                                        
                                        # Veritabanından sil
                                        db.session.delete(msg)
                                        deleted_count += 1
                                    
                                    if deleted_count > 0:
                                        db.session.commit()
                                        log.info(f"[VoiceCleanup] Deleted {deleted_count} voice messages older than 7 days")
                                except Exception as e:
                                    log.error(f"[VoiceCleanup] Error: {e}")
                                    try:
                                        db.session.rollback()
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                
                cleanup_thread = _threading2.Thread(target=_voice_cleanup_loop, daemon=True)
                cleanup_thread.start()
        except Exception:
            pass
        

        
        # Mail Kuyruk İşçisi Başlat
        try:
            from services.mail_service import start_mail_worker
            start_mail_worker(app)
        except Exception as e:
            logging.error(f"Mail worker start failed: {e}")
        
        __startup_done = True


@app.before_request
def _ensure_schema_before_request():
    _run_startup_tasks_once()
    try:
        _check_sla_notifications()
    except Exception:
        pass
# --- END AUTO MIGRATION ---
@socketio.on("connect")
def _socket_connect():
    try:
        uid = session.get("user_id")
        if not uid:
            return
        user = db.session.get(User, uid)
        if not user:
            return
        try:
            join_room(f"chat_user_{int(uid)}")
        except Exception:
            pass
        now = datetime.now()
        _touch_user_activity(user, now=now)
        session["_last_seen_touch_ts"] = now.timestamp()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


@socketio.on("heartbeat")
def _socket_heartbeat(_data=None):
    try:
        uid = session.get("user_id")
        if not uid:
            return
        user = db.session.get(User, uid)
        if not user:
            return
        now = datetime.now()
        _touch_user_activity(user, now=now)
        session["_last_seen_touch_ts"] = now.timestamp()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


@socketio.on("chat_join")
def _socket_chat_join(data=None):
    try:
        uid = session.get("user_id")
        if not uid:
            return
        user = db.session.get(User, uid)
        if not user:
            return
        team_id = int((data or {}).get("team_id", 0) or 0)
        if not _can_access_chat_team(user, team_id=team_id):
            return
        join_room(f"chat_team_{team_id}")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


@socketio.on("chat_leave")
def _socket_chat_leave(data=None):
    try:
        uid = session.get("user_id")
        if not uid:
            return
        user = db.session.get(User, uid)
        if not user:
            return
        team_id = int((data or {}).get("team_id", 0) or 0)
        if not _can_access_chat_team(user, team_id=team_id):
            return
        leave_room(f"chat_team_{team_id}")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Run the same guarded startup path used by requests.
        # This starts the mail worker (once) and runs schema/seed tasks.
        try:
            _run_startup_tasks_once()
        except Exception as e:
            log.error(f"Startup tasks failed in __main__: {e}")
        # Development için varsayılan True, production'da DEBUG=0 ile kapatılabilir
        debug_env = str(os.getenv("DEBUG", "") or "").strip().lower()
        if debug_env:
            # Eğer DEBUG environment variable set edilmişse, onu kullan
            debug = debug_env in ("1", "true", "yes", "on")
        else:
            # Development için varsayılan True (kod değişikliklerini algılar)
            debug = True
        socketio.run(app, debug=debug)



















