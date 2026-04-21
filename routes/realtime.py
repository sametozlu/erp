"""
Gerçek Zamanlı Özellikler API'leri
- WebSocket senkronizasyonu
- Hücre kilitleme
- Tarih taşıma
- İptal mekanizması
- Mesai giriş sistemi
- Ses mesajları
- Kullanıcı ayarları
- Tablo mail gönderimi
- Tam ekran modu
"""

from flask import Blueprint, request, jsonify, render_template, session, current_app
from extensions import db, socketio
from werkzeug.utils import secure_filename
from flask_socketio import emit, join_room, leave_room
from models import (
    PlanCell, CellAssignment, CellLock, CellCancellation, CellVersion,
    TeamOvertime, VoiceMessage, UserSettings, TableSnapshot,
    User, Team, Person, Project, SubProject, Job
)
from utils import login_required, get_current_user, planner_or_admin_required, _csrf_verify, _sync_job_from_cell
from datetime import datetime, timedelta
import json
import os
import base64
import uuid
from services.mail_service import MailService

realtime_bp = Blueprint('realtime', __name__)

# ============== HÜCRE KİLİTLEME (CELL LOCKING) ==============

@realtime_bp.post("/api/cell/lock")
@login_required
def api_cell_lock():
    """Hücreyi kilitle - düzenleme başladığında çağırılır"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    project_id = int(data.get("project_id") or 0)
    work_date_str = (data.get("work_date") or "").strip()
    
    if not project_id or not work_date_str:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    
    try:
        work_date = datetime.strptime(work_date_str, "%Y-%m-%d").date()
    except:
        return jsonify({"ok": False, "error": "invalid_date"}), 400
    
    # Hücreyi bul veya oluştur
    cell = PlanCell.query.filter_by(project_id=project_id, work_date=work_date).first()
    if not cell:
        cell = PlanCell(project_id=project_id, work_date=work_date)
        db.session.add(cell)
        db.session.commit()
    
    now = datetime.now()
    expires_at = now + timedelta(seconds=60)  # 60 saniye kilit süresi
    
    # Mevcut kilidi kontrol et
    existing_lock = CellLock.query.filter_by(cell_id=cell.id).first()
    
    if existing_lock:
        # Kilit süresi dolmuş mu?
        if existing_lock.expires_at < now:
            # Süresi dolmuş, yeni kilit oluştur
            existing_lock.user_id = user.id
            existing_lock.locked_at = now
            existing_lock.expires_at = expires_at
            db.session.commit()
        elif existing_lock.user_id != user.id:
            # Başka kullanıcı tarafından kilitli
            lock_user = User.query.get(existing_lock.user_id)
            lock_user_name = (lock_user.full_name or lock_user.email or lock_user.username or "") if lock_user else "Bilinmeyen"
            return jsonify({
                "ok": False,
                "error": "locked",
                "locked_by": lock_user_name,
                "locked_by_id": existing_lock.user_id,
                "expires_at": existing_lock.expires_at.isoformat()
            }), 409
        else:
            # Aynı kullanıcı, süreyi uzat
            existing_lock.expires_at = expires_at
            db.session.commit()
    else:
        # Yeni kilit oluştur
        new_lock = CellLock(
            cell_id=cell.id,
            user_id=user.id,
            locked_at=now,
            expires_at=expires_at
        )
        db.session.add(new_lock)
        db.session.commit()
    
    # Diğer kullanıcılara bildir
    try:
        socketio.emit("cell_locked", {
            "project_id": project_id,
            "work_date": work_date_str,
            "cell_id": cell.id,
            "locked_by": user.full_name or user.email or user.username,
            "locked_by_id": user.id,
            "expires_at": expires_at.isoformat()
        }, room="plan_updates", namespace="/")
    except:
        pass
    
    return jsonify({
        "ok": True,
        "cell_id": cell.id,
        "expires_at": expires_at.isoformat()
    })


# ============== EKİP API'LERİ ==============

@realtime_bp.get("/api/teams")
@login_required
def api_teams():
    """Tüm ekipleri listele"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    teams = Team.query.order_by(Team.name.asc()).all()
    
    return jsonify({
        "ok": True,
        "teams": [
            {"id": t.id, "name": t.name} 
            for t in teams
        ]
    })


@realtime_bp.get("/api/team/<int:team_id>/personnel")
@login_required
def api_team_personnel(team_id: int):
    """Ekipteki personeli ve email adreslerini getir"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    team = Team.query.get(team_id)
    if not team:
        return jsonify({"ok": False, "error": "team_not_found"}), 404
    
    personnel = (
        db.session.query(Person.id, Person.full_name, Person.email)
        .filter(Person.team_id == team_id)
        .filter(Person.durum == "Aktif")
        .all()
    )
    
    return jsonify({
        "ok": True,
        "team": {"id": team.id, "name": team.name},
        "personnel": [
            {
                "id": p.id,
                "name": p.full_name or "",
                "email": p.email or ""
            }
            for p in personnel
        ]
    })


@realtime_bp.post("/api/cell/unlock")
@login_required
def api_cell_unlock():
    """Hücre kilidini kaldır - düzenleme bittiğinde çağırılır"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    cell_id = int(data.get("cell_id") or 0)
    if not cell_id:
        return jsonify({"ok": False, "error": "missing_cell_id"}), 400
    
    lock = CellLock.query.filter_by(cell_id=cell_id).first()
    if lock:
        # Sadece kilidi oluşturan kaldırabilir
        if lock.user_id == user.id:
            project_id = lock.cell.project_id if lock.cell else 0
            work_date = lock.cell.work_date.isoformat() if lock.cell and lock.cell.work_date else ""
            
            db.session.delete(lock)
            db.session.commit()
            
            # Diğer kullanıcılara bildir
            try:
                socketio.emit("cell_unlocked", {
                    "cell_id": cell_id,
                    "project_id": project_id,
                    "work_date": work_date
                }, room="plan_updates", namespace="/")
            except:
                pass
    
    return jsonify({"ok": True})


