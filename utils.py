import os
import sqlite3
import io
import json
import hashlib
import smtplib
import mimetypes
import html
import logging
import re
import shutil
import secrets as _secrets
import time as _time
import threading as _threading2
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Tuple, List, Any
import requests
from flask import current_app, session, request, g, redirect, url_for, flash, abort, jsonify
from werkzeug.utils import secure_filename
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
# from jinja2 import Environment, BaseLoader, select_autoescape, StrictUndefined  # Removed unused import
from extensions import db, socketio
from models import *
from sqlalchemy import or_, and_, desc, func, text as _sql_text, insert
from sqlalchemy.exc import IntegrityError

log = logging.getLogger('planner')


TR_DAYS = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"]
SHIFT_ORDER = {"Gündüz": 1, "Gündüz Yol": 2, "Gece": 3}
ONLINE_WINDOW = timedelta(minutes=5)

KANBAN_COLUMNS = ["PLANNED", "ASSIGNED", "PUBLISHED", "REPORTED", "CLOSED"]
KANBAN_STATUS_ORDER = {s: i for i, s in enumerate(KANBAN_COLUMNS, start=1)}
KANBAN_LABEL_TR = {
    "PLANNED": "Planlandı",
    "ASSIGNED": "Atandı",
    "PUBLISHED": "Sahada",
    "REPORTED": "Raporlandı",
    "CLOSED": "Kapandı",
}
KANBAN_STATUS_MIGRATE_MAP = {
    "PLANLANDI": "PLANNED",
    "ATANDI": "ASSIGNED",
    "SAHADA": "PUBLISHED",
    "GERİ_BİLDİRİM": "REPORTED",
    "GERI_BILDIRIM": "REPORTED",
    "GERI_BİLDİRİM": "REPORTED",
    "KONTROLDE": "REPORTED",
    "KAPALI": "CLOSED",
}


def _normalize_kanban_status(st: Optional[str]) -> str:
    raw = (st or "").strip()
    if not raw:
        return "PLANNED"
    mapped = KANBAN_STATUS_MIGRATE_MAP.get(raw, raw)
    mapped = (mapped or "").strip().upper()
    if mapped in KANBAN_COLUMNS:
        return mapped
    return "PLANNED"


def _set_job_kanban_status(job: "Job", new_status: str, *, changed_by_user_id: Optional[int] = None, note: Optional[str] = None) -> bool:
    if not job:
        return False
    ns = _normalize_kanban_status(new_status)
    old = _normalize_kanban_status(getattr(job, "kanban_status", None))
    if old == ns:
        return False
    job.kanban_status = ns
    try:
        db.session.add(JobStatusHistory(
            job_id=job.id,
            from_status=old,
            to_status=ns,
            note=(note or None),
            changed_by_user_id=changed_by_user_id,
            changed_at=datetime.now(),
        ))
    except Exception:
        pass
    return True


def _promote_job_kanban_status(job: "Job", required_status: str, *, changed_by_user_id: Optional[int] = None, note: Optional[str] = None) -> bool:
    """
    Promote forward only (never demote) according to KANBAN_STATUS_ORDER.
    """
    if not job:
        return False
    cur = _normalize_kanban_status(getattr(job, "kanban_status", None))
    req = _normalize_kanban_status(required_status)
    if KANBAN_STATUS_ORDER.get(cur, 1) >= KANBAN_STATUS_ORDER.get(req, 1):
        return False
    return _set_job_kanban_status(job, req, changed_by_user_id=changed_by_user_id, note=note)