@realtime_bp.get("/api/cell/locks")
@login_required
def api_cell_locks():
    """Mevcut kilitleri listele"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    now = datetime.now()
    
    # Süresi dolmamış kilitleri getir
    locks = CellLock.query.filter(CellLock.expires_at > now).all()
    
    items = []
    for lock in locks:
        lock_user = User.query.get(lock.user_id)
        cell = lock.cell
        items.append({
            "cell_id": lock.cell_id,
            "project_id": cell.project_id if cell else 0,
            "work_date": cell.work_date.isoformat() if cell and cell.work_date else "",
            "locked_by": (lock_user.full_name or lock_user.email or lock_user.username or "") if lock_user else "",
            "locked_by_id": lock.user_id,
            "expires_at": lock.expires_at.isoformat()
        })
    
    return jsonify({"ok": True, "locks": items})


# ============== ÇAKIŞMA ÇÖZÜMÜ (CONFLICT RESOLUTION) ==============

@realtime_bp.post("/api/cell/save-with-version")
@login_required
def api_cell_save_with_version():
    """Hücreyi versiyon kontrolüyle kaydet - çakışma varsa kullanıcıya sor"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    cell_id = int(data.get("cell_id") or 0)
    expected_version = int(data.get("version") or 0)
    
    if not cell_id:
        return jsonify({"ok": False, "error": "missing_cell_id"}), 400
    
    cell = PlanCell.query.get(cell_id)
    if not cell:
        return jsonify({"ok": False, "error": "cell_not_found"}), 404
    
    # Versiyon kontrolü
    current_version = cell.version or 1
    
    if expected_version > 0 and expected_version != current_version:
        # Çakışma var!
        return jsonify({
            "ok": False,
            "error": "version_conflict",
            "expected_version": expected_version,
            "current_version": current_version,
            "current_data": {
                "shift": cell.shift,
                "note": cell.note,
                "vehicle_info": cell.vehicle_info,
                "updated_at": cell.updated_at.isoformat() if cell.updated_at else None
            }
        }), 409
    
    # Eski veriyi kaydet
    old_data = {
        "shift": cell.shift,
        "note": cell.note,
        "vehicle_info": cell.vehicle_info,
        "team_id": cell.team_id,
        "subproject_id": cell.subproject_id
    }
    
    # Yeni veriyi uygula
    if "shift" in data:
        cell.shift = (data.get("shift") or "").strip() or None
    if "note" in data:
        cell.note = (data.get("note") or "").strip() or None
    if "vehicle_info" in data:
        cell.vehicle_info = (data.get("vehicle_info") or "").strip() or None
    if "team_id" in data:
        cell.team_id = int(data.get("team_id") or 0) or None
    if "subproject_id" in data:
        cell.subproject_id = int(data.get("subproject_id") or 0) or None
    if "important_note" in data:
        cell.important_note = (data.get("important_note") or "").strip() or None
    if "isdp_info" in data:
        cell.isdp_info = (data.get("isdp_info") or "").strip() or None
    if "po_info" in data:
        cell.po_info = (data.get("po_info") or "").strip() or None
    if "job_mail_body" in data:
        cell.job_mail_body = (data.get("job_mail_body") or "").strip() or None
    if "assigned_user_id" in data:
        cell.assigned_user_id = int(data.get("assigned_user_id") or 0) or None
    
    # Versiyonu artır
    cell.version = current_version + 1
    cell.updated_at = datetime.now()
    
    # Versiyon geçmişi kaydet
    version_record = CellVersion(
        cell_id=cell.id,
        version=cell.version,
        data_json=json.dumps({
            "shift": cell.shift,
            "note": cell.note,
            "vehicle_info": cell.vehicle_info,
            "team_id": cell.team_id,
            "subproject_id": cell.subproject_id,
            "important_note": cell.important_note
        }),
        changed_by_user_id=user.id,
        changed_at=datetime.now(),
        change_type="update"
    )
    db.session.add(version_record)
    
    db.session.commit()

    # Hücreye atanan kişi Job'a yansısın (Benim İşlerim'de görünsün)
    try:
        job = Job.query.filter_by(cell_id=cell.id).first()
        if job:
            _sync_job_from_cell(job, cell)
            db.session.add(job)
            db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass

    # Kilidi kaldır
    lock = CellLock.query.filter_by(cell_id=cell.id).first()
    if lock and lock.user_id == user.id:
        db.session.delete(lock)
        db.session.commit()
    
    # Diğer kullanıcılara bildir
    try:
        socketio.emit("cell_updated", {
            "cell_id": cell.id,
            "project_id": cell.project_id,
            "work_date": cell.work_date.isoformat(),
            "version": cell.version,
            "updated_by": user.full_name or user.email or user.username,
            "updated_by_id": user.id,
            "shift": cell.shift,
            "note": cell.note,
            "vehicle_info": cell.vehicle_info,
            "status": cell.status
        }, room="plan_updates", namespace="/")
    except:
        pass
    
    return jsonify({
        "ok": True,
        "cell_id": cell.id,
        "version": cell.version
    })


# ============== TARİH TAŞIMA (TASK DATE UPDATE) ==============

@realtime_bp.put("/api/update-task-date")
@login_required
def api_update_task_date():
    """İşi yeni tarihe taşı - tüm ilişkili verilerle birlikte"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    cell_id = int(data.get("cell_id") or data.get("task_id") or 0)
    new_date_str = (data.get("new_date") or "").strip()
    
    if not cell_id or not new_date_str:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    
    try:
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
    except:
        return jsonify({"ok": False, "error": "invalid_date"}), 400
    
    # Kaynak hücreyi bul
    source_cell = PlanCell.query.get(cell_id)
    if not source_cell:
        return jsonify({"ok": False, "error": "cell_not_found"}), 404
    
    old_date = source_cell.work_date
    project_id = source_cell.project_id
    
    # Aynı tarih kontrolü
    if old_date == new_date:
        return jsonify({"ok": False, "error": "same_date"}), 400
    
    # Hedef tarihte aynı proje için hücre var mı?
    existing_target = PlanCell.query.filter_by(project_id=project_id, work_date=new_date).first()
    
    if existing_target and (existing_target.shift or existing_target.note or existing_target.assignments):
        # Hedef hücre dolu - çakışma
        return jsonify({
            "ok": False,
            "error": "target_not_empty",
            "message": "Hedef tarihte zaten iş var. Önce o işi temizleyin."
        }), 409
    
    # Kişi atamalarını al
    assignments = list(CellAssignment.query.filter_by(cell_id=source_cell.id).all())
    assignment_person_ids = [a.person_id for a in assignments]
    
    # Hedef hücre oluştur veya güncelle
    if existing_target:
        target_cell = existing_target
    else:
        target_cell = PlanCell(project_id=project_id, work_date=new_date)
        db.session.add(target_cell)
        db.session.flush()  # ID almak için
    
    # Verileri kopyala
    target_cell.shift = source_cell.shift
    target_cell.note = source_cell.note
    target_cell.vehicle_info = source_cell.vehicle_info
    target_cell.team_id = source_cell.team_id
    target_cell.team_name = source_cell.team_name
    target_cell.subproject_id = source_cell.subproject_id
    target_cell.isdp_info = source_cell.isdp_info
    target_cell.po_info = source_cell.po_info
    target_cell.important_note = source_cell.important_note
    target_cell.job_mail_body = source_cell.job_mail_body
    target_cell.assigned_user_id = source_cell.assigned_user_id
    target_cell.lld_hhd_files = source_cell.lld_hhd_files
    target_cell.tutanak_files = source_cell.tutanak_files
    target_cell.version = 1
    
    # Kaynak hücreyi temizle
    source_cell.shift = None
    source_cell.note = None
    source_cell.vehicle_info = None
    source_cell.team_id = None
    source_cell.team_name = None
    source_cell.subproject_id = None
    source_cell.isdp_info = None
    source_cell.po_info = None
    source_cell.important_note = None
    source_cell.job_mail_body = None
    source_cell.assigned_user_id = None
    source_cell.lld_hhd_files = None
    source_cell.tutanak_files = None
    
    # Atamaları taşı
    for assignment in assignments:
        db.session.delete(assignment)
    
    db.session.flush()
    
    for person_id in assignment_person_ids:
        new_assignment = CellAssignment(cell_id=target_cell.id, person_id=person_id)
        db.session.add(new_assignment)
    
    db.session.commit()
    
    # Diğer kullanıcılara bildir
    # Diğer kullanıcılara bildir
    try:
        # Target assignment verilerini topla (Person detaylarıyla)
        assignments_data = []
        for a in CellAssignment.query.filter_by(cell_id=target_cell.id).all():
            p = Person.query.get(a.person_id)
            if p:
                assignments_data.append({
                    "id": p.id,
                    "name": p.full_name,
                    "role": p.role or "",
                    "color": p.color or "" 
                })
        
        socketio.emit("task_moved", {
            "source_cell_id": source_cell.id,
            "target_cell_id": target_cell.id,
            "project_id": project_id,
            "old_date": old_date.isoformat(),
            "new_date": new_date.isoformat(),
            "moved_by": user.full_name or user.email or user.username,
            "moved_by_id": user.id,
            "cell_data": {
                "shift": target_cell.shift,
                "note": target_cell.note,
                "vehicle_info": target_cell.vehicle_info,
                "team_id": target_cell.team_id,
                "status": target_cell.status,
                "subproject_id": target_cell.subproject_id,
                "assignments": assignments_data
            }
        }, room="plan_updates", namespace="/")
    except Exception as e:
        print(f"Socket emit error: {e}")
        pass
    
    return jsonify({
        "ok": True,
        "source_cell_id": source_cell.id,
        "target_cell_id": target_cell.id,
        "old_date": old_date.isoformat(),
        "new_date": new_date.isoformat(),
        "cell_data": {
            "shift": target_cell.shift,
            "note": target_cell.note,
            "vehicle_info": target_cell.vehicle_info,
            "team_id": target_cell.team_id,
            "status": target_cell.status,
            "subproject_id": target_cell.subproject_id,
            "assignments": assignments_data
        }
    })


# ============== İŞ İPTAL MEKANİZMASI (TASK CANCELLATION) ==============

@realtime_bp.post("/api/cell/cancel")
@login_required
def api_cell_cancel():
    """İşi iptal et"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    # Support both JSON and Form Data
    if request.is_json:
        data = request.get_json(force=True, silent=True) or {}
    else:
        data = request.form
        
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    cell_id = int(data.get("cell_id") or 0)
    reason = (data.get("reason") or "").strip()
    
    if not cell_id:
        return jsonify({"ok": False, "error": "missing_cell_id"}), 400
    
    cell = PlanCell.query.get(cell_id)
    if not cell:
        return jsonify({"ok": False, "error": "cell_not_found"}), 404
    
    now = datetime.now()
    previous_status = cell.status or "active"
    
    # Dosya yükleme işlemi
    file_path_db = None
    file_name_db = None
    file_type_db = None
    
    file = request.files.get('file')
    if file and file.filename:
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.instance_path, 'uploads', 'cancellations')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Unique name
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        save_path = os.path.join(upload_folder, unique_filename)
        file.save(save_path)
        
        file_path_db = f"uploads/cancellations/{unique_filename}"
        file_name_db = filename
        
        # Determine type
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            file_type_db = 'image'
        elif ext in ['.pdf']:
            file_type_db = 'pdf'
        else:
            file_type_db = 'file'
    
    # Durumu güncelle
    cell.status = "cancelled"
    cell.cancelled_at = now
    cell.cancelled_by_user_id = user.id
    cell.cancellation_reason = reason
    cell.version = (cell.version or 1) + 1
    
    # İptal kaydı oluştur
    cancellation = CellCancellation(
        cell_id=cell.id,
        cancelled_by_user_id=user.id,
        cancelled_at=now,
        reason=reason,
        previous_status=previous_status,
        file_path=file_path_db,
        file_name=file_name_db,
        file_type=file_type_db
    )
    db.session.add(cancellation)
    db.session.commit()
    
    # Diğer kullanıcılara bildir
    try:
        socketio.emit("cell_cancelled", {
            "cell_id": cell.id,
            "project_id": cell.project_id,
            "work_date": cell.work_date.isoformat(),
            "cancelled_by": user.full_name or user.email or user.username,
            "cancelled_by_id": user.id,
            "reason": reason,
            "cancelled_at": now.isoformat(),
            "has_file": bool(file_path_db)
        }, room="plan_updates", namespace="/")
    except:
        pass
    
    return jsonify({
        "ok": True,
        "cell_id": cell.id,
        "status": "cancelled",
        "cancelled_at": now.isoformat()
    })