def normalize_shift(shift_value):
    """Eski shift değerlerini yeni formata çevir (backward compatibility)"""
    if not shift_value:
        return ""
    shift_map = {
        "Gündüz": "08:30 - 18:00",
        "Gündüz Yol": "08:30 - 18:00 YOL",
        "Gece": "00:00 - 06:00"
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

# ===================== HELPERS =====================

def parse_date(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _effective_main_project_id_for_subprojects(project_id: int) -> int:
    """
    Returns the "main project" id to use for SubProject ownership.

    - If `project_id` is a template project (Project.region == "-"), it is the owner.
    - If `project_id` is a plan-row project (Project.region != "-"), try to find a matching template
      by `project_code` (region == "-") and use that as the owner.
    - Fallback: return the given project_id.
    """
    pid = int(project_id or 0)
    if pid <= 0:
        return 0
    try:
        p = Project.query.get(pid)
    except Exception:
        p = None
    if not p:
        return pid
    if (p.region or "").strip() == "-":
        return int(p.id)
    try:
        tpl = Project.query.filter(Project.region == "-", Project.project_code == p.project_code).first()
        if tpl:
            return int(tpl.id)
    except Exception:
        pass
    return int(p.id)


def _subproject_allowed_for_project(*, subproject_id: int, project_id: int) -> bool:
    sid = int(subproject_id or 0)
    pid = int(project_id or 0)
    if sid <= 0:
        return True
    if pid <= 0:
        return False
    sp = SubProject.query.get(sid)
    if not sp:
        return False
    owner_id = _effective_main_project_id_for_subprojects(pid)
    return int(sp.project_id or 0) in {pid, owner_id}


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def pastel_color(key: str) -> str:
    h = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
    hue = h % 360
    return f"hsl({hue} 70% 88%)"


def team_color(team_id: int) -> str:
    # Farklı ekipler için farklı renkler - HEX formatında
    # 12 farklı renk paleti
    colors = [
        "#e5484d",  # Kırmızı
        "#3b82f6",  # Mavi
        "#10b981",  # Yeşil
        "#f59e0b",  # Turuncu
        "#8b5cf6",  # Mor
        "#ec4899",  # Pembe
        "#06b6d4",  # Cyan
        "#f97316",  # Turuncu-kırmızı
        "#84cc16",  # Açık yeşil
        "#6366f1",  # İndigo
        "#14b8a6",  # Teal
        "#f43f5e",  # Rose
    ]
    # team_id'ye göre renk seç (modulo ile döngü)
    return colors[team_id % len(colors)]


def format_date_range(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return start_date.strftime("%d.%m.%Y")
    if start_date.year == end_date.year and start_date.month == end_date.month:
        return f"{start_date.strftime('%d')}-{end_date.strftime('%d')}.{end_date.strftime('%m.%Y')}"
    if start_date.year == end_date.year:
        return f"{start_date.strftime('%d.%m')}-{end_date.strftime('%d.%m.%Y')}"
    return f"{start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}"


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


# =================== HAFTALIK DİNAMİK EKİP NUMARALAMA ===================

def get_weekly_team_map(week_start_date: date) -> Dict[int, int]:
    """
    Verilen hafta için tüm ekiplerin dinamik numaralarını hesaplar.
    Döndürür: {team_id: display_number} (1'den başlayan sıra numaraları)
    
    Her hafta için ekip numaraları 1'den başlar ve o hafta kullanılan
    ekiplerin ID sırasına göre numara verilir.
    """
    ws = week_start(week_start_date)
    we = ws + timedelta(days=6)
    
    # O hafta kullanılan tüm ekip ID'lerini bul (sıralı)
    team_ids_query = db.session.query(PlanCell.team_id)\
        .filter(PlanCell.work_date >= ws)\
        .filter(PlanCell.work_date <= we)\
        .filter(PlanCell.team_id != None)\
        .filter(PlanCell.status != 'cancelled')\
        .distinct()\
        .order_by(PlanCell.team_id.asc())\
        .all()
    
    team_ids = [t[0] for t in team_ids_query if t[0]]
    
    # Her team_id'ye 1'den başlayan sıra numarası ata
    return {tid: idx + 1 for idx, tid in enumerate(team_ids)}


def get_weekly_team_display_name(team_id: int, week_start_date: date) -> str:
    """
    Verilen hafta için ekibin görüntüleme adını döner.
    O hafta kullanılan tüm ekipleri bulur ve sıraya göre numara verir.
    
    Örneğin: Team ID 47 -> "Ekip 1" (eğer o hafta ilk kullanılan ekipse)
    """
    if not team_id:
        return ""
    
    team_map = get_weekly_team_map(week_start_date)
    
    if team_id in team_map:
        return f"Ekip {team_map[team_id]}"
    
    # Fallback: Eğer haftalık haritada yoksa, veritabanındaki adı kullan
    try:
        t = Team.query.get(team_id)
        if t and (t.name or "").strip():
            return (t.name or "").strip()
    except Exception:
        pass
    
    return f"Ekip #{team_id}"


def get_team_members(team_id: int) -> List[Dict[str, Any]]:
    """
    Ekip ID'sine göre personel listesini döndürür.
    Team.signature alanından personel ID'lerini çıkarır ve isimlerini getirir.
    
    Döndürür: [{"id": 1, "full_name": "Ali Yılmaz"}, ...]
    """
    if not team_id:
        return []
    
    try:
        team = Team.query.get(team_id)
        if not team or not team.signature:
            return []
        
        # Signature formatı: "1,2,3" (virgülle ayrılmış personel ID'leri)
        person_ids = [int(x.strip()) for x in team.signature.split(",") if x.strip().isdigit()]
        
        if not person_ids:
            return []
        
        # Personel bilgilerini getir
        persons = Person.query.filter(Person.id.in_(person_ids)).order_by(Person.full_name.asc()).all()
        
        return [{"id": p.id, "full_name": p.full_name or f"Kişi #{p.id}"} for p in persons]
    
    except Exception as e:
        log.warning(f"get_team_members error for team_id={team_id}: {e}")
        return []


def get_team_members_names(team_id: int) -> List[str]:
    """
    Ekip ID'sine göre sadece personel isimlerini döndürür.
    Tooltip gibi basit görüntüleme için kullanılır.
    
    Döndürür: ["Ali Yılmaz", "Veli Kaya", ...]
    """
    members = get_team_members(team_id)
    return [m["full_name"] for m in members]


def set_assignments_and_team(cell: PlanCell, person_ids: List[int], preferred_vehicle_info: Optional[str] = None):
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
    vehicle = None
    if t and t.vehicle_id:
        vehicle = Vehicle.query.get(t.vehicle_id)
    cell.team_id = t.id if t else None
    if preferred_vehicle_info is not None:
        cell.vehicle_info = preferred_vehicle_info if preferred_vehicle_info else None
    else:
        apply_team_vehicle_to_cell(cell, vehicle)

    return added_ids


def apply_team_vehicle_to_cell(cell: PlanCell, vehicle: Optional[Vehicle]):
    if not cell:
        return
    cell.vehicle_info = vehicle.plate if vehicle else None


def apply_team_vehicle_to_cells(team: Team, vehicle: Optional[Vehicle], commit: bool = True):
    if not team:
        return
    plate = vehicle.plate if vehicle else None
    db.session.query(PlanCell).filter(PlanCell.team_id == team.id).update(
        {PlanCell.vehicle_info: plate}, synchronize_session=False
    )
    if commit:
        db.session.commit()


def _vehicle_payload(vehicle: Optional[Vehicle], assigned_team_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if not vehicle:
        return None
    return {
        "id": int(vehicle.id),
        "plate": vehicle.plate,
        "brand": vehicle.brand,
        "model": vehicle.model,
        "year": vehicle.year,
        "type": vehicle.vehicle_type,
        "capacity": vehicle.capacity,
        "vodafone_approval": bool(vehicle.vodafone_approval),
        "status": vehicle.status,
        "notes": vehicle.notes or "",
        "assigned_team_id": int(assigned_team_id) if assigned_team_id else None
    }


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


ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "webp", "gif"}
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
    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
    full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique)
    fs.save(full_path)
    return unique

def delete_upload(filename: Optional[str]):
    if not filename:
        return
    # prevent path traversal (best-effort)
    if any(x in filename for x in ("..", "/", "\\")):
        return
    full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception:
        pass


# ---------- MAIL SETTINGS ----------
MAIL_PASSWORD_PLACEHOLDER = "••••••"


def _set_secure_file_permissions(path: str):
    try:
        if os.name == "posix":
            os.chmod(path, 0o600)
        else:
            # Best-effort on Windows; chmod maps to read-only flag only.
            os.chmod(path, 0o600)
    except Exception:
        pass


def _load_mail_settings_file() -> dict:
    import json
    if not os.path.exists(os.path.join(current_app.instance_path, "mail_settings.json")):
        return {}
    try:
        with open(os.path.join(current_app.instance_path, "mail_settings.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _env_bool(name: str) -> bool:
    v = (os.getenv(name) or '').strip().lower()
    return v in ('1', 'true', 'yes', 'y', 'on')

def load_mail_settings() -> dict:
    # file -> env override (env wins if set)
    cfg = {
        'host': '',
        'port': 587,
        'user': '',
        'password': '',
        'from_name': '',  # Gönderen Adı (Takma Ad)
        'from_addr': '',
        'use_tls': True,
        'use_ssl': False,
        'notify_to': '',
        'notify_cc': '',
    }
    cfg.update(_load_mail_settings_file())

    if os.getenv('SMTP_HOST'):
        cfg['host'] = os.getenv('SMTP_HOST') or ''
    if os.getenv('SMTP_PORT'):
        try:
            cfg['port'] = int(os.getenv('SMTP_PORT', '587'))
        except Exception:
            pass
    if os.getenv('SMTP_USER'):
        cfg['user'] = os.getenv('SMTP_USER') or ''
    if os.getenv('SMTP_PASS'):
        cfg['password'] = os.getenv('SMTP_PASS') or ''
    if os.getenv('SMTP_FROM'):
        cfg['from_addr'] = os.getenv('SMTP_FROM') or ''
    if os.getenv('SMTP_NOTIFY_TO') is not None:
        cfg['notify_to'] = os.getenv('SMTP_NOTIFY_TO') or ''
    if os.getenv('SMTP_NOTIFY_CC') is not None:
        cfg['notify_cc'] = os.getenv('SMTP_NOTIFY_CC') or ''
    if os.getenv('SMTP_TLS'):
        cfg['use_tls'] = _env_bool('SMTP_TLS')
    if os.getenv('SMTP_SSL'):
        cfg['use_ssl'] = _env_bool('SMTP_SSL')

    # normalize types
    try:
        cfg['port'] = int(cfg.get('port') or 587)
    except Exception:
        cfg['port'] = 587
    cfg['use_tls'] = bool(cfg.get('use_tls', True))
    cfg['use_ssl'] = bool(cfg.get('use_ssl', False))
    return cfg

def save_mail_settings(data: dict):
    import json
    os.makedirs(current_app.instance_path, exist_ok=True)
    tmp_path = os.path.join(current_app.instance_path, "mail_settings.json") + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _set_secure_file_permissions(tmp_path)
    os.replace(tmp_path, os.path.join(current_app.instance_path, "mail_settings.json"))
    _set_secure_file_permissions(os.path.join(current_app.instance_path, "mail_settings.json"))


def _split_email_list(val) -> List[str]:
    """
    Normalize an input that may be:
      - string: "a@b.com, c@d.com"
      - list/tuple/set: ["a@b.com", "c@d.com"]
      - JSON list string: '["a@b.com","c@d.com"]'
      - Python list string (legacy bug): "['a@b.com']"
    into a list of raw entries.
    """
    if not val:
        return []

    # Fast-path: already a sequence (but not a string/bytes)
    if isinstance(val, (list, tuple, set)):
        out = []
        for x in val:
            s = (str(x) if x is not None else "").strip()
            if s:
                out.append(s)
        return out

    s = str(val).strip()
    if not s:
        return []

    # If it's a serialized list, parse it.
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
        parsed = None
        try:
            import json as _json

            parsed = _json.loads(s)
        except Exception:
            parsed = None
        if parsed is None:
            try:
                import ast as _ast

                parsed = _ast.literal_eval(s)
            except Exception:
                parsed = None
        if isinstance(parsed, (list, tuple, set)):
            return _split_email_list(list(parsed))

    parts = re.split(r"[,\s;]+", s)
    out = []
    for p in parts:
        p = (p or "").strip()
        if not p:
            continue
        out.append(p)
    return out


class MailSendError(RuntimeError):
    def __init__(self, code: str, user_message: str, *, recipient: str = '', debug_detail: str = ''):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.recipient = recipient or ''
        self.debug_detail = (debug_detail or "").strip()


def _is_valid_email_address(value: str) -> bool:
    """
    Accepts either a raw email (a@b.com) or display-name form (Name <a@b.com>).
    """
    if not value:
        return False
    try:
        from email.utils import parseaddr
        _, addr = parseaddr(str(value))
    except Exception:
        addr = str(value)
    addr = (addr or "").strip()
    if not addr or " " in addr:
        return False
    if "@" not in addr:
        return False
    local, _, domain = addr.partition("@")
    if not local or not domain:
        return False
    return True


def _canonical_email(value: str) -> str:
    """
    Extract the bare email from values like:
      - "Name <a@b.com>" -> "a@b.com"
      - "a@b.com" -> "a@b.com"
    """
    if value is None:
        return ""
    try:
        from email.utils import parseaddr

        _, addr = parseaddr(str(value))
        return (addr or "").strip()
    except Exception:
        return (str(value) or "").strip()


def _smtp_exception_detail(exc: Exception) -> str:
    try:
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            code = getattr(exc, "smtp_code", None)
            err = getattr(exc, "smtp_error", None)
            if code or err:
                return f"{type(exc).__name__} smtp_code={code} smtp_error={err!r}"
        if isinstance(exc, smtplib.SMTPConnectError):
            code = getattr(exc, "smtp_code", None)
            err = getattr(exc, "smtp_error", None)
            if code or err:
                return f"{type(exc).__name__} smtp_code={code} smtp_error={err!r}"
        if isinstance(exc, smtplib.SMTPRecipientsRefused):
            try:
                return f"{type(exc).__name__} refused={getattr(exc, 'recipients', None)!r}"
            except Exception:
                return type(exc).__name__
        if isinstance(exc, smtplib.SMTPSenderRefused):
            code = getattr(exc, "smtp_code", None)
            err = getattr(exc, "smtp_error", None)
            snd = getattr(exc, "sender", None)
            return f"{type(exc).__name__} smtp_code={code} smtp_error={err!r} sender={snd!r}"
        return f"{type(exc).__name__}: {str(exc) or ''}".strip()
    except Exception:
        return str(exc) or "unknown"


def _mail_error_meta_from_exc(exc: Exception) -> dict:
    if isinstance(exc, MailSendError):
        return {
            "error_code": exc.code,
            "user_message": exc.user_message,
            "debug_detail": exc.debug_detail,
            "exc_type": type(exc).__name__,
        }
    code = _smtp_error_code(exc)
    return {
        "error_code": code,
        "user_message": _smtp_user_message(code),
        "debug_detail": _smtp_exception_detail(exc),
        "exc_type": type(exc).__name__,
    }


def _smtp_error_code(exc: Exception) -> str:
    import socket
    import ssl
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return 'timeout'
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return 'authentication'
    if isinstance(exc, smtplib.SMTPConnectError):
        return 'refused'
    if isinstance(exc, ConnectionRefusedError):
        return 'refused'
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return 'from_refused'
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return 'recipient_refused'
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        msg = (str(exc) or '').lower()
        if 'timed out' in msg or 'timeout' in msg:
            return 'timeout'
        return 'disconnected'
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return 'tls'
    if isinstance(exc, ssl.SSLError):
        return 'ssl_tls'
    msg = (str(exc) or '').lower()
    if 'timed out' in msg or 'timeout' in msg:
        return 'timeout'
    return 'unknown'


def _smtp_user_message(code: str) -> str:
    if code == 'timeout':
        return 'SMTP timeout: sunucu zamaninda yanit vermedi.'
    if code == 'authentication':
        return 'SMTP authentication hatasi: kullanici/sifre reddedildi.'
    if code == 'from_refused':
        return 'Gonderen (From) adresi reddedildi: From alanini tam bir e-posta olarak girin (ornegin ad@domain.com).'
    if code == 'ssl_tls':
        return 'SSL/TLS uyumsuzlugu: SSL/TLS ayarlarinizi kontrol edin.'
    if code == 'tls':
        return 'TLS desteklenmiyor veya baslatilamadi (STARTTLS).'
    if code == 'refused':
        return 'SMTP baglanti reddedildi: host/port veya firewall kontrol edin.'
    if code == 'recipient_refused':
        return 'Alici adresi reddedildi.'
    if code == 'disconnected':
        return 'SMTP baglantisi kesildi: sunucu baglantiyi kapatti.'
    if code == 'config':
        return 'SMTP ayarlari eksik.'
    if code == 'recipient':
        return 'Alici bulunamadi.'
    return 'SMTP gonderim hatasi.'


def _smtp_open(host: str, port: int, *, use_ssl: bool):
    if use_ssl:
        return smtplib.SMTP_SSL(host, port, timeout=30)
    return smtplib.SMTP(host, port, timeout=30)


def _smtp_close(server):
    if not server:
        return
    try:
        server.quit()
    except Exception:
        try:
            server.close()
        except Exception:
            pass


def send_email_smtp(to_addr, subject: str, html_body: str, attachments: Optional[List[dict]] = None,
                    cc_addrs=None, bcc_addrs=None, cfg_override: Optional[dict] = None):
    import time
    import random
    import copy
    from email.utils import formataddr

    cfg = dict(load_mail_settings())
    if cfg_override:
        cfg.update(cfg_override)

    host = (cfg.get('host') or '').strip()
    port = int(cfg.get('port', 587) or 587)
    user = (cfg.get('user') or '').strip()
    pw = (cfg.get('password') or '')
    from_name = (cfg.get('from_name') or '').strip()
    from_addr = (cfg.get('from_addr') or user).strip()
    use_tls = bool(cfg.get('use_tls', True))
    use_ssl = bool(cfg.get('use_ssl', False))

    # FIX: Force envelope sender to be the authenticated user to avoid "Sender/Recipient address rejected"
    if user and '@' in user:
        from_addr = user

    if not (host and user and pw and from_addr):
        raise MailSendError('config', _smtp_user_message('config'))
    
    # From header - eğer from_name varsa "Ad <email>" formatı kullan
    if from_name:
        from_header = formataddr((from_name, from_addr))
    else:
        from_header = from_addr

    to_list = _split_email_list(to_addr)
    cc_list = _split_email_list(cc_addrs)
    bcc_list = _split_email_list(bcc_addrs)
    rcpt = []
    for x in (to_list + cc_list + bcc_list):
        addr = _canonical_email(x)
        if not addr:
            continue
        if not _is_valid_email_address(addr):
            continue
        if addr not in rcpt:
            rcpt.append(addr)
    if not rcpt:
        raise MailSendError('recipient', _smtp_user_message('recipient'))

    base_msg = MIMEMultipart()
    base_msg['From'] = from_header
    base_msg['Subject'] = subject
    base_msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    if attachments:
        for att in attachments:
            try:
                fname = att.get('filename') or 'dosya'
                data = att.get('data') or b''
                content_type = att.get('content_type') or 'application/octet-stream'
                maintype, subtype = content_type.split('/', 1) if '/' in content_type else ('application', 'octet-stream')
                part = MIMEBase(maintype, subtype)
                part.set_payload(data)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment; filename="%s"' % fname)
                base_msg.attach(part)
            except Exception:
                continue

    def _send_one(recipient: str):
        delays = [0, 5, 10]
        last_exc = None
        for attempt, wait_s in enumerate(delays, start=1):
            if wait_s:
                _time.sleep(wait_s)
            server = None
            try:
                server = _smtp_open(host, port, use_ssl=use_ssl)
                try:
                    server.ehlo()
                except Exception:
                    pass
                if (not use_ssl) and use_tls:
                    server.starttls()
                    try:
                        server.ehlo()
                    except Exception:
                        pass
                server.login(user, pw)

                msg = copy.deepcopy(base_msg)
                if 'To' in msg:
                    del msg['To']
                msg['To'] = recipient

                server.sendmail(from_addr, [recipient], msg.as_string())
                return
            except Exception as e:
                last_exc = e
                code = _smtp_error_code(e)
                log.exception('SMTP send failed attempt=%s code=%s to=%s host=%s port=%s ssl=%s tls=%s', attempt, code, recipient, host, port, bool(use_ssl), bool(use_tls))
            finally:
                _smtp_close(server)

        code = _smtp_error_code(last_exc or Exception('unknown'))
        raise MailSendError(code, _smtp_user_message(code), recipient=recipient, debug_detail=_smtp_exception_detail(last_exc or Exception("unknown")))

    for i, r in enumerate(rcpt):
        _send_one(r)
        if len(rcpt) > 1 and i < len(rcpt) - 1:
            _time.sleep(random.uniform(1.0, 2.0))

def create_mail_log(*, kind: str, ok: bool, to_addr: str, subject: str, week_start_val: Optional[date] = None,
                    team_name: Optional[str] = None, error: Optional[str] = None, meta: Optional[dict] = None,
                    # Yeni parametreler (v2)
                    mail_type: Optional[str] = None,
                    cc_addrs: Optional[str] = None,
                    bcc_addrs: Optional[str] = None,
                    error_code: Optional[str] = None,
                    attachments: Optional[List[dict]] = None,
                    user_id: Optional[int] = None,
                    project_id: Optional[int] = None,
                    job_id: Optional[int] = None,
                    task_id: Optional[int] = None,
                    body_preview: Optional[str] = None,
                    body_html: Optional[str] = None,  # Tam HTML içerik
                    body_size: int = 0
                    ):
    """
    Kapsamlı Mail Loglama (v2)
    Args:
        kind: send/preview/test
        ok: Başarılı mı?
        to_addr: Alıcı adresleri
        subject: Konu
        ... diğer parametreler
    """
    try:
        import json
        
        # Meta verisini hazırla
        meta_final = meta or {}
        
        # Attachment sayısını hesapla
        att_count = 0
        if attachments:
            att_count = len(attachments)
            # Attachment isimlerini meta'ya ekle
            meta_final['attachments_list'] = [a.get('filename', 'unknown') for a in attachments]
            
        # MailLog nesnesi oluştur
        # Not: models.py güncellenene kadar bazı alanlar kwargs ile geçilirse hata verebilir
        # Bu yüzden güvenli bir şekilde dict unpacking kullanıyoruz veya doğrudan atıyoruz.
        # Ancak Model tanımında olmayan alanlar __init__'te hata verir. 
        # Bu sebeple önce kwargs hazirlayalim.

        log_data = {
            "kind": kind or "send",
            "ok": bool(ok),
            "to_addr": to_addr or "",
            "subject": subject or "",
            "week_start": week_start_val,
            "team_name": team_name or None,
            "error": error or None,
            "meta_json": json.dumps(meta_final, ensure_ascii=False) if meta_final else None,
        }
        
        # V2 alanlarını varsa ekleyelim (Model destekliyorsa çalışır, yoksa crash olmaması için kontrol edilebilir ama 
        # SQLAlchemy modelde olmayan alanı init'te verirsek TypeError alırız.
        # Bu aşamada models.py'nin güncel olduğunu varsayıyoruz. 
        # Eğer models.py güncel değilse migration yapılmalı.
        
        log_data["mail_type"] = mail_type or kind
        log_data["error_code"] = error_code
        log_data["cc_addr"] = cc_addrs if cc_addrs else None
        log_data["bcc_addr"] = bcc_addrs if bcc_addrs else None
        log_data["body_preview"] = body_preview
        log_data["body_html"] = body_html  # Tam HTML içerik
        log_data["attachments_count"] = att_count
        log_data["body_size_bytes"] = body_size
        log_data["sent_at"] = datetime.now() if ok and kind == "send" else None
        log_data["user_id"] = user_id
        log_data["project_id"] = project_id
        log_data["job_id"] = job_id
        log_data["task_id"] = task_id
        # Try to find team_id from team_name if not provided
        if not log_data.get("team_id") and log_data.get("team_name"):
            try:
                from models import Team
                t = Team.query.filter_by(name=log_data["team_name"]).first()
                if t:
                    log_data["team_id"] = t.id
            except Exception:
                pass

        # Modelde olmayan alanları temizle (Reflection kullanamadığımız için try-catch ile yapacağız ya da field listesi hardcoded)
        # En temizi: models.py güncellendi varsayımıyla ilerlemek.
        
        row = MailLog()
        for k, v in log_data.items():
            if hasattr(row, k):
                setattr(row, k, v)
        
        db.session.add(row)
        try:
            db.session.flush()
        except Exception as e:
            log.exception(f"MailLog flush failed: {e}")
            db.session.rollback()
            return

        try:
            if (not ok) and (kind or '') == 'send':
                link = '/reports/mail-log'
                try:
                    link = url_for('planner.mail_log_page')
                except Exception:
                    pass
                
                # Admin bildirimi
                _notify_admins(
                    event='mail_fail',
                    title='Mail Gonderim Hatasi',
                    body=((subject or '') + (' | ' + (error or '') if error else ''))[:500],
                    link_url=link,
                    mail_log_id=(row.id if getattr(row, 'id', None) else None),
                    meta=meta_final,
                )
        except Exception as e:
            log.warning(f"MailLog notify admin failed: {e}")
            
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        log.exception("MailLog yazilamadi: %s", str(e))


# _mail_body_env and _mail_subject_env removed (unused)

DEFAULT_JOB_MAIL_SUBJECT_TEMPLATE = "[{{ project_code }}] {{ site_code }} - {{ date }} - Is Atamasi"
DEFAULT_JOB_MAIL_BODY_TEMPLATE = """
<p><strong>Kisa Ozet</strong><br>{{ short_summary }}</p>
{% if job_details_list and job_details_list|length %}
<p><strong>Is Detayi</strong></p>
<ul>
{% for it in job_details_list %}
  <li>{{ it }}</li>
{% endfor %}
</ul>
{% endif %}
{% if checklist and checklist|length %}
<p><strong>Kontrol Listesi</strong></p>
<ul>
{% for c in checklist %}
  <li>{% if c.checked %}[x]{% else %}[ ]{% endif %} {{ c.label }}</li>
{% endfor %}
</ul>
{% endif %}
{% if links and links|length %}
<p><strong>Linkler</strong></p>
<ul>
{% for l in links %}
  <li><a href="{{ l.url }}">{{ l.label }}</a></li>
{% endfor %}
</ul>
{% endif %}
{% if people and people|length %}
<p><strong>Ekip</strong></p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%; font-size:13px;">
  <thead><tr><th>Ad Soyad</th><th>Cep</th></tr></thead>
  <tbody>
  {% for p in people %}
    <tr><td>{{ p.full_name }}</td><td>{{ p.phone }}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endif %}
"""

DEFAULT_BULK_TEAM_MAIL_SUBJECT_TEMPLATE = "Ekip: {{ team_name }} | {{ start }} - {{ end }} | Toplu Mail"
DEFAULT_BULK_TEAM_MAIL_BODY_TEMPLATE = """
<p><strong>Ekip:</strong> {{ team_name }}</p>
<p><strong>Aralik:</strong> {{ start }} - {{ end }}</p>
<p><strong>Is Adedi:</strong> {{ jobs_count }}</p>
{% if jobs_table_html %}
  {{ jobs_table_html | safe }}
{% endif %}
"""


# NOT: _get_default_mail_template() ve _render_mail_template() fonksiyonları
# mail şablon sistemi kaldırıldığı için artık kullanılmıyor (09.02.2026).
# Yeni mail işlevi email_base.html ve render_*_email() fonksiyonlarını kullanır.




def _abs_url(path: str) -> str:
    base = (request.host_url or "").rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _job_mail_context_for_cell(project_id: int, d: date, *, short_summary: str, job_details: str,
                               checklist: List[dict], links: List[dict]) -> dict:
    project = Project.query.get(project_id)
    cell = PlanCell.query.filter_by(project_id=project_id, work_date=d).first()
    team = Team.query.get(cell.team_id) if (cell and cell.team_id) else None

    people_rows = []
    if cell:
        people_rows = (
            db.session.query(Person.full_name, Person.phone, Person.email)
            .join(CellAssignment, CellAssignment.person_id == Person.id)
            .filter(CellAssignment.cell_id == cell.id)
            .order_by(Person.full_name.asc())
            .all()
        )

    people = [{"full_name": n, "phone": ph or "", "email": em or ""} for (n, ph, em) in people_rows]
    team_name = ""
    try:
        if cell and cell.team_name:
            team_name = cell.team_name
        elif cell and cell.team_id:
            t = Team.query.get(cell.team_id)
            team_name = (t.name if t else "") or ""
    except Exception:
        team_name = ""

    job_details_list = [x.strip() for x in (job_details or "").splitlines() if x.strip()]
    safe_links = []
    for l in (links or []):
        label = (l.get("label") or "").strip()
        url = (l.get("url") or "").strip()
        if not url:
            continue
        safe_links.append({"label": label or url, "url": url})

    return {
        "project_code": (project.project_code if project else "") or "",
        "site_code": (project.region if project else "") or "",
        "date": iso(d),
        "team_name": team_name,
        "short_summary": (short_summary or "").strip(),
        "job_details_list": job_details_list,
        "checklist": checklist or [],
        "links": safe_links,
        "people": people,
        "shift": (cell.shift if cell else "") or "",
        "vehicle": (cell.vehicle_info if cell else "") or "",
    }


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

ONLINE_WINDOW = timedelta(minutes=2)
LAST_SEEN_THROTTLE_SECONDS = 15

def _touch_user_activity(user: "User", now: Optional[datetime] = None) -> bool:
    """
    Updates user's last_seen on activity.
    If the user was offline (last_seen older than ONLINE_WINDOW), sets online_since = now.
    """
    if not user:
        return False
    now = now or datetime.now()
    try:
        was_offline = (not getattr(user, "last_seen", None)) or (user.last_seen < (now - ONLINE_WINDOW))
        user.last_seen = now
        if was_offline:
            user.online_since = now
        db.session.add(user)
        db.session.commit()
        return True
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False

def login_required(f):
    """Decorator to require login for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        # Gözlemci rolü POST isteklerini engelle (değişiklik yapamaz)
        if request.method == 'POST':
            current_user = get_current_user()
            if current_user and current_user.role == 'gözlemci':
                flash("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.", "danger")
                return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash("Bu işlem için admin yetkisi gereklidir.", "danger")
            return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function


def planner_or_admin_required(f):
    """Decorator to require admin or planner role for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = User.query.get(session['user_id'])
        if not user:
            flash("Oturum açmanız gerekiyor.", "danger")
            return redirect(url_for('auth.login'))
        role = (user.role or "").strip().lower()
        if not (bool(user.is_admin) or role in ("planlayici", "planlayıcı", "planner")):
            flash("Bu işlem için admin/planlayıcı yetkisi gereklidir.", "danger")
            return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function


def field_required(f):
    """Decorator to require field role (mobile portal)."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = get_current_user()
        if not user:
            session.clear()
            return redirect(url_for('auth.login'))
        if not bool(getattr(user, "is_active", True)):
            session.clear()
            return redirect(url_for('auth.login'))
        role = (user.role or "").strip().lower()
        if role != "field":
            flash("Bu sayfaya erişim yetkiniz yok.", "danger")
            return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function


def _user_is_admin_or_planner(user: "User") -> bool:
    if not user:
        return False
    if bool(getattr(user, "is_admin", False)):
        return True
    role = (getattr(user, "role", "") or "").strip().lower()
    return role in ("planlayici", "planlayŽñcŽñ", "planner")


def _can_access_chat_team(user: "User", *, team_id: int) -> bool:
    if not user:
        return False
    tid = int(team_id or 0)
    if tid <= 0:
        return False
    if _user_is_admin_or_planner(user):
        return True
    return int(getattr(user, "team_id", 0) or 0) == tid


# @app.before_request
def _touch_last_seen_before_request():
    try:
        uid = session.get("user_id")
        if not uid:
            return None
        path = request.path or ""
        if path.startswith("/static/") or path.startswith("/socket.io/"):
            return None

        now = datetime.now()
        last_ts = session.get("_last_seen_touch_ts")
        try:
            if last_ts and (now.timestamp() - float(last_ts)) < LAST_SEEN_THROTTLE_SECONDS:
                return None
        except Exception:
            pass

        user = User.query.get(uid)
        if not user:
            return None
        if _touch_user_activity(user, now=now):
            session["_last_seen_touch_ts"] = now.timestamp()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return None


# @app.before_request
def _field_portal_guard():
    """
    Field users must not access admin/staff screens.
    Keep an allowlist for mobile portal + static + file downloads.
    """
    try:
        if 'user_id' not in session:
            return None
        user = get_current_user()
        if not user:
            return None
        if (user.role or "").strip().lower() != "field":
            return None
        path = request.path or ""
        if path.startswith("/static/") or path.startswith("/files/") or path.startswith("/socket.io/"):
            return None
        if path.startswith("/me") or path.startswith("/logout") or path.startswith("/login"):
            return None
        # allow field portal utilities (online list) + chat + reschedule APIs
        if path.startswith("/chat") or path.startswith("/api/chat/"):
            return None
        if path.startswith("/announcements") or path.startswith("/api/announcements/"):
            return None
        if path == "/api/online_users":
            return None
        if path.startswith("/api/jobs/") and path.endswith("/reschedule"):
            return None
        # allow field report POST redirect targets etc.
        return redirect(url_for('planner.portal_home'))
    except Exception:
        return None


# @app.before_request
def _rbac_guard_admin_api_paths():
    """
    Central RBAC guard to reduce risk of missing decorators on new endpoints.
    """
    try:
        path = request.path or ""
        if path == "/health" or path.startswith("/static/"):
            return None

        # Require login for all /api/* except health.
        if path.startswith("/api/") and 'user_id' not in session:
            return jsonify({"ok": False, "error": "auth"}), 401

        # Protect admin namespace if a decorator is missed.
        if path.startswith("/admin"):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))
            u = get_current_user()
            if not u:
                return redirect(url_for('auth.login'))
            role = (u.role or "").strip().lower()
            if not (bool(getattr(u, "is_admin", False)) or role in ("planner", "planlayici", "planlayıcı")):
                flash("Bu işlem için admin/planlayıcı yetkisi gereklidir.", "danger")
                return redirect(url_for('planner.plan_week'))
    except Exception:
        pass
    return None


# ---------- CSRF (simple) ----------
def _csrf_token() -> str:
    import secrets
    tok = session.get("_csrf_token")
    if not tok:
        tok = secrets.token_urlsafe(32)
        session["_csrf_token"] = tok
    return tok


def _csrf_verify(form_token: str) -> bool:
    return bool(form_token) and form_token == session.get("_csrf_token")




def _csrf_token_from_request() -> str:
    try:
        hdr = (request.headers.get("X-CSRF-Token") or "").strip()
    except Exception:
        hdr = ""
    if hdr:
        return hdr
    try:
        if request.is_json:
            data = request.get_json(silent=True) or {}
            tok = str(data.get("csrf_token") or "").strip()
            if tok:
                return tok
    except Exception:
        pass
    try:
        tok = str(request.form.get("csrf_token") or "").strip()
        if tok:
            return tok
    except Exception:
        pass
    return ""


# @app.before_request
def _csrf_protect_unsafe_methods():
    try:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        if request.path == "/login":
            return None
        if request.path == "/health":
            return None
        if request.path.startswith("/static/"):
            return None
        # Bypass CSRF for API endpoints (they use their own auth)
        if request.path.startswith("/api/"):
            return None
        # Bypass CSRF for admin/user routes (they have their own CSRF check)
        if request.path.startswith("/admin/users/"):
            return None

        tok = _csrf_token_from_request()
        if not _csrf_verify(tok):
            return jsonify({"ok": False, "error": "CSRF dogrulamasi basarisiz."}), 400
    except Exception:
        return jsonify({"ok": False, "error": "CSRF dogrulamasi basarisiz."}), 400
    return None


# ========== ROLE-BASED ACCESS CONTROL ==========

def _check_role_permission(user_role: str, permission_key: str) -> bool:
    """
    Rolün belirli bir izne sahip olup olmadığını kontrol eder.
    
    Args:
        user_role: Kullanıcının rolü (admin, planner, field, user, gözlemci)
        permission_key: İzin anahtarı (reports_analytics, admin_users, vb.)
    
    Returns:
        True: Erişim var
        False: Erişim yok
    """
    if not user_role or not permission_key:
        return False
    
    # Super admin her şeye erişebilir
    try:
        current_user = get_current_user()
        if current_user and getattr(current_user, 'is_super_admin', False):
            return True
    except Exception:
        pass
    
    # RolePermission tablosunu kontrol et
    try:
        from models import RolePermission
        perm = RolePermission.query.filter_by(
            role=user_role, 
            permission_key=permission_key
        ).first()
        
        if perm:
            return perm.can_access
        
        # Eğer kayıt yoksa, varsayılan olarak erişim yok
        return False
    except Exception:
        # Model yoksa veya hata varsa, erişim ver
        return True


def _can_access_reports_analytics() -> bool:
    """Kullanıcının raporlar/analitik sayfasına erişimi var mı?"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False
        return _check_role_permission(current_user.role or "user", "reports_analytics")
    except Exception:
        return True


def _can_access_admin_users() -> bool:
    """Kullanıcının admin/users sayfasına erişimi var mı?"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False
        return _check_role_permission(current_user.role or "user", "admin_users")
    except Exception:
        return True


def _can_access_tasks_management() -> bool:
    """Kullanıcının tasks sayfasına erişimi var mı?"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False
        return _check_role_permission(current_user.role or "user", "tasks_management")
    except Exception:
        return True


_FEEDBACK_ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "mp4", "mov", "pdf"}
_FEEDBACK_IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}
_FEEDBACK_VIDEO_EXT = {"mp4", "mov"}


def _feedback_file_type_for_ext(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    if e in _FEEDBACK_IMAGE_EXT:
        return "image"
    if e in _FEEDBACK_VIDEO_EXT:
        return "video"
    return "file"


def _save_feedback_uploads(files, *, feedback_id: int) -> List["JobFeedbackMedia"]:
    if not files:
        return []

    safe_feedback_id = int(feedback_id or 0)
    if safe_feedback_id <= 0:
        return []

    base_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "feedback", str(safe_feedback_id))
    os.makedirs(base_dir, exist_ok=True)

    out = []
    for f in files:
        if not f or not getattr(f, "filename", None):
            continue
        original_name = (f.filename or "").strip()
        safe_name = secure_filename(original_name) or "file"
        ext = os.path.splitext(safe_name)[1].lower().lstrip(".")
        if ext not in _FEEDBACK_ALLOWED_EXT:
            raise ValueError(f"Dosya tipi izinli degil: {ext or '-'}")

        token = _secrets.token_hex(8)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_name = f"{stamp}_{token}_{safe_name}"
        final_path = os.path.join(base_dir, final_name)
        f.save(final_path)

        rel_path = os.path.join("feedback", str(safe_feedback_id), final_name).replace("\\", "/")
        out.append(JobFeedbackMedia(
            feedback_id=safe_feedback_id,
            file_path=rel_path,
            file_type=_feedback_file_type_for_ext(ext),
            original_name=original_name,
            uploaded_at=datetime.now(),
        ))

    return out


_RATE_LOCK = _threading2.Lock()
_RATE_BUCKETS: Dict[str, List[float]] = {}


def _rate_limit(key: str, *, limit: int, window_seconds: int) -> bool:
    """
    Returns True if allowed, False if rate-limited.
    """
    if not key:
        return True
    now = _time.time()
    cutoff = now - float(window_seconds or 0)
    with _RATE_LOCK:
        arr = _RATE_BUCKETS.get(key) or []
        arr = [t for t in arr if t >= cutoff]
        if len(arr) >= int(limit or 0):
            _RATE_BUCKETS[key] = arr
            return False
        arr.append(now)
        _RATE_BUCKETS[key] = arr
    return True


# ---------- MAIL SETTINGS PAGE ----------
def _send_test_mail(to_addr: str, *, cfg_override: Optional[dict] = None):
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    html_body = render_template(
        "email_base.html",
        title="SMTP Test Maili",
        heading="SMTP Test Maili",
        intro="Bu mail, Mail Ayarları sayfasından gönderilen test mesajıdır.",
        table_headers=["Alan", "Değer"],
        table_rows=[["Tarih/Saat", now], ["Sunucu", request.host_url.rstrip("/")]],
        footer=f"Otomatik test maili - {now}",
    )
    send_email_smtp(to_addr, "SMTP Test Maili", html_body, attachments=None, cfg_override=cfg_override)




def get_current_user():
    """Get current logged in user"""
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])