@realtime_bp.post("/api/cell/restore")
@login_required
def api_cell_restore():
    """İptal edilen işi geri yükle"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    cell_id = int(data.get("cell_id") or 0)
    
    if not cell_id:
        return jsonify({"ok": False, "error": "missing_cell_id"}), 400
    
    cell = PlanCell.query.get(cell_id)
    if not cell:
        return jsonify({"ok": False, "error": "cell_not_found"}), 404
    
    if cell.status != "cancelled":
        return jsonify({"ok": False, "error": "not_cancelled"}), 400
    
    # Durumu geri yükle
    cell.status = "active"
    cell.cancelled_at = None
    cell.cancelled_by_user_id = None
    cell.cancellation_reason = None
    cell.version = (cell.version or 1) + 1
    
    db.session.commit()
    
    # Diğer kullanıcılara bildir
    try:
        socketio.emit("cell_restored", {
            "cell_id": cell.id,
            "project_id": cell.project_id,
            "work_date": cell.work_date.isoformat(),
            "restored_by": user.full_name or user.email or user.username,
            "restored_by_id": user.id
        }, room="plan_updates", namespace="/")
    except:
        pass
    
    return jsonify({
        "ok": True,
        "cell_id": cell.id,
        "status": "active"
    })




# ============== MESAİ GİRİŞ SİSTEMİ (OVERTIME) ==============

@realtime_bp.post("/api/overtime/add")
@login_required
def api_overtime_add():
    """Mesai kaydı ekle"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    cell_id = int(data.get("cell_id") or 0)
    person_id = int(data.get("person_id") or 0)
    team_id = int(data.get("team_id") or 0)
    work_date_str = (data.get("work_date") or "").strip()
    duration_hours = float(data.get("duration_hours") or 0)
    description = (data.get("description") or "").strip()
    
    if not work_date_str:
        return jsonify({"ok": False, "error": "missing_date"}), 400
    
    if duration_hours <= 0:
        return jsonify({"ok": False, "error": "invalid_duration"}), 400
    
    try:
        work_date = datetime.strptime(work_date_str, "%Y-%m-%d").date()
    except:
        return jsonify({"ok": False, "error": "invalid_date"}), 400
    
    overtime = TeamOvertime(
        team_id=team_id or None,
        cell_id=cell_id or None,
        person_id=person_id or None,
        work_date=work_date,
        duration_hours=duration_hours,
        description=description,
        created_by_user_id=user.id
    )
    db.session.add(overtime)
    db.session.commit()
    
    # Diğer kullanıcılara bildir
    try:
        socketio.emit("overtime_added", {
            "id": overtime.id,
            "cell_id": cell_id,
            "person_id": person_id,
            "team_id": team_id,
            "work_date": work_date_str,
            "duration_hours": duration_hours,
            "description": description,
            "created_by": user.full_name or user.email or user.username
        }, room="plan_updates", namespace="/")
    except:
        pass
    
    return jsonify({
        "ok": True,
        "id": overtime.id
    })


@realtime_bp.get("/api/overtime/list")
@login_required
def api_overtime_list():
    """Mesai kayıtlarını listele"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    cell_id = request.args.get("cell_id", type=int)
    team_id = request.args.get("team_id", type=int)
    work_date_str = request.args.get("work_date", "").strip()
    
    query = TeamOvertime.query
    
    if cell_id:
        query = query.filter_by(cell_id=cell_id)
    if team_id:
        query = query.filter_by(team_id=team_id)
    if work_date_str:
        try:
            work_date = datetime.strptime(work_date_str, "%Y-%m-%d").date()
            query = query.filter_by(work_date=work_date)
        except:
            pass
    
    records = query.order_by(TeamOvertime.created_at.desc()).limit(100).all()
    
    items = []
    for r in records:
        team = Team.query.get(r.team_id) if r.team_id else None
        person = Person.query.get(r.person_id) if r.person_id else None
        created_by = User.query.get(r.created_by_user_id)
        
        items.append({
            "id": r.id,
            "team_id": r.team_id,
            "team_name": team.name if team else None,
            "cell_id": r.cell_id,
            "person_id": r.person_id,
            "person_name": person.full_name if person else None,
            "work_date": r.work_date.isoformat(),
            "duration_hours": r.duration_hours,
            "description": r.description,
            "created_by": (created_by.full_name or created_by.email or "") if created_by else "",
            "created_at": r.created_at.isoformat()
        })
    
    return jsonify({"ok": True, "items": items})





# ============== KULLANICI AYARLARI (USER SETTINGS) ==============

@realtime_bp.get("/api/settings")
@login_required
def api_settings_get():
    """Kullanıcı ayarlarını getir"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    
    if not settings:
        # Varsayılan ayarlar
        return jsonify({
            "ok": True,
            "settings": {
                "fullscreen_shortcut": "F11",
                "theme": "light",
                "notifications_enabled": True,
                "sound_enabled": True,
                "ptt_key": "Space",
                "auto_play_voice": True
            }
        })
    
    return jsonify({
        "ok": True,
        "settings": {
            "fullscreen_shortcut": settings.fullscreen_shortcut or "F11",
            "theme": settings.theme or "light",
            "notifications_enabled": settings.notifications_enabled,
            "sound_enabled": settings.sound_enabled,
            "ptt_key": settings.ptt_key or "Space",
            "auto_play_voice": settings.auto_play_voice
        }
    })


@realtime_bp.post("/api/settings")
@login_required
def api_settings_save():
    """Kullanıcı ayarlarını kaydet"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    settings = UserSettings.query.filter_by(user_id=user.id).first()
    
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.session.add(settings)
    
    if "fullscreen_shortcut" in data:
        settings.fullscreen_shortcut = (data.get("fullscreen_shortcut") or "F11").strip()
    if "theme" in data:
        settings.theme = (data.get("theme") or "light").strip()
    if "notifications_enabled" in data:
        settings.notifications_enabled = bool(data.get("notifications_enabled"))
    if "sound_enabled" in data:
        settings.sound_enabled = bool(data.get("sound_enabled"))
    if "ptt_key" in data:
        settings.ptt_key = (data.get("ptt_key") or "Space").strip()
    if "auto_play_voice" in data:
        settings.auto_play_voice = bool(data.get("auto_play_voice"))
    
    db.session.commit()
    
    return jsonify({"ok": True})


@realtime_bp.get("/api/cell/details/<int:cell_id>")
@login_required
def api_cell_details(cell_id):
    """Hücre detaylarını getir (personeller dahil)"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    cell = PlanCell.query.get(cell_id)
    if not cell:
        return jsonify({"ok": False, "error": "not_found"}), 404
        
    assignments = []
    for a in cell.assignments:
        p = Person.query.get(a.person_id)
        if p:
            assignments.append({"id": p.id, "name": p.full_name})
            
    overtimes = []
    ots = TeamOvertime.query.filter_by(cell_id=cell.id).all()
    for ot in ots:
        p = Person.query.get(ot.person_id)
        overtimes.append({
            "id": ot.id,
            "person_name": p.full_name if p else "Bilinmeyen",
            "duration": ot.duration_hours,
            "description": ot.description
        })

    cancellation_details = None
    if cell.status == "cancelled":
        # İptal kaydını bul (en sonuncusu)
        cancellation = CellCancellation.query.filter_by(cell_id=cell.id).order_by(CellCancellation.id.desc()).first()
        if cancellation:
            user_name = cancellation.cancelled_by.full_name if cancellation.cancelled_by else "Bilinmiyor"
            cancellation_details = {
                "reason": cancellation.reason,
                "by": user_name,
                "at": cancellation.cancelled_at.strftime("%d.%m.%Y %H:%M"),
                "file_path": cancellation.file_path,
                "file_name": cancellation.file_name
            }
        else:
            # Fallback
            u = User.query.get(cell.cancelled_by_user_id) if cell.cancelled_by_user_id else None
            user_name = u.full_name if u else "Bilinmiyor"
            cancellation_details = {
                "reason": cell.cancellation_reason,
                "by": user_name,
                "at": cell.cancelled_at.strftime("%d.%m.%Y %H:%M") if cell.cancelled_at else "-",
                "file_path": None
            }

    return jsonify({
        "ok": True,
        "cell": {
            "id": cell.id,
            "status": cell.status,
            "cancellation_reason": cell.cancellation_reason,
            "cancellation": cancellation_details,
            "assignments": assignments,
            "overtimes": overtimes
        }
    })


@realtime_bp.post("/api/overtime/delete")
@login_required
def api_overtime_delete():
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
        
    ot_id = int(data.get("overtime_id") or 0)
    ot = TeamOvertime.query.get(ot_id)
    if ot:
        cell_id = ot.cell_id
        db.session.delete(ot)
        db.session.commit()
        
        remaining = TeamOvertime.query.filter_by(cell_id=cell_id).count()
        try:
             socketio.emit("overtime_deleted", {
                "cell_id": cell_id,
                "remaining_count": remaining
             }, room="plan_updates", namespace="/")
        except: pass
        
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not_found"})


@realtime_bp.post("/api/cell/paste")
@login_required
def api_cell_paste():
    """Hücre verilerini ve personelleri yapıştır"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
        
    cell_id = int(data.get("cell_id") or 0)
    project_id = int(data.get("project_id") or 0)
    work_date_str = (data.get("work_date") or "").strip()
    
    # Hücreyi bul veya oluştur
    cell = None
    
    if cell_id and cell_id > 0:
        cell = PlanCell.query.get(cell_id)
    
    # cell_id = 0 veya bulunamadıysa, project_id ve work_date ile bul/oluştur
    if not cell:
        if project_id and work_date_str:
            try:
                wd = datetime.strptime(work_date_str, "%Y-%m-%d").date()
                cell = PlanCell.query.filter_by(project_id=project_id, work_date=wd).first()
                if not cell:
                    cell = PlanCell(project_id=project_id, work_date=wd)
                    db.session.add(cell)
                    db.session.commit()  # ID almak için
            except Exception as e:
                return jsonify({"ok": False, "error": f"invalid_params: {str(e)}"}), 400
        else:
            return jsonify({"ok": False, "error": "missing_cell_or_project_info"}), 400

    # Verileri güncelle
    cell.shift = (data.get("shift") or "").strip() or None
    cell.note = (data.get("note") or "").strip() or None
    cell.vehicle_info = (data.get("vehicle_info") or "").strip() or None
    cell.team_id = int(data.get("team_id") or 0) or None
    cell.subproject_id = int(data.get("subproject_id") or 0) or None
    
    cell.updated_at = datetime.now()
    cell.version = (cell.version or 1) + 1
    
    # Personel atamaları
    # Önce eskileri sil
    CellAssignment.query.filter_by(cell_id=cell.id).delete()
    
    # Yenileri ekle
    assignments = data.get("assignments") or []
    for p_id in assignments:
        if p_id:
            new_assign = CellAssignment(cell_id=cell.id, person_id=int(p_id))
            db.session.add(new_assign)
            
    db.session.commit()
    
    # Socket emit
    try:
        # Assignment verilerini topla (Person detaylarıyla)
        assignments_data = []
        for a in CellAssignment.query.filter_by(cell_id=cell.id).all():
            p = Person.query.get(a.person_id)
            if p:
                assignments_data.append({
                    "id": p.id,
                    "name": p.full_name,
                    "role": p.role or "",
                    "color": p.color or "" 
                })

        socketio.emit("cell_updated", {
            "cell_id": cell.id,
            "project_id": cell.project_id,
            "work_date": cell.work_date.isoformat(),
            "updated_by": user.full_name or user.email,
            "updated_by_id": user.id,
            "shift": cell.shift,
            "note": cell.note,
            "vehicle_info": cell.vehicle_info,
            "status": cell.status,
            "subproject_id": cell.subproject_id,
            "assignments": assignments_data
        }, room="plan_updates", namespace="/")
    except:
        pass
        
    return jsonify({"ok": True, "cell_id": cell.id})


# ============== SES MESAJLARI (VOICE MESSAGES - PTT) ==============

@realtime_bp.post("/api/voice/send")
@login_required
def api_voice_send():
    """Ses mesajı gönder"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    to_user_id = int(data.get("to_user_id") or 0)
    team_id = int(data.get("team_id") or 0)
    audio_base64 = (data.get("audio_data") or "").strip()
    duration_seconds = float(data.get("duration") or 0)
    
    if not audio_base64:
        return jsonify({"ok": False, "error": "missing_audio"}), 400
    
    # Alıcı belirtilmezse broadcast modda çalış (to_user_id=0, team_id=0 = tümü)

    
    # Ses dosyasını kaydet
    try:
        audio_bytes = base64.b64decode(audio_base64)
    except:
        return jsonify({"ok": False, "error": "invalid_audio_data"}), 400
    
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    voice_dir = os.path.join(upload_dir, "voice")
    os.makedirs(voice_dir, exist_ok=True)
    
    filename = f"voice_{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.webm"
    filepath = os.path.join(voice_dir, filename)
    
    with open(filepath, "wb") as f:
        f.write(audio_bytes)
    
    relative_path = f"voice/{filename}"
    
    voice_msg = VoiceMessage(
        from_user_id=user.id,
        to_user_id=to_user_id or None,
        team_id=team_id or None,
        audio_path=relative_path,
        duration_seconds=duration_seconds
    )
    db.session.add(voice_msg)
    db.session.commit()
    
    # Alıcıya/ekibe bildir
    sender_name = user.full_name or user.email or user.username or f"User {user.id}"
    
    payload = {
        "id": voice_msg.id,
        "from_user_id": user.id,
        "from_user_name": sender_name,
        "audio_url": f"/uploads/{relative_path}",
        "duration": duration_seconds,
        "created_at": voice_msg.created_at.isoformat()
    }
    
    try:
        if to_user_id:
            socketio.emit("voice_message", payload, room=f"user_{to_user_id}", namespace="/")
            socketio.emit("voice_message", payload, room=f"chat_user_{to_user_id}", namespace="/")
        if team_id:
            socketio.emit("voice_message", payload, room=f"chat_team_{team_id}", namespace="/")
    except:
        pass
    
    return jsonify({
        "ok": True,
        "id": voice_msg.id,
        "audio_url": f"/uploads/{relative_path}"
    })