def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = get_current_user()
        if not user or not getattr(user, "is_admin", False):
             flash("Yönetici yetkisi gerekiyor.", "danger")
             return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function

def planner_or_admin_required(f):
    from functools import wraps
    from flask import request, jsonify
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or (request.accept_mimetypes.best and "application/json" in str(request.accept_mimetypes)):
                return jsonify({"ok": False, "error": "auth", "message": "Oturum açmanız gerekiyor."}), 401
            return redirect(url_for('auth.login'))
        user = get_current_user()
        if not user:
            if request.is_json or (request.accept_mimetypes.best and "application/json" in str(request.accept_mimetypes)):
                return jsonify({"ok": False, "error": "auth", "message": "Oturum açmanız gerekiyor."}), 401
            return redirect(url_for('auth.login'))
        role = (user.role or "").strip().lower()
        if not (getattr(user, "is_admin", False) or role in ("planner", "planlayici", "planlayıcı")):
            if request.is_json or (request.headers.get("Content-Type") or "").startswith("application/json") or (request.accept_mimetypes.best and "application/json" in str(request.accept_mimetypes)):
                return jsonify({"ok": False, "error": "forbidden", "message": "Bu işlem için planlayıcı yetkisi gereklidir."}), 403
            flash("Planlayıcı yetkisi gerekiyor.", "danger")
            return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function