@realtime_bp.get("/api/voice/history")
@login_required
def api_voice_history():
    """Ses mesajı geçmişi"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    other_user_id = request.args.get("user_id", type=int)
    team_id = request.args.get("team_id", type=int)
    
    query = VoiceMessage.query
    
    if other_user_id:
        query = query.filter(
            db.or_(
                db.and_(VoiceMessage.from_user_id == user.id, VoiceMessage.to_user_id == other_user_id),
                db.and_(VoiceMessage.from_user_id == other_user_id, VoiceMessage.to_user_id == user.id)
            )
        )
    elif team_id:
        query = query.filter_by(team_id=team_id)
    else:
        # Kullanıcının kendi mesajları + kendisine gönderilenler + broadcast mesajlar
        query = query.filter(
            db.or_(
                VoiceMessage.from_user_id == user.id,
                VoiceMessage.to_user_id == user.id,
                db.and_(VoiceMessage.to_user_id.is_(None), VoiceMessage.team_id.is_(None))  # Broadcast
            )
        )

    
    messages = query.order_by(VoiceMessage.created_at.desc()).limit(50).all()
    
    items = []
    for m in messages:
        from_user = User.query.get(m.from_user_id)
        items.append({
            "id": m.id,
            "from_user_id": m.from_user_id,
            "from_user_name": (from_user.full_name or from_user.email or "") if from_user else "",
            "to_user_id": m.to_user_id,
            "team_id": m.team_id,
            "audio_url": f"/uploads/{m.audio_path}",
            "duration": m.duration_seconds,
            "is_heard": m.is_heard,
            "created_at": m.created_at.isoformat()
        })
    
    # En yeni en üstte (desc order, reverse yapmadan döndür)
    return jsonify({"ok": True, "messages": items})


@realtime_bp.post("/api/voice/<int:voice_id>/heard")
@login_required
def api_voice_mark_heard(voice_id: int):
    """Ses mesajını dinlendi olarak işaretle"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    voice = VoiceMessage.query.get(voice_id)
    if not voice:
        return jsonify({"ok": False, "error": "not_found"}), 404
    
    # Broadcast (to_user_id=None) veya kendisine gönderilen mesajları işaretleyebilir
    if voice.to_user_id is not None and voice.to_user_id != user.id:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    
    voice.is_heard = True
    voice.heard_at = datetime.now()
    db.session.commit()
    
    return jsonify({"ok": True})



# ============== TABLO MAİL GÖNDERİMİ (TABLE SNAPSHOT & EMAIL) ==============

@realtime_bp.post("/api/table/snapshot")
@login_required
def api_table_snapshot():
    """Tablo snapshot'ı oluştur (Backend generation ile fixlendi)"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    week_start_str = (data.get("week_start") or "").strip()
    # html_content from frontend is ignored to prevent empty table bug
    
    if not week_start_str:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    
    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    except:
        return jsonify({"ok": False, "error": "invalid_date"}), 400
        
    # Generate HTML on backend
    html_content = generate_full_plan_html(week_start)
    
    snapshot = TableSnapshot(
        week_start=week_start,
        html_content=html_content,
        created_by_user_id=user.id
    )
    db.session.add(snapshot)
    db.session.commit()
    
    return jsonify({
        "ok": True,
        "id": snapshot.id
    })


def generate_full_plan_html(week_start):
    """Haftalık plan tablosunu HTML olarak oluştur"""
    start = week_start
    days = [start + timedelta(days=i) for i in range(7)]
    week_end = days[-1]
    
    # Projeleri ve hücreleri al
    cells = PlanCell.query.filter(PlanCell.work_date >= days[0], PlanCell.work_date <= days[-1]).all()
    project_ids_with_work = {c.project_id for c in cells}
    
    projects = []
    if project_ids_with_work:
        projects = Project.query.filter(Project.id.in_(project_ids_with_work))\
            .order_by(Project.region.asc(), Project.project_code.asc()).all()
            
    cell_by_key = {(c.project_id, c.work_date.isoformat()): c for c in cells}
    
    # Personel atamalarını al
    ass_map = {}
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

    # HTML Başlangıç
    html = """
    <table style="border-collapse: collapse; width: 100%; border: 1px solid #e2e8f0; font-family: sans-serif; font-size: 13px;">
        <thead>
            <tr style="background-color: #f8fafc;">
                <th style="border: 1px solid #e2e8f0; padding: 10px; text-align: left; width: 100px;">İL</th>
                <th style="border: 1px solid #e2e8f0; padding: 10px; text-align: left;">PROJE</th>
                <th style="border: 1px solid #e2e8f0; padding: 10px; text-align: left; width: 120px;">SORUMLU</th>
    """
    
    TR_DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
    for i, d in enumerate(days):
        bg = "#fef3c7" if i >= 5 else "#f8fafc"
        html += f'<th style="border: 1px solid #e2e8f0; padding: 10px; text-align: center; width: 100px; background-color: {bg}">{d.strftime("%d.%m")}<br>{TR_DAYS[i]}</th>'
    
    html += """
            </tr>
        </thead>
        <tbody>
    """
    
    for p in projects:
        # Proje verisi
        proj_info = f"<b>{p.project_code}</b><br>{p.project_name}"
        
        region_bg = "#f0fdf4" # Açık yeşil
        
        html += f"""
        <tr>
            <td style="border: 1px solid #e2e8f0; padding: 8px; background-color: {region_bg}; font-weight: bold; color: #166534;">{p.region or '-'}</td>
            <td style="border: 1px solid #e2e8f0; padding: 8px;">{proj_info}</td>
            <td style="border: 1px solid #e2e8f0; padding: 8px;">{p.responsible or ''}</td>
        """
        
        for i, d in enumerate(days):
            k = d.isoformat()
            cell = cell_by_key.get((p.id, k))
            
            content = "-"
            bg_color = "#ffffff"
            
            if i >= 5: # Haftasonu
                bg_color = "#fffbeb"
            
            if cell:
                parts = []
                
                # Personel
                if ass_map.get(cell.id):
                    parts.append(", ".join(ass_map[cell.id]))
                    bg_color = "#dcfce7" # Dolu yeşil
                elif cell.note or getattr(cell, "job_mail_body", None) or cell.shift:
                    bg_color = "#d1fae5" # Sadece not/detay/saat varsa açık yeşil
                
                # Çalışma saati (vardiya değil, saat aralığı)
                if cell.shift:
                    parts.append(f"Çalışma saati: {cell.shift}")
                
                # Detay (iş detay metni)
                if getattr(cell, "job_mail_body", None):
                    parts.append(f"Detay: {cell.job_mail_body}")
                
                # Not
                if cell.note:
                    parts.append(f"Not: {cell.note}")
                
                if parts:
                    content = "<br>".join(parts)
            
            html += f'<td style="border: 1px solid #e2e8f0; padding: 8px; vertical-align: top; background-color: {bg_color};">{content}</td>'
        
        html += "</tr>"
            
    html += """
        </tbody>
    </table>
    """
    
    return html


@realtime_bp.post("/api/table/send-email")
@planner_or_admin_required
def api_table_send_email():
    """Tablo snapshot'ını e-posta ile gönder"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    snapshot_id = int(data.get("snapshot_id") or 0)
    recipients = data.get("recipients") or []
    subject = (data.get("subject") or "").strip() or "Haftalık Plan Tablosu"
    
    if not snapshot_id:
        return jsonify({"ok": False, "error": "missing_snapshot_id"}), 400
    
    snapshot = TableSnapshot.query.get(snapshot_id)
    if not snapshot:
        return jsonify({"ok": False, "error": "snapshot_not_found"}), 404
    
    if not recipients:
        return jsonify({"ok": False, "error": "no_recipients"}), 400
    
    # Mail settings'ten ayarları al
    from utils import load_mail_settings
    
    mail_cfg = load_mail_settings()
    if not (mail_cfg.get('host') and mail_cfg.get('user') and mail_cfg.get('password') and mail_cfg.get('from_addr')):
        return jsonify({"ok": False, "error": "smtp_not_configured", "message": "Mail ayarları eksik. Lütfen Mail Settings sayfasından ayarları yapın."}), 500
    
    errors = []
    successes = []
    
    # HTML içerik
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f8fafc; }}
        </style>
    </head>
    <body>
        <h2>Haftalık Plan Tablosu</h2>
        <p>Tarih: {snapshot.week_start.strftime('%d.%m.%Y')}</p>
        {snapshot.html_content}
        <hr>
        <p style="color: #666; font-size: 12px;">Bu e-posta Saha Planlama Sistemi tarafından otomatik olarak gönderilmiştir.</p>
    </body>
    </html>
    """
    
    # Her alıcıya mail gönder
    for recipient in recipients:
        ok = MailService.send(
            mail_type="weekly",
            recipients=[recipient],
            subject=subject,
            html=html_body,
            user_id=session.get("user_id"),
            meta={"type": "snapshot_send", "snapshot_id": snapshot_id},
        )
        if ok:
            successes.append(recipient)
        else:
            errors.append({"recipient": recipient, "error": "Mail gonderilemedi"})
    
    # Snapshot'ı güncelle (sadece en az bir başarı varsa)
    if successes:
        snapshot.sent_at = datetime.now()
        snapshot.recipients_json = json.dumps(recipients)
    db.session.commit()
    
    return jsonify({
        "ok": len(errors) == 0,
        "successes": successes,
        "errors": errors,
        "message": "E-posta gönderilemedi. Mail ayarlarını (Mail Settings) kontrol edin." if errors and not successes else None,
    })


@realtime_bp.post("/api/table/send-team-email")
@planner_or_admin_required
def api_table_send_team_email():
    """Ekip bazlı tablo maili gönder - sadece o ekibin işlerini içerir"""
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    
    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400
    
    week_start_str = (data.get("week_start") or "").strip()
    team_id = int(data.get("team_id") or 0)
    
    if not week_start_str or not team_id:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    
    try:
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
    except:
        return jsonify({"ok": False, "error": "invalid_date"}), 400
    
    # Ekip bilgilerini al
    team = Team.query.get(team_id)
    if not team:
        return jsonify({"ok": False, "error": "team_not_found"}), 404
    
    # Ekipteki personeli ve email adreslerini al
    team_personnel = (
        db.session.query(Person.id, Person.full_name, Person.email)
        .filter(Person.team_id == team_id)
        .filter(Person.durum == "Aktif")
        .filter(Person.email.isnot(None))
        .filter(Person.email != "")
        .all()
    )
    
    if not team_personnel:
        return jsonify({"ok": False, "error": "no_personnel"}), 400
    
    # Email adreslerini topla
    recipient_emails = [p.email for p in team_personnel if p.email]
    if not recipient_emails:
        return jsonify({"ok": False, "error": "no_emails"}), 400
    
    # Ekipteki hücreleri al (haftalık)
    week_end = week_start + timedelta(days=6)
    team_cells = (
        PlanCell.query
        .filter(PlanCell.work_date >= week_start)
        .filter(PlanCell.work_date <= week_end)
        .filter(PlanCell.team_id == team_id)
        .filter(PlanCell.status == "active")
        .all()
    )
    
    # Proje bilgilerini al
    project_ids = {c.project_id for c in team_cells if c.project_id}
    projects_by_id = {}
    for pid in project_ids:
        p = Project.query.get(pid)
        if p:
            projects_by_id[pid] = p
    
    # Alt proje bilgilerini al
    subproject_ids = {c.subproject_id for c in team_cells if c.subproject_id}
    subprojects_by_id = {}
    for sid in subproject_ids:
        sp = SubProject.query.get(sid)
        if sp:
            subprojects_by_id[sid] = sp
    
    # Günler
    days = [week_start + timedelta(days=i) for i in range(7)]
    TR_DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
    
    # Basit HTML tablo oluştur
    table_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 13px; line-height: 1.5; color: #333; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
            th, td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
            th { background-color: #f8fafc; font-weight: 600; color: #1e293b; }
            .city-row { font-weight: 700; background-color: #f0fdf4; color: #166534; padding: 10px 12px; }
            .project-cell { font-weight: 600; color: #1e293b; background-color: #f8fafc; }
            .empty { color: #94a3b8; font-style: italic; text-align: center; }
            .day-header { text-align: center; white-space: nowrap; }
            .content-cell { background-color: #ffffff; }
        </style>
    </head>
    <body>
        <h2 style="color: #1e293b; margin-bottom: 5px;">{team_name} - Haftalık Plan</h2>
        <p style="color: #64748b; margin-top: 0; margin-bottom: 20px;">Tarih: {week_start} - {week_end}</p>
        <table>
            <tr>
                <th>Proje</th>
    """.format(
        team_name=team.name,
        week_start=week_start.strftime('%d.%m.%Y'),
        week_end=week_end.strftime('%d.%m.%Y')
    )
    
    # Gün başlıkları
    for i, d in enumerate(days):
        table_html += f'<th class="day-header">{d.strftime("%d.%m")}<br>{TR_DAYS[i]}</th>'
    table_html += '</tr>'
    
    # Şehirlere göre grupla
    cells_by_city = {}
    for cell in team_cells:
        project = projects_by_id.get(cell.project_id)
        if project:
            city = (project.region or "").strip()
            if city and city != "-":
                if city not in cells_by_city:
                    cells_by_city[city] = []
                cells_by_city[city].append(cell)
    
    # Şehir satırları
    for city in sorted(cells_by_city.keys()):
        table_html += f'<tr><td colspan="8" class="city-row">{city}</td></tr>'
        
        city_cells = cells_by_city[city]
        # Projeye göre grupla
        cells_by_project = {}
        for cell in city_cells:
            if cell.project_id not in cells_by_project:
                cells_by_project[cell.project_id] = []
            cells_by_project[cell.project_id].append(cell)

        for pid in cells_by_project:
            project = projects_by_id[pid]
            cells = cells_by_project[pid]
            
            project_info = f"{project.project_code} {project.project_name}"
            
            # Alt proje (varsa en çok tekrar eden)
            sub_id = sorted([c.subproject_id for c in cells if c.subproject_id], key=lambda x: [c.subproject_id for c in cells].count(x), reverse=True)
            if sub_id:
                sp = subprojects_by_id.get(sub_id[0])
                if sp:
                     project_info += f" ({sp.name})"

            table_html += f'<tr><td class="project-cell">{project_info}</td>'
            
            # Günler
            for d in days:
                cell = next((c for c in cells if c.work_date == d), None)
                if cell:
                    cell_info = []
                    
                    # Vardiya removed per request
                    # if cell.shift: ...
                    
                    # Not
                    if cell.note:
                        cell_info.append(cell.note)
                    
                    if cell_info:
                        table_html += f'<td class="content-cell">{" | ".join(cell_info)}</td>'
                    else:
                        table_html += '<td class="empty">-</td>'
                else:
                    table_html += '<td class="empty">-</td>'
            
            table_html += '</tr>'
    
    table_html += """
        </table>
        <hr>
        <p style="color: #666; font-size: 11px;">Bu e-posta Saha Planlama Sistemi tarafından otomatik olarak gönderilmiştir.</p>
    </body>
    </html>
    """
    
    # Mail settings'ten ayarları al
    from utils import load_mail_settings
    
    mail_cfg = load_mail_settings()
    if not (mail_cfg.get('host') and mail_cfg.get('user') and mail_cfg.get('password') and mail_cfg.get('from_addr')):
        return jsonify({"ok": False, "error": "smtp_not_configured", "message": "Mail ayarları eksik."}), 500
    
    subject = f"{team.name} - Haftalık Plan ({week_start.strftime('%d.%m.%Y')})"
    
    errors = []
    successes = []
    
    # Her alıcıya mail gönder
    for recipient in recipient_emails:
        ok = MailService.send(
            mail_type="weekly",
            recipients=[recipient],
            subject=subject,
            html=table_html,
            user_id=session.get("user_id"),
            meta={"type": "table_mail", "team_id": team.id if team else None},
        )
        if ok:
            successes.append(recipient)
        else:
            errors.append({"recipient": recipient, "error": "Mail gonderilemedi"})
    
    return jsonify({
        "ok": len(errors) == 0,
        "team_name": team.name,
        "recipient_count": len(recipient_emails),
        "successes": successes,
        "errors": errors
    })