def kivanc_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = get_current_user()
        # kivanc check
        is_kivanc = user and (user.username == "kivanc" or user.email == "kivancozcan@netmon.com.tr")
        if not is_kivanc:
             flash("Bu alan sadece yönetici (Kıvanç) erişimine açıktır.", "danger")
             return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function

def observer_required(f):
    """Decorator to allow observer role - can only view, cannot modify"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        current_user = get_current_user()
        if not current_user:
            flash("Oturum açmanız gerekiyor.", "danger")
            return redirect(url_for('auth.login'))
        # Gözlemci rolü sadece görüntüleme yapabilir, değişiklik yapamaz
        if current_user.role == 'gözlemci':
            # POST isteklerini engelle (değişiklik yapma)
            if request.method == 'POST':
                flash("Gözlemci rolü değişiklik yapamaz. Sadece görüntüleme yetkiniz var.", "danger")
                return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function





def _is_user_online(user_obj, *, now=None):
    if not user_obj:
        return False
    now = now or datetime.now()
    cutoff = now - ONLINE_WINDOW
    last_seen = getattr(user_obj, "last_seen", None)
    return bool(last_seen and last_seen >= cutoff)


def _fetch_announcements(user, limit=5):
    if not user:
        return []
    clauses = [Announcement.audience_type == "all"]
    if user.team_id:
        clauses.append(and_(Announcement.audience_type == "team", Announcement.audience_id == user.team_id))
    clauses.append(and_(Announcement.audience_type == "user", Announcement.audience_id == user.id))
    q = Announcement.query.filter(or_(*clauses)).order_by(Announcement.created_at.desc())
    rows = q.limit(limit).all()
    out = []
    for a in rows:
        is_read = AnnouncementRead.query.filter_by(announcement_id=a.id, user_id=user.id).count() > 0
        out.append({"id": a.id, "title": a.title, "body": a.body, "created_at": a.created_at.strftime("%d.%m.%Y %H:%M"), "is_read": is_read})
    return out


def _fetch_popup_announcement(user):
    if not user:
        return None
    try:
        clauses = [Announcement.audience_type.in_(["", "all"])]
        if user.team_id:
            clauses.append(and_(Announcement.audience_type == "team", Announcement.audience_id == user.team_id))
        clauses.append(and_(Announcement.audience_type == "user", Announcement.audience_id == user.id))
        q = (
            Announcement.query
            .filter(or_(*clauses), Announcement.is_popup == True)
            .order_by(Announcement.created_at.desc())
        )
        a = q.first()
        if not a:
            return None
        is_read = AnnouncementRead.query.filter_by(announcement_id=a.id, user_id=user.id).count() > 0
        if is_read:
            return None
        created_at = a.created_at.strftime("%d.%m.%Y %H:%M") if a.created_at else ""
        return {"id": a.id, "title": a.title, "body": a.body, "created_at": created_at}
    except Exception:
        return None


def _cell_has_meaningful_job(cell: "PlanCell") -> bool:
    if not cell:
        return False
    if (cell.shift or "").strip():
        return True
    if (cell.vehicle_info or "").strip():
        return True
    if (cell.note or "").strip():
        return True
    if (getattr(cell, "important_note", None) or "").strip():
        return True
    if (getattr(cell, "job_mail_body", None) or "").strip():
        return True
    if (getattr(cell, "isdp_info", None) or "").strip():
        return True
    if (getattr(cell, "po_info", None) or "").strip():
        return True
    if _parse_files(getattr(cell, "lld_hhd_files", None)) or _parse_files(getattr(cell, "tutanak_files", None)):
        return True
    if getattr(cell, "lld_hhd_path", None) or getattr(cell, "tutanak_path", None):
        return True
    try:
        if cell.assignments and len(cell.assignments) > 0:
            return True
    except Exception:
        pass
    return False

def _effective_team_name_for_cell(cell: "PlanCell") -> str:
    if not cell:
        return ""
    if (cell.team_name or "").strip():
        return (cell.team_name or "").strip()
    try:
        if cell.team_id:
            t = Team.query.get(cell.team_id)
            if t and (t.name or "").strip():
                return (t.name or "").strip()
    except Exception:
        pass
    return ""

def _sync_job_from_cell(job: "Job", cell: "PlanCell"):
    if not job or not cell:
        return
    job.project_id = cell.project_id
    job.subproject_id = getattr(cell, "subproject_id", None) or None
    job.work_date = cell.work_date
    job.team_id = cell.team_id or None
    job.team_name = _effective_team_name_for_cell(cell) or None
    job.assigned_user_id = getattr(cell, "assigned_user_id", None) or None
    job.shift = cell.shift or None
    job.vehicle_info = cell.vehicle_info or None
    job.note = cell.note or None

    _promote_job_kanban_status(job, "PLANNED", changed_by_user_id=None, note="planning_sync")
    if getattr(job, "assigned_user_id", None):
        _promote_job_kanban_status(job, "ASSIGNED", changed_by_user_id=None, note="assignment_sync")

    person_ids = []
    try:
        person_ids = [a.person_id for a in (cell.assignments or []) if a and a.person_id]
    except Exception:
        person_ids = []
    person_ids = sorted({int(x) for x in person_ids})
    JobAssignment.query.filter_by(job_id=job.id).delete()
    for pid in person_ids:
        db.session.add(JobAssignment(job_id=job.id, person_id=pid))

def _is_sqlite_db() -> bool:
    try:
        return str(db.engine.url).startswith("sqlite")
    except Exception:
        return False


def _ensure_job_for_cell(cell: "PlanCell") -> Optional["Job"]:
    if not cell:
        return None
    job = Job.query.filter_by(cell_id=cell.id).first()
    if job:
        return job

    if _is_sqlite_db():
        try:
            stmt = insert(Job.__table__).values(
                cell_id=cell.id,
                project_id=cell.project_id,
                work_date=cell.work_date,
            ).prefix_with("OR IGNORE")
            db.session.execute(stmt)
            db.session.flush()
            job = Job.query.filter_by(cell_id=cell.id).first()
            if job:
                return job
        except IntegrityError:
            try:
                db.session.rollback()
            except Exception:
                pass
            return Job.query.filter_by(cell_id=cell.id).first()

    job = Job(cell_id=cell.id, project_id=cell.project_id, work_date=cell.work_date)
    db.session.add(job)
    db.session.flush()
    return job


def _publish_cell(cell: "PlanCell", *, publisher: "User", now: Optional[datetime] = None) -> Optional["Job"]:
    if not cell:
        return None
    now = now or datetime.now()
    publisher_id = getattr(publisher, "id", None) if publisher else None

    job = _ensure_job_for_cell(cell)
    if not job:
        return None

    _sync_job_from_cell(job, cell)
    job.is_published = True
    job.published_at = now
    job.published_by_user_id = publisher_id
    _promote_job_kanban_status(job, "PUBLISHED", changed_by_user_id=publisher_id, note="publish")
    db.session.add(job)
    return job

def upsert_jobs_for_range(start: date, end: date):
    """
    Backfill/sync Job + JobAssignment from PlanCell for given range (idempotent).
    Keeps Job.status in sync with latest JobFeedback if present.
    """
    if not start or not end or start > end:
        return

    cells = PlanCell.query.filter(PlanCell.work_date >= start, PlanCell.work_date <= end).all()
    cell_ids = [c.id for c in cells]

    # Eğer bu tarih aralığında hiç hücre yoksa, yayınlanmamış tüm işleri temizle
    if not cells:
        jobs_to_delete = Job.query.filter(
            Job.work_date >= start,
            Job.work_date <= end,
            db.or_(Job.is_published == False, Job.is_published == None),
        ).all()
        if jobs_to_delete:
            for j in jobs_to_delete:
                JobAssignment.query.filter_by(job_id=j.id).delete()
                JobFeedback.query.filter_by(job_id=j.id).delete()
                db.session.delete(j)
            db.session.commit()
        return

    existing_jobs = Job.query.filter(Job.cell_id.in_(cell_ids)).all()
    job_by_cell = {j.cell_id: j for j in existing_jobs}

    # Hücresi kalmamış ama iş tablosunda duran yayınlanmamış kayıtları temizle
    dangling_jobs = (
        Job.query.filter(
            Job.work_date >= start,
            Job.work_date <= end,
            db.or_(Job.cell_id == None, ~Job.cell_id.in_(cell_ids)),  # noqa: E711
            db.or_(Job.is_published == False, Job.is_published == None),  # noqa: E712
        ).all()
    )
    if dangling_jobs:
        for j in dangling_jobs:
            JobAssignment.query.filter_by(job_id=j.id).delete()
            JobFeedback.query.filter_by(job_id=j.id).delete()
            db.session.delete(j)
        db.session.commit()

    # feedback latest per job
    feedback_rows = (
        db.session.query(JobFeedback.job_id, db.func.max(JobFeedback.closed_at))
        .join(Job, Job.id == JobFeedback.job_id)
        .filter(Job.cell_id.in_(cell_ids))
        .group_by(JobFeedback.job_id)
        .all()
    )
    latest_feedback_at_by_job = {jid: dt for (jid, dt) in feedback_rows if jid and dt}
    latest_feedback_by_job = {}
    if latest_feedback_at_by_job:
        jids = list(latest_feedback_at_by_job.keys())
        rows = JobFeedback.query.filter(JobFeedback.job_id.in_(jids)).all()
        for r in rows:
            if latest_feedback_at_by_job.get(r.job_id) == r.closed_at:
                latest_feedback_by_job[r.job_id] = r

    for cell in cells:
        has_job = _cell_has_meaningful_job(cell)
        job = job_by_cell.get(cell.id)
        if not has_job:
            if job:
                JobAssignment.query.filter_by(job_id=job.id).delete()
                JobFeedback.query.filter_by(job_id=job.id).delete()
                db.session.delete(job)
            continue

        if not job:
            job = _ensure_job_for_cell(cell)
            if not job:
                continue
            job_by_cell[cell.id] = job
            _promote_job_kanban_status(job, "PLANNED", note="planning_create")

        if not bool(getattr(job, "is_published", False)):
            job.project_id = cell.project_id
            job.subproject_id = getattr(cell, "subproject_id", None) or None
            job.work_date = cell.work_date
            job.team_id = cell.team_id or None
            job.team_name = _effective_team_name_for_cell(cell) or None
            job.assigned_user_id = getattr(cell, "assigned_user_id", None) or None
            job.shift = cell.shift or None
            job.vehicle_info = cell.vehicle_info or None
            job.note = cell.note or None
            if job.assigned_user_id:
                _promote_job_kanban_status(job, "ASSIGNED", note="assignment_sync")

            # Sync assignments
            person_ids = []
            try:
                person_ids = [a.person_id for a in (cell.assignments or []) if a and a.person_id]
            except Exception:
                person_ids = []
            person_ids = sorted({int(x) for x in person_ids})
            JobAssignment.query.filter_by(job_id=job.id).delete()
            for pid in person_ids:
                db.session.add(JobAssignment(job_id=job.id, person_id=pid))
        else:
            # Yayınlanmış işte de atanan kişi her zaman hücreyle senkronize edilsin (Benim İşlerim'de görünsün)
            job.assigned_user_id = getattr(cell, "assigned_user_id", None) or None
            if job.assigned_user_id:
                _promote_job_kanban_status(job, "ASSIGNED", note="assignment_sync")

        # Status from latest feedback
        fb = latest_feedback_by_job.get(job.id)
        if fb:
            job.status = fb.status or "completed"
            job.closed_at = fb.closed_at
        else:
            job.status = "pending"
            job.closed_at = None

    db.session.commit()


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


def _create_sqlite_backup_file(dest_path: str) -> bool:
    """SQLite veritabanını tam olarak yedekler (tüm tablolar, indexler, veriler)"""
    src = _sqlite_db_path()
    if not src or not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        import sqlite3 as _sqlite3
        src_conn = _sqlite3.connect(src)
        try:
            # Kaynak veritabanı bilgilerini al (doğrulama için)
            src_tables = src_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            src_table_count = len(src_tables)
            
            dst_conn = _sqlite3.connect(dest_path)
            try:
                # SQLite'ın native backup metodu - TÜM verileri kopyalar (tablolar, indexler, triggerlar, viewlar, metadata)
                src_conn.backup(dst_conn)
                dst_conn.commit()
                
                # Doğrulama: Hedef veritabanında aynı tablolar var mı?
                dst_tables = dst_conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                dst_table_count = len(dst_tables)
                
                if dst_table_count != src_table_count:
                    # Tablo sayısı eşleşmiyorsa, dosya kopyalama yöntemini dene
                    dst_conn.close()
                    try:
                        os.remove(dest_path)
                    except:
                        pass
                    shutil.copy2(src, dest_path)
                    return True
                
            finally:
                try:
                    dst_conn.close()
                except Exception:
                    pass
        finally:
            try:
                src_conn.close()
            except Exception:
                pass
        return True
    except Exception as e:
        # Backup başarısız olursa, dosyayı direkt kopyala (byte-byte kopyalama - tamamen aynı dosya)
        log.warning(f"SQLite backup failed (native), trying shutil copy. Error: {e}")
        try:
            shutil.copy2(src, dest_path)
            return True
        except Exception as e2:
            log.error(f"SQLite backup completely failed: {e2}")
            return False


# ============== SABİT MAİL ŞABLONLARI ==============
# Mail şablon sistemi kaldırıldı, bunun yerine sabit HTML şablonları kullanılıyor.

def _get_priority_color(priority_label: str) -> str:
    """Öncelik seviyesine göre renk döndür"""
    colors = {
        "Kritik": "#dc2626",
        "Yüksek": "#f97316", 
        "Orta": "#eab308",
        "Düşük": "#22c55e",
        "Çok Düşük": "#64748b",
        "1": "#dc2626",
        "2": "#f97316",
        "3": "#eab308",
        "4": "#22c55e",
        "5": "#64748b",
    }
    return colors.get(str(priority_label), "#64748b")


def _get_status_color(status: str) -> str:
    """Durum için renk döndür"""
    colors = {
        "İlk Giriş": "#3b82f6",
        "Devam Ediyor": "#f59e0b", 
        "Beklemede": "#8b5cf6",
        "İş Halledildi": "#22c55e",
        "Reddedildi": "#ef4444",
        "İptal": "#ef4444",
        "Hatalı Giriş": "#ef4444",
    }
    return colors.get(status, "#64748b")


def _get_priority_label(priority: int) -> str:
    """Öncelik numarasını etikete çevir"""
    labels = {1: "Kritik", 2: "Yüksek", 3: "Orta", 4: "Düşük", 5: "Çok Düşük"}
    return labels.get(priority, "Orta")


def render_email_base(
    subject: str,
    header_title: str,
    header_subtitle: str,
    recipient_name: str,
    action_message: str,
    main_content: str = "",
    action_button: str = "",
    action_by: str = "Sistem",
) -> Tuple[str, str]:
    """
    Tüm mailler için tek bir wrapper fonksiyonu.
    Returns: (subject, html_body)
    """
    system_name = "Netmon Proje Takip"
    company_name = "Netmon"
    
    html = f'''<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <!--[if mso]>
  <style type="text/css">body, table, td {{font-family: Arial, sans-serif !important;}}</style>
  <![endif]-->
</head>
<body style="margin:0; padding:0; background-color:#f0f4f8; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  
  <!-- Header Banner -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);">
    <tr>
      <td style="padding: 24px 0; text-align: center;">
        <h1 style="color: #ffffff; margin: 0; font-size: 26px; font-weight: 700;">{header_title}</h1>
        <p style="color: rgba(255,255,255,0.85); margin: 10px 0 0 0; font-size: 14px;">{header_subtitle}</p>
      </td>
    </tr>
  </table>

  <!-- Main Content -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr>
      <td style="padding: 28px 16px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
          
          <!-- Personal Greeting -->
          <tr>
            <td style="padding: 28px 28px 16px 28px;">
              <p style="margin: 0; font-size: 16px; color: #1e3a5f;">
                Merhaba <strong style="color: #1e40af;">{recipient_name}</strong>,
              </p>
            </td>
          </tr>

          <!-- Action Message -->
          <tr>
            <td style="padding: 0 28px;">
              <div style="background-color: #f0f9ff; border-left: 4px solid #3b82f6; padding: 16px 20px; border-radius: 0 10px 10px 0;">
                <p style="margin: 0; font-size: 15px; color: #1e40af; line-height: 1.5;">{action_message}</p>
              </div>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 24px 28px;">{main_content}</td>
          </tr>

          <!-- Action Button -->
          {action_button}

          <!-- Footer Info -->
          <tr>
            <td style="padding: 20px 28px; background-color: #f8fafc; border-top: 1px solid #e2e8f0; border-radius: 0 0 12px 12px;">
              <p style="margin: 0 0 6px 0; font-size: 12px; color: #64748b;">
                📧 Bu mail <strong>{system_name}</strong> tarafından otomatik olarak gönderilmiştir.
              </p>
              <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                👤 İşlemi gerçekleştiren: <strong>{action_by}</strong>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- Footer -->
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr>
      <td style="padding: 24px; text-align: center;">
        <p style="margin: 0; font-size: 12px; color: #94a3b8;">{company_name}</p>
      </td>
    </tr>
  </table>
</body>
</html>'''

    return subject, html


def render_task_created_email(
    task_no: str,
    task_subject: str,
    task_type: str,
    priority: int,
    target_date: Optional[str],
    description: Optional[str],
    project_codes: Optional[str],
    recipient_name: str,
    created_by_name: str,
    task_url: str = "#"
) -> Tuple[str, str]:
    """Yeni görev oluşturulduğunda gönderilen mail"""
    
    priority_label = _get_priority_label(priority)
    priority_color = _get_priority_color(priority_label)
    
    subject = f"📋 Yeni Görev Atandı: {task_no} - {task_subject}"
    
    # Detay Grid
    details_grid = f'''
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 16px;">
      <tr>
        <td style="padding: 8px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 48%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">📌 Görev No</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{task_no}</div>
              </td>
              <td style="width: 4%;"></td>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 48%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">📁 Tip</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{task_type}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding: 8px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 48%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">⚡ Öncelik</div>
                <div style="font-size: 14px; font-weight: 600;">
                  <span style="background: {priority_color}; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-size: 12px;">{priority_label}</span>
                </div>
              </td>
              <td style="width: 4%;"></td>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 48%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">📅 Hedef Tarih</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{target_date or 'Belirtilmemiş'}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    '''
    
    # Açıklama
    description_html = ""
    if description:
        desc_escaped = description.replace('\n', '<br>')
        description_html = f'''
        <div style="background-color: #fffbeb; border: 1px solid #fcd34d; padding: 16px; border-radius: 8px; margin-top: 16px;">
          <div style="font-size: 12px; color: #92400e; font-weight: 600; margin-bottom: 8px;">📝 Açıklama</div>
          <div style="font-size: 14px; color: #451a03; line-height: 1.6;">{desc_escaped}</div>
        </div>
        '''
    
    # Proje Bilgisi
    project_html = ""
    if project_codes:
        project_html = f'''
        <div style="background: #f0fdf4; border: 1px solid #86efac; padding: 12px 16px; border-radius: 8px; margin-top: 12px;">
          <span style="font-size: 12px; color: #166534;">🏢 Proje: <strong>{project_codes}</strong></span>
        </div>
        '''
    
    # Buton
    action_button = f'''
    <tr>
      <td style="padding: 24px 28px; text-align: center;">
        <a href="{task_url}" 
           style="display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: #ffffff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
          👁 Görevi Görüntüle
        </a>
      </td>
    </tr>
    '''
    
    main_content = details_grid + project_html + description_html
    
    return render_email_base(
        subject=subject,
        header_title="📋 Yeni Görev Atandı",
        header_subtitle=f"Görev No: {task_no}",
        recipient_name=recipient_name,
        action_message="Size yeni bir görev atandı. Görevi inceleyip gerekli aksiyonları alabilirsiniz.",
        main_content=main_content,
        action_button=action_button,
        action_by=created_by_name,
    )


def render_task_status_changed_email(
    task_no: str,
    task_subject: str,
    old_status: str,
    new_status: str,
    recipient_name: str,
    changed_by_name: str,
    comment: Optional[str] = None,
    task_url: str = "#"
) -> Tuple[str, str]:
    """Görev durumu değiştiğinde gönderilen mail"""
    
    status_color = _get_status_color(new_status)
    subject = f"🔄 Görev Durumu Güncellendi: {task_no}"
    
    # Durum Değişimi
    status_change_html = f'''
    <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 16px;">
      <div style="font-size: 12px; color: #92400e; margin-bottom: 8px;">Eski Durum</div>
      <div style="font-size: 16px; font-weight: 700; color: #78350f; margin-bottom: 12px;">{old_status}</div>
      <div style="font-size: 20px; color: #92400e; margin-bottom: 12px;">⬇️</div>
      <div style="font-size: 12px; color: #166534; margin-bottom: 8px;">Yeni Durum</div>
      <div style="font-size: 16px; font-weight: 700; color: #166534;">
        <span style="background: {status_color}; color: #ffffff; padding: 6px 16px; border-radius: 6px;">{new_status}</span>
      </div>
    </div>
    '''
    
    # Yorum varsa
    comment_html = ""
    if comment:
        comment_html = f'''
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 8px; margin-top: 16px;">
          <div style="font-size: 12px; color: #64748b; margin-bottom: 8px;">💬 {changed_by_name} yazdı:</div>
          <div style="font-size: 14px; color: #1e293b; line-height: 1.5; font-style: italic;">"{comment}"</div>
        </div>
        '''
    
    action_button = f'''
    <tr>
      <td style="padding: 24px 28px; text-align: center;">
        <a href="{task_url}" 
           style="display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: #ffffff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
          👁 Görevi Görüntüle
        </a>
      </td>
    </tr>
    '''
    
    return render_email_base(
        subject=subject,
        header_title="🔄 Durum Güncellemesi",
        header_subtitle=f"Görev: {task_no} - {task_subject}",
        recipient_name=recipient_name,
        action_message=f"Görevin durumu <strong>{old_status}</strong> → <strong>{new_status}</strong> olarak güncellendi.",
        main_content=status_change_html + comment_html,
        action_button=action_button,
        action_by=changed_by_name,
    )


def render_task_comment_email(
    task_no: str,
    task_subject: str,
    comment_text: str,
    comment_by_name: str,
    recipient_name: str,
    comment_date: str = "",
    task_url: str = "#"
) -> Tuple[str, str]:
    """Göreve yorum eklendiğinde gönderilen mail"""
    
    subject = f"💬 Yeni Yorum: {task_no}"
    
    comment_html = f'''
    <div style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-left: 4px solid #3b82f6; padding: 20px; border-radius: 0 12px 12px 0;">
      <div style="font-size: 12px; color: #1e40af; margin-bottom: 8px;">
        <span style="background: rgba(255,255,255,0.5); padding: 4px 10px; border-radius: 4px;">💬 {comment_by_name}</span>
        {f'<span style="color: #64748b; margin-left: 8px;">{comment_date}</span>' if comment_date else ''}
      </div>
      <div style="font-size: 15px; color: #1e3a8a; line-height: 1.6; font-style: italic;">
        "{comment_text}"
      </div>
    </div>
    '''
    
    action_button = f'''
    <tr>
      <td style="padding: 24px 28px; text-align: center;">
        <a href="{task_url}" 
           style="display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: #ffffff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
          👁 Görevi Görüntüle
        </a>
      </td>
    </tr>
    '''
    
    return render_email_base(
        subject=subject,
        header_title="💬 Yeni Yorum Eklendi",
        header_subtitle=f"Görev: {task_no}",
        recipient_name=recipient_name,
        action_message=f"{comment_by_name} görevinize yeni bir yorum ekledi.",
        main_content=comment_html,
        action_button=action_button,
        action_by=comment_by_name,
    )


def render_task_reminder_email(
    task_no: str,
    task_subject: str,
    target_date: str,
    days_left: int,
    recipient_name: str,
    task_url: str = "#"
) -> Tuple[str, str]:
    """Görev hatırlatma maili"""
    
    urgency_color = "#ef4444" if days_left <= 1 else "#f59e0b" if days_left <= 3 else "#22c55e"
    subject = f"⏰ Hatırlatma: {task_no} - {days_left} gün kaldı"
    
    reminder_html = f'''
    <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); padding: 24px; border-radius: 12px; text-align: center;">
      <div style="font-size: 48px; margin-bottom: 12px;">⏰</div>
      <div style="font-size: 18px; font-weight: 700; color: {urgency_color}; margin-bottom: 8px;">
        Hedef Tarihe {days_left} Gün Kaldı!
      </div>
      <div style="font-size: 14px; color: #7f1d1d;">
        Görevinizi tamamlamak için acele edin.
      </div>
      <div style="margin-top: 16px; padding: 12px; background: white; border-radius: 8px;">
        <div style="font-size: 12px; color: #64748b;">Hedef Tarih</div>
        <div style="font-size: 16px; font-weight: 600; color: #1e293b;">{target_date}</div>
      </div>
    </div>
    '''
    
    action_button = f'''
    <tr>
      <td style="padding: 24px 28px; text-align: center;">
        <a href="{task_url}" 
           style="display: inline-block; background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%); color: #ffffff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
          🚀 Göreve Git
        </a>
      </td>
    </tr>
    '''
    
    return render_email_base(
        subject=subject,
        header_title="⏰ Görev Hatırlatması",
        header_subtitle=f"{task_no} - {task_subject}",
        recipient_name=recipient_name,
        action_message="Görevinizin hedef tarihi yaklaşıyor. Lütfen görevi gözden geçirin.",
        main_content=reminder_html,
        action_button=action_button,
        action_by="Sistem",
    )


def render_task_deadline_expired_email(
    task_no: str,
    task_subject: str,
    target_date: str,
    days_overdue: int,
    recipient_name: str,
    task_url: str = "#"
) -> Tuple[str, str]:
    """Görev süresi dolduğunda gönderilen mail"""
    
    subject = f"⚠️ Süre Doldu: {task_no} - {days_overdue} gün geçti"
    
    expired_html = f'''
    <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); padding: 24px; border-radius: 12px; text-align: center; border: 2px solid #fca5a5;">
      <div style="font-size: 48px; margin-bottom: 12px;">⚠️</div>
      <div style="font-size: 18px; font-weight: 700; color: #dc2626; margin-bottom: 8px;">
        Görev Süresi Doldu!
      </div>
      <div style="font-size: 14px; color: #7f1d1d; margin-bottom: 16px;">
        Hedef tarih <strong>{days_overdue}</strong> gün önce geçti.
      </div>
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td style="padding: 12px; background: white; border-radius: 8px; width: 48%;">
            <div style="font-size: 12px; color: #64748b;">Hedef Tarih</div>
            <div style="font-size: 14px; font-weight: 600; color: #dc2626;">{target_date}</div>
          </td>
          <td style="width: 4%;"></td>
          <td style="padding: 12px; background: white; border-radius: 8px; width: 48%;">
            <div style="font-size: 12px; color: #64748b;">Geciken Gün</div>
            <div style="font-size: 14px; font-weight: 600; color: #dc2626;">{days_overdue} gün</div>
          </td>
        </tr>
      </table>
    </div>
    '''
    
    action_button = f'''
    <tr>
      <td style="padding: 24px 28px; text-align: center;">
        <a href="{task_url}" 
           style="display: inline-block; background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%); color: #ffffff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px;">
          🚨 Görevi İncele
        </a>
      </td>
    </tr>
    '''
    
    return render_email_base(
        subject=subject,
        header_title="⚠️ Görev Süresi Doldu",
        header_subtitle=f"{task_no} - {task_subject}",
        recipient_name=recipient_name,
        action_message=f"Aşağıdaki görevin süresi dolmuştur. Lütfen durumu güncelleyin.",
        main_content=expired_html,
        action_button=action_button,
        action_by="Sistem",
    )


def render_weekly_plan_email(
    person_name: str,
    week_start: str,
    week_end: str,
    table_html: str = "",
    total_jobs: int = 0,
    action_by: str = "Sistem"
) -> Tuple[str, str]:
    """Haftalık plan maili"""
    
    subject = f"📅 Haftalık Planınız - {week_start} / {week_end}"
    
    summary_html = f'''
    <div style="background: #f0fdf4; border: 1px solid #86efac; padding: 16px; border-radius: 8px; margin-bottom: 16px; text-align: center;">
      <div style="font-size: 24px; font-weight: 700; color: #166534;">{total_jobs}</div>
      <div style="font-size: 14px; color: #166534;">Toplam İş</div>
    </div>
    '''
    
    content = summary_html
    if table_html:
        content += f'''
        <div style="overflow-x: auto; margin-top: 16px;">
          {table_html}
        </div>
        '''
    
    return render_email_base(
        subject=subject,
        header_title="📅 Haftalık İş Planınız",
        header_subtitle=f"{week_start} - {week_end}",
        recipient_name=person_name,
        action_message="Haftalık iş planınız aşağıda sunulmuştur. Planınızı inceleyip hazırlıklarınızı yapabilirsiniz.",
        main_content=content,
        action_by=action_by,
    )


def render_team_report_email(
    team_name: str,
    date_range: str,
    total_jobs: int,
    completed_jobs: int,
    pending_jobs: int,
    recipient_name: str,
    table_html: str = "",
    action_by: str = "Sistem"
) -> Tuple[str, str]:
    """Ekip raporu maili"""
    
    subject = f"👥 Ekip Raporu - {team_name} - {date_range}"
    
    summary_html = f'''
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 16px;">
      <tr>
        <td style="background: #f0fdf4; padding: 16px; border-radius: 8px; text-align: center; width: 30%;">
          <div style="font-size: 24px; font-weight: 700; color: #166534;">{total_jobs}</div>
          <div style="font-size: 12px; color: #166534;">Toplam İş</div>
        </td>
        <td style="width: 5%;"></td>
        <td style="background: #eff6ff; padding: 16px; border-radius: 8px; text-align: center; width: 30%;">
          <div style="font-size: 24px; font-weight: 700; color: #1e40af;">{completed_jobs}</div>
          <div style="font-size: 12px; color: #1e40af;">Tamamlanan</div>
        </td>
        <td style="width: 5%;"></td>
        <td style="background: #fef3c7; padding: 16px; border-radius: 8px; text-align: center; width: 30%;">
          <div style="font-size: 24px; font-weight: 700; color: #92400e;">{pending_jobs}</div>
          <div style="font-size: 12px; color: #92400e;">Bekleyen</div>
        </td>
      </tr>
    </table>
    '''
    
    content = summary_html
    if table_html:
        content += f'''
        <div style="overflow-x: auto; margin-top: 16px;">
          {table_html}
        </div>
        '''
    
    return render_email_base(
        subject=subject,
        header_title="👥 Ekip Raporu",
        header_subtitle=f"{team_name}",
        recipient_name=recipient_name,
        action_message=f"{date_range} dönemine ait ekip raporu aşağıdadır.",
        main_content=content,
        action_by=action_by,
    )


def render_job_assignment_email(
    project_name: str,
    project_code: str,
    work_date: str,
    team_name: str,
    shift: str,
    recipient_name: str,
    job_details: str = "",
    people_list: List[dict] = None,
    action_by: str = "Sistem"
) -> Tuple[str, str]:
    """İş atama maili"""
    
    subject = f"🔧 İş Atandı: {project_code} - {work_date}"
    
    details_html = f'''
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-bottom: 16px;">
      <tr>
        <td style="padding: 8px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 48%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">📁 Proje</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{project_name}</div>
              </td>
              <td style="width: 4%;"></td>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 48%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">📅 Tarih</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{work_date}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding: 8px 0;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 48%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">👥 Ekip</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{team_name}</div>
              </td>
              <td style="width: 4%;"></td>
              <td style="background: #f8fafc; padding: 12px 16px; border-radius: 8px; width: 48%;">
                <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">⏰ Vardiya</div>
                <div style="font-size: 14px; font-weight: 600; color: #1e3a5f;">{shift or 'Belirtilmemiş'}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    '''
    
    if job_details:
        details_html += f'''
        <div style="background: #fffbeb; border: 1px solid #fcd34d; padding: 16px; border-radius: 8px; margin-top: 16px;">
          <div style="font-size: 12px; color: #92400e; font-weight: 600; margin-bottom: 8px;">📝 İş Detayları</div>
          <div style="font-size: 14px; color: #451a03; line-height: 1.6;">{job_details.replace(chr(10), '<br>')}</div>
        </div>
        '''
    
    if people_list:
        people_rows = ""
        for p in people_list:
            people_rows += f'''<tr><td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{p.get("full_name", "")}</td><td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{p.get("phone", "")}</td></tr>'''
        
        details_html += f'''
        <div style="margin-top: 16px;">
          <div style="font-size: 12px; color: #64748b; font-weight: 600; margin-bottom: 8px;">👥 Ekip Üyeleri</div>
          <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
            <thead>
              <tr style="background: #1e3a5f; color: white;">
                <th style="padding: 10px; text-align: left;">Ad Soyad</th>
                <th style="padding: 10px; text-align: left;">Telefon</th>
              </tr>
            </thead>
            <tbody>{people_rows}</tbody>
          </table>
        </div>
        '''
    
    return render_email_base(
        subject=subject,
        header_title="🔧 Yeni İş Ataması",
        header_subtitle=f"{project_code} - {project_name}",
        recipient_name=recipient_name,
        action_message="Size yeni bir iş atanmıştır. Detaylar aşağıdadır.",
        main_content=details_html,
        action_by=action_by,
    )


def render_test_email(
    recipient_name: str = "Test Kullanıcı",
    sender_name: str = "Sistem",
    test_date: str = ""
) -> Tuple[str, str]:
    """Test maili"""
    
    if not test_date:
        test_date = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    subject = "[TEST] Mail Sistemi Testi"
    
    test_html = f'''
    <div style="background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%); padding: 24px; border-radius: 12px; text-align: center;">
      <div style="font-size: 48px; margin-bottom: 12px;">✅</div>
      <div style="font-size: 18px; font-weight: 700; color: #1e40af; margin-bottom: 8px;">
        Mail Sistemi Çalışıyor!
      </div>
      <div style="font-size: 14px; color: #3b82f6;">
        Bu bir test mailidir. Mail sisteminiz düzgün çalışıyor.
      </div>
      <div style="margin-top: 16px; padding: 12px; background: white; border-radius: 8px;">
        <div style="font-size: 12px; color: #64748b;">Test Tarihi</div>
        <div style="font-size: 14px; font-weight: 600; color: #1e293b;">{test_date}</div>
      </div>
    </div>
    '''
    
    return render_email_base(
        subject=subject,
        header_title="🧪 Test Maili",
        header_subtitle="Mail Sistemi Kontrolü",
        recipient_name=recipient_name,
        action_message="Bu bir test mailidir. Mail sisteminiz başarıyla çalışıyor!",
        main_content=test_html,
        action_by=sender_name,
    )