# ============== SOCKET.IO EVENTLARI ==============

@socketio.on("join_plan_updates")
def on_join_plan_updates():
    """Plan güncellemeleri odasına katıl"""
    current_user = get_current_user()
    if current_user and current_user.is_authenticated:
        join_room("plan_updates")


@socketio.on("leave_plan_updates")
def on_leave_plan_updates():
    """Plan güncellemeleri odasından ayrıl"""
    leave_room("plan_updates")


@socketio.on("cell_editing_start")
def on_cell_editing_start(data):
    """Hücre düzenleme başladı bildirimi"""
    current_user = get_current_user()
    if not current_user or not current_user.is_authenticated:
        return
    
    emit("cell_editing", {
        "project_id": data.get("project_id"),
        "work_date": data.get("work_date"),
        "user_id": current_user.id,
        "user_name": current_user.full_name or current_user.email or current_user.username
    }, room="plan_updates", include_self=False)


@socketio.on("cell_editing_end")
def on_cell_editing_end(data):
    """Hücre düzenleme bitti bildirimi"""
    current_user = get_current_user()
    if not current_user or not current_user.is_authenticated:
        return
    
    emit("cell_editing_stopped", {
        "project_id": data.get("project_id"),
        "work_date": data.get("work_date"),
        "user_id": current_user.id
    }, room="plan_updates", include_self=False)


@socketio.on("join_task_updates")
def on_join_task_updates():
    """Görev güncellemeleri odasına katıl"""
    current_user = get_current_user()
    if current_user and current_user.is_authenticated:
        join_room("task_updates")


@socketio.on("leave_task_updates")
def on_leave_task_updates():
    """Görev güncellemeleri odasından ayrıl"""
    leave_room("task_updates")
