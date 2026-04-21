# -*- coding: utf-8 -*-
"""
Görev Takip Sistemi - Routes
"""
import os
import json
import threading
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from werkzeug.utils import secure_filename
from extensions import db, socketio
from models import User, Task, TaskLog, TaskAttachment, Project, SubProject

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")

# Görev tipleri sabitleri
TASK_TYPES = [
    "Normal",
    "Uygunsuzluk",
    "Düzeltici Faaliyet",
    "Önleyici Faaliyet",
    "Diğer"
]

# Durum sabitleri
TASK_STATUSES = [
    "İlk Giriş",
    "Cevap Bekleniyor",
    "Yorum",
    "Tasarlanıyor",
    "Devam Ediyor",
    "Delege Edildi",
    "Hatalı Giriş",
    "Reddedildi",
    "İş Halledildi",
    "Güncelleme Bekliyor",
    "İptal"
]

# Önem kodları
PRIORITY_LEVELS = [1, 2, 3, 4, 5]

# Dosya yükleme için izin verilen uzantılar
# NOTE: Clipboard paste (screenshot) uploads may come as webp/bmp in some browsers.
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'zip', 'rar'
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_type(filename):
    """Dosya tipini belirle"""
    if not filename:
        return 'other'
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in ('png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'):
        return 'image'
    elif ext in ('pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt'):
        return 'document'
    return 'other'


def log_task_action(task_id, user_id, action_type, field_name=None, old_value=None, new_value=None, comment=None):
    """Görev log kaydı oluştur"""
    log = TaskLog(
        task_id=task_id,
        user_id=user_id,
        action_type=action_type,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        comment=comment
    )
    db.session.add(log)
    return log



def send_task_email(task, event_type="created", changed_by_user=None, extra_content=None):
    """
    Görev için e-posta gönder - Şablon sistemini kullanır
    event_type: created, status_changed, assigned, comment, updated, deadline_expired, reminder
    """
    import logging
    log = logging.getLogger(__name__)
    
    try:
        from utils import load_mail_settings
        
        # Mail ayarlarını kontrol et
        cfg = load_mail_settings()
        if not cfg.get('host') or not cfg.get('user') or not cfg.get('password'):
            log.warning("Mail ayarları eksik, görev bildirimi gönderilemedi")
            return
        
        # 0. Bildirim ayarı kontrolü
        if hasattr(task, 'notification_enabled') and not task.notification_enabled:
            log.info(f"Görev bildirimi kapalı, mail gönderilmedi: {task.task_no}")
            return False
        
        # Alıcı belirleme
        recipient_email = None
        
        if event_type in ['comment', 'status_changed', 'updated']:
            is_assignee_acting = (changed_by_user and task.assigned_user_id and changed_by_user.id == task.assigned_user_id)
            
            if is_assignee_acting:
                if task.created_by:
                    recipient_email = getattr(task.created_by, 'email', None)
            else:
                if task.assigned_user:
                    recipient_email = getattr(task.assigned_user, 'email', None)
        else:
            if task.assigned_user:
                recipient_email = getattr(task.assigned_user, 'email', None)
        
        if not recipient_email:
            return False
            
        # Gönderen kişiye mail atma
        if changed_by_user and recipient_email == getattr(changed_by_user, 'email', None):
            log.info("Gönderen ve alıcı aynı, mail gönderilmedi.")
            return False
        
        # Kişi bilgileri
        created_by_name = task.created_by.full_name if task.created_by else "Sistem"
        changed_by_name = changed_by_user.full_name if changed_by_user else created_by_name
        assigned_user_name = task.assigned_user.full_name if task.assigned_user else "-"
        
        # Hedef tarih formatla
        target_date_str = task.target_date.strftime("%d.%m.%Y") if task.target_date else "-"
        
        # Öncelik bilgisi
        priority_labels = {1: "Kritik", 2: "Yüksek", 3: "Orta", 4: "Düşük", 5: "Çok Düşük"}
        priority_label = priority_labels.get(task.priority, str(task.priority))
        
        # Mail türünü ve şablon tipini belirle
        if event_type == "created":
            mail_type = "task_created"
            action_text = "Size yeni bir görev atandı."
        elif event_type == "status_changed":
            mail_type = "task_status_changed"
            action_text = f"Görev durumu <strong>{task.status}</strong> olarak güncellendi."
        elif event_type == "assigned":
            mail_type = "task_assigned"
            action_text = "Bu görev size atandı."
        elif event_type == "comment":
            mail_type = "task_comment"
            action_text = "Göreve yeni bir yorum eklendi."
        elif event_type == "updated":
            mail_type = "task"
            action_text = "Görev detayları güncellendi."
        elif event_type == "deadline_expired":
            mail_type = "deadline_expired"
            action_text = "Görevin hedef tarihi geçti. Lütfen görevi tamamlayın veya yeni bir süre belirleyin."
        elif event_type == "reminder":
            mail_type = "reminder"
            action_text = "Görevinizin hedef tarihi yaklaşıyor."
        else:
            mail_type = "task"
            action_text = "Görev güncellendi."
        
        # Ekstra içerik varsa
        extra_html = ""
        if extra_content:
            extra_html = f'<div style="margin-top:15px; padding:12px; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:4px;">{extra_content}</div>'
        
        # Context (şablon değişkenleri)
        context = {
            "task_no": task.task_no,
            "task_subject": task.subject,
            "task_type": task.task_type,
            "status": task.status,
            "priority": priority_label,
            "target_date": target_date_str,
            "created_by_name": created_by_name,
            "changed_by_name": changed_by_name,
            "assigned_user_name": assigned_user_name,
            "person_name": assigned_user_name,
            "project_codes": task.project_codes or "-",
            "description": task.description or "",
            "action_text": action_text,
            "extra_content": extra_html,
            "task_id": task.id,
            "link_url": "",
            "footer": f"Bu bildirim Görev Takip Sistemi tarafından otomatik olarak gönderilmiştir. İşlem yapan: {changed_by_name}",
        }
        
        from services.mail_service import MailService
        from flask import render_template
        
        subject = f"[Görev] {task.task_no} - {task.subject}"
        
        # Görev detay tablosu oluştur
        body_html = _generate_task_body_content(task, action_text, context, extra_html)
        
        # email_base.html şablonunu kullan
        html_body = render_template(
            "email_base.html",
            title=subject,
            heading=f"{task.task_no} - {task.subject}",
            intro=action_text,
            body_html=body_html,
            footer=context.get("footer", "Bu bildirim Görev Takip Sistemi tarafından otomatik olarak gönderilmiştir."),
        )
        
        ok = MailService.send(
            mail_type=mail_type,
            recipients=[recipient_email],
            subject=subject,
            html=html_body,
            user_id=getattr(changed_by_user, "id", None),
            task_id=task.id,
            meta={
                "event_type": event_type,
                "task_no": task.task_no,
                "task_id": task.id,
                "project_codes": task.project_codes,
            },
        )
        log.info(f"Gorev bildirimi sonucu: ok={ok} {task.task_no} -> {recipient_email} ({event_type})")
        return ok
            
    except Exception as e:
        log.exception(f"Görev mail gönderim hatası: {str(e)}")


def _generate_task_body_content(task, action_text, context, extra_html=""):
    """email_base.html ile kullanılmak üzere görev body içeriği oluştur"""
    priority_colors = {
        "Kritik": "#dc2626", "Yüksek": "#f97316", "Orta": "#eab308",
        "Düşük": "#22c55e", "Çok Düşük": "#3b82f6",
    }
    priority_color = priority_colors.get(context.get("priority", ""), "#64748b")
    
    description_html = ""
    if task.description:
        desc_escaped = task.description.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        description_html = f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; margin-top: 16px; border-radius: 8px;">
            <div style="font-size: 12px; color: #64748b; text-transform: uppercase; margin-bottom: 8px; font-weight: 600;">Açıklama</div>
            <div style="font-size: 14px; color: #334155; line-height: 1.6;">{desc_escaped}</div>
        </div>"""
    
    return f"""
    {extra_html}
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px;">
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px;">
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px; font-weight: 600;">Görev Tipi</div>
            <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context.get("task_type", "-")}</div>
        </div>
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px;">
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px; font-weight: 600;">Öncelik</div>
            <div style="font-size: 14px; color: #1e293b; font-weight: 600;">
                <span style="background-color: {priority_color}; color: #ffffff; padding: 4px 12px; border-radius: 4px; font-weight: 700; font-size: 12px;">{context.get("priority", "-")}</span>
            </div>
        </div>
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px;">
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px; font-weight: 600;">Durum</div>
            <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context.get("status", "-")}</div>
        </div>
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px;">
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px; font-weight: 600;">Hedef Tarih</div>
            <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context.get("target_date", "-")}</div>
        </div>
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px;">
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px; font-weight: 600;">Oluşturan</div>
            <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context.get("created_by_name", "-")}</div>
        </div>
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 8px;">
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px; font-weight: 600;">Proje Kodları</div>
            <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context.get("project_codes", "-")}</div>
        </div>
    </div>
    {description_html}
    """


def _generate_task_email_html(task, action_text, context, extra_html=""):
    """Fallback için basit HTML mail oluştur (Geriye Uyumluluk)"""
    priority_colors = {
        "Kritik": "#dc2626", "Yüksek": "#f97316", "Orta": "#eab308",
        "Düşük": "#22c55e", "Çok Düşük": "#3b82f6",
    }
    priority_color = priority_colors.get(context.get("priority", ""), "#64748b")
    
    description_html = ""
    if task.description:
        desc_escaped = task.description.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        description_html = f"""
        <tr><td style="padding: 16px 24px;">
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 16px;">
                <div style="font-size: 12px; color: #64748b; text-transform: uppercase; margin-bottom: 8px;">Açıklama</div>
                <div style="font-size: 14px; color: #334155; line-height: 1.6;">{desc_escaped}</div>
            </div>
        </td></tr>"""
    
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<!--[if mso]><style type="text/css">body, table, td {{font-family: Arial, sans-serif !important;}}</style><![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #f5f7fa; font-family: Arial, Helvetica, sans-serif;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #f5f7fa;">
<tr><td align="center" style="padding: 20px 0;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width: 600px; background-color: #ffffff; border: 1px solid #e2e8f0;">
<tr><td style="background-color: #1e3a5f; padding: 24px; color: #ffffff;">
    <span style="background-color: rgba(255,255,255,0.2); padding: 4px 12px; font-size: 14px;">{context["task_no"]}</span>
    <h1 style="margin: 8px 0 0 0; font-size: 20px; font-weight: 700; color: #ffffff;">{context["task_subject"]}</h1>
</td></tr>
<tr><td style="padding: 24px;">
    <div style="background-color: #f0f9ff; border-left: 4px solid #3b82f6; padding: 12px 16px; font-size: 15px; color: #1e40af;">{action_text}</div>
    {extra_html}
</td></tr>
<tr><td style="padding: 0 24px 24px 24px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
<tr>
<td width="50%" style="padding-right: 8px; padding-bottom: 16px; vertical-align: top;">
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px;">
        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Görev Tipi</div>
        <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context["task_type"]}</div>
    </div>
</td>
<td width="50%" style="padding-left: 8px; padding-bottom: 16px; vertical-align: top;">
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px;">
        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Öncelik</div>
        <div style="font-size: 14px; color: #1e293b; font-weight: 600;">
            <span style="background-color: {priority_color}; color: #ffffff; padding: 4px 12px; font-weight: 700; font-size: 12px;">{context["priority"]}</span>
        </div>
    </div>
</td>
</tr>
<tr>
<td width="50%" style="padding-right: 8px; padding-bottom: 16px; vertical-align: top;">
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px;">
        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Durum</div>
        <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context["status"]}</div>
    </div>
</td>
<td width="50%" style="padding-left: 8px; padding-bottom: 16px; vertical-align: top;">
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px;">
        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Hedef Tarih</div>
        <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context["target_date"]}</div>
    </div>
</td>
</tr>
<tr>
<td width="50%" style="padding-right: 8px; vertical-align: top;">
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px;">
        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Oluşturan</div>
        <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context["created_by_name"]}</div>
    </div>
</td>
<td width="50%" style="padding-left: 8px; vertical-align: top;">
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px;">
        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Proje Kodları</div>
        <div style="font-size: 14px; color: #1e293b; font-weight: 600;">{context["project_codes"]}</div>
    </div>
</td>
</tr>
</table>
</td></tr>
{description_html}
<tr><td style="background-color: #f8fafc; padding: 16px 24px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0;">{context["footer"]}</td></tr>
</table>
</td></tr>
</table>
</body></html>"""



# --- Süresi geçen görevler için mail hatırlatma ---
_deadline_mail_state = {"last_run_date": None, "running": False}


def _send_deadline_emails_once_per_day_async():
    """
    Gün içinde bir kez süresi geçmiş görevler için mail gönder.
    Ağır çalışmayı HTTP yanıtından ayırmak için arka planda thread kullanır.
    """
    today = date.today()
    if _deadline_mail_state.get("last_run_date") == today:
        return
    if _deadline_mail_state.get("running"):
        return

    # App context'i thread'e taşımak için
    app = current_app._get_current_object()

    def runner(app_obj):
        with app_obj.app_context():
            try:
                _deadline_mail_state["running"] = True
                _send_deadline_emails()
                _deadline_mail_state["last_run_date"] = today
            except Exception as exc:
                import logging
                logging.getLogger(__name__).exception("deadline email kontrolü başarısız: %s", exc)
            finally:
                _deadline_mail_state["running"] = False

    try:
        threading.Thread(target=runner, args=(app,), daemon=True).start()
    except Exception as e:
        print(f"Error starting deadline mail thread: {e}")


def _send_deadline_emails():
    """Süresi geçen açık görevleri bulur, gün içinde bir kez mail gönderir."""
    import logging

    log = logging.getLogger(__name__)
    today = date.today()
    closed_statuses = {"İş Halledildi", "İptal"}

    expired_tasks = Task.query.filter(
        Task.target_date.is_not(None),
        Task.target_date < today,
        ~Task.status.in_(closed_statuses),
    ).all()

    sent = 0
    for t in expired_tasks:
        last_mail = t.last_deadline_mail_at.date() if t.last_deadline_mail_at else None
        if last_mail == today:
            continue

        if send_task_email(t, event_type="deadline_expired"):
            t.last_deadline_mail_at = datetime.now()
            sent += 1

    if sent:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            log.warning("deadline mail commit hatası, rollback edildi")
        log.info("Süre bitim maili gönderildi, adet=%s", sent)


@tasks_bp.route("/")
def task_list():
    """Görev listesi sayfası"""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    
    # Kullanıcıları al
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    
    return render_template("tasks.html",
                           task_types=TASK_TYPES,
                           task_statuses=TASK_STATUSES,
                           priority_levels=PRIORITY_LEVELS,
                           users=users)


# Kapalı sayılan durumlar (Görev Takip Raporu)
CLOSED_STATUSES = ["İş Halledildi", "Reddedildi", "Hatalı Giriş", "İptal"]


@tasks_bp.route("/report")
def task_report_page():
    """Görev Takip Raporu: açık görevler, tamamlanma süreleri, en hızlı kapatan, en çok açan, projeye göre."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    all_tasks = Task.query.all()
    users_by_id = {u.id: u for u in User.query.filter_by(is_active=True).all()}

    # 1) Personel üzerindeki açık görevler (assigned_user_id bazlı)
    open_tasks = [t for t in all_tasks if t.status not in CLOSED_STATUSES]
    open_by_person = {}
    for t in open_tasks:
        uid = t.assigned_user_id or 0
        open_by_person.setdefault(uid, []).append(t)
    open_per_person = []
    for uid, task_list in sorted(open_by_person.items(), key=lambda x: -len(x[1])):
        user = users_by_id.get(uid)
        name = (user.full_name or user.email or f"ID {uid}") if user else f"Atanmamış (ID {uid})"
        open_per_person.append({"user_id": uid, "user_name": name, "count": len(task_list), "tasks": task_list})

    # 2) Tamamlanma süreleri (kapalı görevlerde closed_at - created_at)
    closed_tasks = [t for t in all_tasks if t.closed_at is not None and t.status in CLOSED_STATUSES]
    completion_times = []
    for t in closed_tasks:
        delta = t.closed_at - t.created_at
        days = delta.total_seconds() / 86400
        completion_times.append({
            "task": t,
            "days": round(days, 1),
            "assigned_name": (t.assigned_user.full_name or t.assigned_user.email) if t.assigned_user else "-",
            "assigned_id": t.assigned_user_id,
        })
    completion_times.sort(key=lambda x: x["days"])

    # 3) En hızlı görevini kapatan (kapalı görevde en kısa sürede kapatan personel)
    fastest_closer = None
    if completion_times:
        fastest = completion_times[0]
        fastest_closer = {
            "user_name": fastest["assigned_name"],
            "user_id": fastest["assigned_id"],
            "task_no": fastest["task"].task_no,
            "subject": fastest["task"].subject,
            "days": fastest["days"],
        }

    # 4) En çok kayıt açılan (created_by_user_id)
    created_by_count = {}
    for t in all_tasks:
        uid = t.created_by_user_id or 0
        created_by_count[uid] = created_by_count.get(uid, 0) + 1
    most_created = []
    for uid, count in sorted(created_by_count.items(), key=lambda x: -x[1]):
        if uid == 0:
            continue
        user = users_by_id.get(uid)
        name = (user.full_name or user.email or f"ID {uid}") if user else f"ID {uid}"
        most_created.append({"user_id": uid, "user_name": name, "count": count})
    most_created = most_created[:15]

    # 5) Projelere göre görev sayıları (project_codes virgülle ayrılmış)
    project_code_counts = {}
    for t in all_tasks:
        codes = (t.project_codes or "").strip()
        if not codes:
            project_code_counts.setdefault("(Proje yok)", 0)
            project_code_counts["(Proje yok)"] += 1
            continue
        for code in [c.strip() for c in codes.split(",") if c.strip()]:
            project_code_counts.setdefault(code, 0)
            project_code_counts[code] += 1
    by_project = sorted(project_code_counts.items(), key=lambda x: -x[1])

    return render_template(
        "task_report.html",
        open_per_person=open_per_person,
        completion_times=completion_times[:50],
        fastest_closer=fastest_closer,
        most_created=most_created,
        by_project=by_project,
    )


@tasks_bp.route("/api/projects")
def api_task_projects():
    """Görev ekranı için proje kodları ve alt projeler."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    projects_raw = (
        Project.query.filter(Project.is_active == True)  # noqa: E712
        .order_by(Project.id.desc())
        .all()
    )
    projects_by_code = {}
    project_ids_by_code = {}
    for p in projects_raw:
        code = (p.project_code or "").strip()
        if not code:
            continue
        project_ids_by_code.setdefault(code, []).append(p.id)
        if code not in projects_by_code:
            projects_by_code[code] = p

    projects = list(projects_by_code.values())
    projects.sort(key=lambda p: (p.project_code or ""))
    project_ids = [pid for ids in project_ids_by_code.values() for pid in ids]
    subprojects = []
    if project_ids:
        subprojects = (
            SubProject.query.filter(
                SubProject.project_id.in_(project_ids),
                SubProject.is_active == True,  # noqa: E712
            )
            .order_by(SubProject.name.asc())
            .all()
        )

    subprojects_by_code = {}
    for sp in subprojects:
        code = (sp.project_id or 0)
        for proj_code, ids in project_ids_by_code.items():
            if code in ids:
                subprojects_by_code.setdefault(proj_code, [])
                subprojects_by_code[proj_code].append({
                    "id": sp.id,
                    "code": sp.code or "",
                    "name": sp.name or "",
                    "project_id": sp.project_id,
                })
                break

    payload = []
    for p in projects:
        proj_code = p.project_code or ""
        payload.append({
            "id": p.id,
            "code": proj_code,
            "name": p.project_name or "",
            "subprojects": subprojects_by_code.get(proj_code, []),
        })

    return jsonify({"ok": True, "projects": payload})


# YETKİ KONTROLÜ YARDIMCISI
def check_task_permission(task, current_user_id):
    """Kullanıcının görevi düzenleme/silme yetkisi var mı?"""
    # 1. Admin ise her şeye yetkisi var
    current_user = User.query.get(current_user_id)
    if current_user and (current_user.is_admin or current_user.role == 'admin'):
        return True
    
    # 2. Görevi oluşturan kişi ise yetkisi var
    if task.created_by_user_id == current_user_id:
        return True
        
    # 3. Görev atanan kişi ise yetkisi var
    if task.assigned_user_id == current_user_id:
        return True
        
    return False


@tasks_bp.route("/api/list")
def api_task_list():
    """Görev listesi API - filtreleme destekli"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    # Süresi geçmiş görevler için günlük bir kez mail kontrolü
    _send_deadline_emails_once_per_day_async()
    
    # Filtreler
    status_filter = request.args.get("status", "")
    open_closed = request.args.get("open_closed", "")  # AÇIK, KAPALI, veya boş
    priority_filter = request.args.get("priority", "")
    assigned_user_id = request.args.get("assigned_user_id", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    search = request.args.get("search", "").strip()
    project_code = request.args.get("project_code", "").strip()
    subproject_code = request.args.get("subproject_code", "").strip()
    my_tasks = request.args.get("my_tasks", "")  # "1" ise sadece kullanıcıya atanmış görevler
    
    # Query başlat
    query = Task.query
    
    # AÇIK/KAPALI filtresi
    closed_statuses = ["İş Halledildi", "Reddedildi", "Hatalı Giriş", "İptal"]
    if open_closed == "AÇIK":
        query = query.filter(~Task.status.in_(closed_statuses))
    elif open_closed == "KAPALI":
        query = query.filter(Task.status.in_(closed_statuses))
    
    # Durum filtresi
    if status_filter:
        query = query.filter(Task.status == status_filter)
    
    # Önem kodu filtresi
    if priority_filter:
        try:
            query = query.filter(Task.priority == int(priority_filter))
        except:
            pass
    
    # İlgili kişi filtresi
    if assigned_user_id:
        try:
            query = query.filter(Task.assigned_user_id == int(assigned_user_id))
        except:
            pass
    
    # Sadece benim görevlerim (Atanan VEYA Oluşturan)
    if my_tasks == "1":
        query = query.filter(
            db.or_(
                Task.assigned_user_id == user_id,
                Task.created_by_user_id == user_id
            )
        )
    
    # Tarih filtreleri
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.filter(Task.target_date >= dt_from)
        except:
            pass
    
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.filter(Task.target_date <= dt_to)
        except:
            pass
    
    # Arama
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Task.task_no.ilike(search_term),
                Task.subject.ilike(search_term),
                Task.description.ilike(search_term),
                Task.project_codes.ilike(search_term)
            )
        )

    if project_code:
        project_term = f"%{project_code}%"
        query = query.filter(Task.project_codes.ilike(project_term))

    if subproject_code:
        subproject_term = f"%Alt:%{subproject_code}%"
        query = query.filter(Task.project_codes.ilike(subproject_term))
    
    # Sıralama: Önce açık görevler, sonra önceliğe göre, sonra tarihe göre
    query = query.order_by(
        db.case(
            (Task.status.in_(closed_statuses), 1),
            else_=0
        ),
        Task.priority.asc(),
        Task.target_date.asc().nullslast(),
        Task.created_at.desc()
    )
    
    # Sonuçları al
    tasks = query.all()
    
    # JSON formatına dönüştür
    result = []
    for t in tasks:
        result.append({
            "id": t.id,
            "task_no": t.task_no,
            "task_type": t.task_type,
            "subject": t.subject,
            "description": t.description or "",
            "priority": t.priority,
            "status": t.status,
            "target_date": t.target_date.strftime("%Y-%m-%d") if t.target_date else None,
            "target_date_display": t.target_date.strftime("%d.%m.%Y") if t.target_date else "-",
            "project_codes": t.project_codes or "",
            "assigned_user_id": t.assigned_user_id,
            "assigned_user_name": t.assigned_user.full_name if t.assigned_user else "-",
            "created_by_user_id": t.created_by_user_id,  # Yetki kontrolü için
            "created_by_name": t.created_by.full_name if t.created_by else "-",
            "created_at": t.created_at.strftime("%d.%m.%Y %H:%M"),
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "is_open": t.is_open,
            "attachment_count": len(t.attachments) if t.attachments else 0
        })
    
    return jsonify({"ok": True, "tasks": result, "count": len(result)})


@tasks_bp.route("/api/create", methods=["POST"])
def api_create_task():
    """Yeni görev oluştur"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    
    # Zorunlu alanlar
    subject = (data.get("subject") or "").strip()
    if not subject:
        return jsonify({"ok": False, "error": "Konu zorunludur"}), 400
    
    # Görev numarası üret
    task_no = Task.generate_task_no()
    
    # Yeni görev oluştur
    initial_status = data.get("status") or "İlk Giriş"
    if initial_status not in TASK_STATUSES:
        initial_status = "İlk Giriş"
    
    task = Task(
        task_no=task_no,
        task_type=data.get("task_type") or "Normal",
        assigned_user_id=int(data.get("assigned_user_id")) if data.get("assigned_user_id") else None,
        priority=int(data.get("priority") or 3),
        status=initial_status,
        project_codes=data.get("project_codes") or "",
        subject=subject,
        description=data.get("description") or "",
        created_by_user_id=user_id,
        # Mail Hatırlatma Ayarları
        reminder_days_before=int(data.get("reminder_days_before") or 0),
        reminder_count=int(data.get("reminder_count") or 0),
        # Bildirim Ayarı
        notification_enabled=bool(data.get("notification_enabled", True) if "notification_enabled" in data else True)
    )
    
    # Hedef tarih
    if data.get("target_date"):
        try:
            task.target_date = datetime.strptime(data["target_date"], "%Y-%m-%d").date()
        except:
            pass
    
    db.session.add(task)
    db.session.commit()
    
    # Log kaydı
    log_task_action(task.id, user_id, "create", comment=f"Görev oluşturuldu: {task_no}")
    db.session.commit()
    
    # E-posta gönder
    current_user = User.query.get(user_id)
    email_sent = send_task_email(task, "created", changed_by_user=current_user)
    
    # Socket bildirimi
    try:
        task_data = {
            "id": task.id,
            "task_no": task.task_no,
            "task_type": task.task_type,
            "subject": task.subject,
            "description": task.description or "",
            "priority": task.priority,
            "status": task.status,
            "target_date_display": task.target_date.strftime("%d.%m.%Y") if task.target_date else "-",
            "assigned_user_id": task.assigned_user_id,
            "assigned_user_name": task.assigned_user.full_name if task.assigned_user else "-",
            "is_open": task.is_open
        }
        socketio.emit("task_created", {"task": task_data}, room="task_updates", namespace="/")
    except Exception as e:
        print(f"Socket emit error: {e}")

    return jsonify({
        "ok": True,
        "task_id": task.id,
        "task_no": task.task_no,
        "email_sent": email_sent,
        "message": f"Görev {task_no} başarıyla oluşturuldu"
    })


@tasks_bp.route("/api/<int:task_id>")
def api_get_task(task_id):
    """Görev detayı"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401


    
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"ok": False, "error": "Görev bulunamadı"}), 404
    
    # Log kayıtları
    logs = []
    for log in task.logs:
        logs.append({
            "id": log.id,
            "action_type": log.action_type,
            "field_name": log.field_name,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "comment": log.comment,
            "user_name": log.user.full_name if log.user else "-",
            "created_at": log.created_at.strftime("%d.%m.%Y %H:%M")
        })
    
    # Ek dosyalar
    attachments = []
    for att in task.attachments:
        attachments.append({
            "id": att.id,
            "file_name": att.file_name,
            "file_type": att.file_type,
            "file_size": att.file_size,
            "file_path": att.file_path,
            "uploaded_by": att.uploaded_by.full_name if att.uploaded_by else "-",
            "uploaded_at": att.uploaded_at.strftime("%d.%m.%Y %H:%M")
        })
    
    return jsonify({
        "ok": True,
        "task": {
            "id": task.id,
            "task_no": task.task_no,
            "task_type": task.task_type,
            "subject": task.subject,
            "description": task.description or "",
            "priority": task.priority,
            "status": task.status,
            "target_date": task.target_date.strftime("%Y-%m-%d") if task.target_date else None,
            "project_codes": task.project_codes or "",
            "assigned_user_id": task.assigned_user_id,
            "assigned_user_name": task.assigned_user.full_name if task.assigned_user else "-",
            "created_by_user_id": task.created_by_user_id,
            "created_by_name": task.created_by.full_name if task.created_by else "-",
            "created_at": task.created_at.strftime("%d.%m.%Y %H:%M"),
            "updated_at": task.updated_at.strftime("%d.%m.%Y %H:%M"),
            "closed_at": task.closed_at.strftime("%d.%m.%Y %H:%M") if task.closed_at else None,
            "is_open": task.is_open,
            # Mail hatırlatma ayarları
            "reminder_days_before": getattr(task, 'reminder_days_before', 0) or 0,
            "reminder_count": getattr(task, 'reminder_count', 0) or 0,
            "notification_enabled": getattr(task, 'notification_enabled', True)
        },
        "logs": logs,
        "attachments": attachments
    })


@tasks_bp.route("/api/<int:task_id>/update", methods=["POST"])
def api_update_task(task_id):
    """Görev güncelle"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"ok": False, "error": "Görev bulunamadı"}), 404

    # YETKİ KONTROLÜ
    if not check_task_permission(task, user_id):
        return jsonify({"ok": False, "error": "Bu işlem için yetkiniz yok (Sadece atanan veya oluşturan düzenleyebilir)"}), 403
    
    data = request.get_json() or {}
    
    # Değişiklikleri takip et
    changes = []
    email_sent = False
    
    # Kısıtlı Yetki Kontrolü: Sadece Atanan Kişi ise (Admin/Oluşturan değilse)
    # Sadece STATÜ değiştirebilir. Diğer alanlar yasak.
    current_user = User.query.get(user_id)
    is_full_admin = current_user.is_admin or current_user.role == 'admin'
    is_creator = (task.created_by_user_id == user_id)
    
    if not (is_full_admin or is_creator):
        # Sadece atanan kişi buraya düşer (check_task_permission geçtikten sonra)
        # Gelen veride status dışında bir şey var mı bak
        # (csrf_token veya boş field'lar hariç)
        for key in data.keys():
            if key not in ["status", "csrf_token"] and data[key] is not None:
                # Field listesindeyse yasakla
                if any(f[0] == key for f in [
                    ("task_type", "", ""), ("priority", "", ""), ("subject", "", ""),
                    ("description", "", ""), ("project_codes", "", ""),
                    ("reminder_days_before", "", ""), ("reminder_count", "", ""),
                    ("assigned_user_id", "", ""), ("target_date", "", "")
                ]):
                     return jsonify({"ok": False, "error": "Atanan kişi sadece durumu değiştirebilir."}), 403
    
    # Alan güncellemeleri
    fields_to_update = [
        ("task_type", "task_type", "Görev Tipi"),
        ("priority", "priority", "Önem Kodu"),
        ("subject", "subject", "Konu"),
        ("description", "description", "Açıklama"),
        ("project_codes", "project_codes", "Proje Kodları"),
        ("reminder_days_before", "reminder_days_before", "Hatırlatma Günü"),
        ("reminder_count", "reminder_count", "Hatırlatma Sayısı"),
        ("notification_enabled", "notification_enabled", "Bildirim Ayarı"),
    ]
    
    for field_key, field_attr, field_label in fields_to_update:
        if field_key in data:
            old_val = getattr(task, field_attr)
            new_val = data[field_key]
            
            if field_key == "priority" or field_key == "reminder_days_before" or field_key == "reminder_count":
                try:
                    new_val = int(new_val) if new_val else 0
                    if field_key == "priority" and new_val == 0: new_val = 3
                except:
                    new_val = 0
            elif field_key == "notification_enabled":
                new_val = bool(new_val)
            
            if str(old_val or "") != str(new_val or ""):
                setattr(task, field_attr, new_val)
                changes.append((field_attr, old_val, new_val, field_label))
    
    # İlgili kişi güncellemesi
    if "assigned_user_id" in data:
        old_user_id = task.assigned_user_id
        new_user_val = data["assigned_user_id"]
        new_user_id = int(new_user_val) if new_user_val else None
        
        if old_user_id != new_user_id:
            # İsimleri ID üzerinden manuel çek (İlişki yükleme hatasını önlemek için)
            old_u = User.query.get(old_user_id) if old_user_id else None
            new_u = User.query.get(new_user_id) if new_user_id else None
            
            print(f"DEBUG: Assignee Change - OldID: {old_user_id}, NewID: {new_user_id}")
            print(f"DEBUG: Old User: {old_u}, New User: {new_u}")

            old_user_name = (old_u.full_name or old_u.username) if old_u else "-"
            new_user_name = (new_u.full_name or new_u.username) if new_u else "-"
            
            print(f"DEBUG: Names - Old: {old_user_name}, New: {new_user_name}")

            task.assigned_user_id = new_user_id            
            changes.append(("assigned_user_id", old_user_name, new_user_name, "İlgili Kişi"))
            
            # Yeni atanan kişiye e-posta gönder
            if new_user_id:
                current_user = User.query.get(user_id)
                sent = send_task_email(task, "assigned", changed_by_user=current_user)
                if sent: email_sent = True
    
    # Hedef tarih güncellemesi
    if "target_date" in data:
        old_date = task.target_date
        new_date = None
        if data["target_date"]:
            try:
                new_date = datetime.strptime(data["target_date"], "%Y-%m-%d").date()
            except:
                pass
        
        if old_date != new_date:
            old_date_str = old_date.strftime("%d.%m.%Y") if old_date else "-"
            new_date_str = new_date.strftime("%d.%m.%Y") if new_date else "-"
            task.target_date = new_date
            changes.append(("target_date", old_date_str, new_date_str, "Hedef Tarih"))
    
    # Durum güncellemesi - özel işlem
    if "status" in data and data["status"] != task.status:
        old_status = task.status
        new_status = data["status"]
        
        task.status = new_status
        
        # Kapatma durumları
        closed_statuses = ["İş Halledildi", "Reddedildi", "Hatalı Giriş"]
        if new_status in closed_statuses and old_status not in closed_statuses:
            task.closed_at = datetime.now()
            task.closed_by_user_id = user_id
        elif new_status not in closed_statuses and old_status in closed_statuses:
            # Yeniden açılıyor
            task.closed_at = None
            task.closed_by_user_id = None
        
        # Durum değişikliği için log
        log_task_action(task.id, user_id, "status_change",
                       field_name="status",
                       old_value=old_status,
                       new_value=new_status)
        
        # E-posta gönder
        current_user = User.query.get(user_id)
        sent = send_task_email(task, "status_changed", changed_by_user=current_user)
        if sent: email_sent = True
    
    # Diğer değişiklikler için log
    for field_attr, old_val, new_val, field_label in changes:
        log_task_action(task.id, user_id, "field_change",
                       field_name=field_label,
                       old_value=old_val,
                       new_value=new_val)
    
    db.session.commit()
    
    # Genel güncelleme maili (Statü ve Atama hariç - onlar yukarıda gönderiliyor)
    # Atama değişikliği 'changes' içinde olabilir ('assigned_user_id'), onu filtrelemeliyiz.
    generic_changes = [c for c in changes if c[0] != "assigned_user_id" and c[0] != "status"]
    if generic_changes:
        summary_lines = []
        for field, old, new, label in generic_changes:
            summary_lines.append(f"<strong>{label}:</strong> {old} → {new}")
        
        summary_text = "<br>".join(summary_lines)
        # Mevcut kullanıcıyı çek
        current_user = User.query.get(user_id)
        sent = send_task_email(task, "updated", changed_by_user=current_user, extra_content=summary_text)
        if sent: email_sent = True
    
    # Socket bildirimi
    try:
        task_data = {
            "id": task.id,
            "task_no": task.task_no,
            "status": task.status,
            "priority": task.priority,
            "subject": task.subject,
            "assigned_user_id": task.assigned_user_id,
            "assigned_user_name": task.assigned_user.full_name if task.assigned_user else "-",
            "target_date_display": task.target_date.strftime("%d.%m.%Y") if task.target_date else "-",
            "is_open": task.is_open
        }
        socketio.emit("task_updated", {"task": task_data, "changes": changes}, room="task_updates", namespace="/")
    except Exception as e:
        print(f"Socket emit error: {e}")
    
    return jsonify({
        "ok": True,
        "message": "Görev güncellendi",
        "changes_count": len(changes) + (1 if "status" in data else 0)
    })


@tasks_bp.route("/api/<int:task_id>/comment", methods=["POST"])
def api_add_comment(task_id):
    """Göreve yorum ekle"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"ok": False, "error": "Görev bulunamadı"}), 404
    
    data = request.get_json() or {}
    comment_text = (data.get("comment") or "").strip()
    
    if not comment_text:
        return jsonify({"ok": False, "error": "Yorum boş olamaz"}), 400
    
    log_task_action(task.id, user_id, "comment", comment=comment_text)
    db.session.commit()
    
    current_user = User.query.get(user_id)

    # Yorum bildirimi gönder (send_task_email içinde alıcı belirlenir)
    email_sent = send_task_email(task, "comment", changed_by_user=current_user, extra_content=comment_text)
    
    # Socket bildirimi - opsiyonel, listede bir şey güncellenmiyor ama bildirim verilebilir
    try:
        socketio.emit("task_commented", {"task_id": task.id, "comment": comment_text, "user_name": current_user.full_name}, room="task_updates", namespace="/")
    except:
        pass

    return jsonify({"ok": True, "message": "Yorum eklendi", "email_sent": email_sent})


@tasks_bp.route("/api/<int:task_id>/attachment", methods=["POST"])
def api_upload_attachment(task_id):
    """Göreve dosya ekle"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"ok": False, "error": "Görev bulunamadı"}), 404
    
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Dosya bulunamadı"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "Dosya seçilmedi"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Bu dosya türü desteklenmiyor"}), 400
    
    # Dosyayı kaydet
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_filename = f"task_{task_id}_{timestamp}_{filename}"
    
    upload_folder = os.path.join(current_app.instance_path, "uploads", "tasks")
    os.makedirs(upload_folder, exist_ok=True)
    
    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)
    
    # Dosya boyutu
    file_size = os.path.getsize(file_path)
    
    # Veritabanına kaydet
    attachment = TaskAttachment(
        task_id=task_id,
        file_path=f"tasks/{unique_filename}",
        file_name=filename,
        file_type=get_file_type(filename),
        file_size=file_size,
        uploaded_by_user_id=user_id
    )
    db.session.add(attachment)
    
    # Log kaydı
    log_task_action(task_id, user_id, "attachment_add", comment=f"Dosya eklendi: {filename}")
    db.session.commit()
    
    return jsonify({
        "ok": True,
        "attachment_id": attachment.id,
        "file_name": filename,
        "message": "Dosya yüklendi"
    })


@tasks_bp.route("/api/attachment/<int:attachment_id>/delete", methods=["POST"])
def api_delete_attachment(attachment_id):
    """Dosya sil"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    attachment = TaskAttachment.query.get(attachment_id)
    if not attachment:
        return jsonify({"ok": False, "error": "Dosya bulunamadı"}), 404
    
    task_id = attachment.task_id
    file_name = attachment.file_name
    
    # Fiziksel dosyayı sil
    try:
        file_path = os.path.join(current_app.instance_path, "uploads", attachment.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass
    
    # Veritabanından sil
    db.session.delete(attachment)
    
    # Log kaydı
    log_task_action(task_id, user_id, "attachment_delete", comment=f"Dosya silindi: {file_name}")
    db.session.commit()
    
    return jsonify({"ok": True, "message": "Dosya silindi"})


@tasks_bp.route("/api/stats")
def api_task_stats():
    """Görev istatistikleri"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    closed_statuses = ["İş Halledildi", "Reddedildi", "Hatalı Giriş", "İptal"]
    
    # Toplam sayılar
    total = Task.query.count()
    open_count = Task.query.filter(~Task.status.in_(closed_statuses)).count()
    closed_count = Task.query.filter(Task.status.in_(closed_statuses)).count()
    
    # Bana atanan görevler
    my_open = Task.query.filter(
        Task.assigned_user_id == user_id,
        ~Task.status.in_(closed_statuses)
    ).count()
    
    my_total = Task.query.filter(Task.assigned_user_id == user_id).count()
    
    # Önceliğe göre açık görevler
    priority_stats = {}
    for p in PRIORITY_LEVELS:
        count = Task.query.filter(
            Task.priority == p,
            ~Task.status.in_(closed_statuses)
        ).count()
        priority_stats[p] = count
    
    return jsonify({
        "ok": True,
        "stats": {
            "total": total,
            "open": open_count,
            "closed": closed_count,
            "my_open": my_open,
            "my_total": my_total,
            "by_priority": priority_stats
        }
    })


# ========== TOPLU İŞLEMLER (BULK ACTIONS) ==========

@tasks_bp.route("/api/bulk/status", methods=["POST"])
def api_bulk_status():
    """Toplu statü değiştir"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    task_ids = data.get("task_ids", [])
    new_status = data.get("status")
    
    if not task_ids or not new_status:
        return jsonify({"ok": False, "error": "Eksik parametre"}), 400
    
    updated = 0
    email_sent_count = 0
    current_user = User.query.get(user_id)
    
    for task_id in task_ids:
        task = Task.query.get(task_id)
        if not task:
            continue
        
        if not check_task_permission(task, user_id):
            continue
        
        old_status = task.status
        if old_status == new_status:
            continue
            
        task.status = new_status
        task.updated_at = datetime.now()
        
        # Log kaydet
        log_task_action(task.id, user_id, "status_change", 
                       field_name="status", old_value=old_status, new_value=new_status)
                       
        # Mail gönder (Status değişikliği için)
        sent = send_task_email(task, "status_changed", changed_by_user=current_user)
        if sent: email_sent_count += 1
        
        updated += 1
    
    db.session.commit()
    return jsonify({"ok": True, "updated_count": updated, "email_sent_count": email_sent_count})


@tasks_bp.route("/api/bulk/assign", methods=["POST"])
def api_bulk_assign():
    """Toplu kişi ata"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    task_ids = data.get("task_ids", [])
    assigned_user_id = data.get("assigned_user_id")
    
    if not task_ids or assigned_user_id is None:
        return jsonify({"ok": False, "error": "Eksik parametre"}), 400
    
    updated = 0
    email_sent_count = 0
    
    user_to_assign = User.query.get(assigned_user_id)
    new_user_name = user_to_assign.full_name if user_to_assign else "-"
    
    current_user = User.query.get(user_id)
    
    for task_id in task_ids:
        task = Task.query.get(task_id)
        if not task:
            continue

        if not check_task_permission(task, user_id):
            continue
        
        old_user_id = task.assigned_user_id
        if str(old_user_id) == str(assigned_user_id):
            continue
        
        old_u = User.query.get(old_user_id) if old_user_id else None
        old_user_name = (old_u.full_name or old_u.username) if old_u else "-"
        
        task.assigned_user_id = assigned_user_id
        task.updated_at = datetime.now()
        
        # Değişikliğin anında yansıması için flush (ÖNEMLİ: Mail gönderirken relation güncel olsun)
        db.session.flush()
        
        # Log kaydet
        log_task_action(task.id, user_id, "assigned_user_id", 
                       field_name="İlgili Kişi", old_value=old_user_name, new_value=new_user_name)
        
        # Mail gönder
        sent = send_task_email(task, "assigned", changed_by_user=current_user)
        if sent: email_sent_count += 1
        
        updated += 1
    
    db.session.commit()
    return jsonify({"ok": True, "updated_count": updated, "email_sent_count": email_sent_count})


@tasks_bp.route("/api/bulk/priority", methods=["POST"])
def api_bulk_priority():
    """Toplu önem değiştir"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    task_ids = data.get("task_ids", [])
    new_priority = data.get("priority")
    
    if not task_ids or new_priority is None:
        return jsonify({"ok": False, "error": "Eksik parametre"}), 400
    
    updated = 0
    for task_id in task_ids:
        task = Task.query.get(task_id)
        if not task:
            continue

        if not check_task_permission(task, user_id):
            continue
        
        old_priority = task.priority
        task.priority = int(new_priority)
        task.updated_at = datetime.now()
        
        # Log kaydet
        log_task_action(task.id, user_id, "field_change", 
                       field_name="priority", old_value=str(old_priority), new_value=str(new_priority))
        updated += 1
    
    db.session.commit()
    return jsonify({"ok": True, "updated_count": updated})


@tasks_bp.route("/api/bulk/date", methods=["POST"])
def api_bulk_date():
    """Toplu tarih değiştir"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    task_ids = data.get("task_ids", [])
    target_date_str = data.get("target_date")
    
    if not task_ids:
        return jsonify({"ok": False, "error": "Eksik parametre"}), 400
    
    # Tarih parse
    new_date = None
    if target_date_str:
        try:
            new_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except:
            return jsonify({"ok": False, "error": "Geçersiz tarih formatı"}), 400
    
    updated = 0
    for task_id in task_ids:
        task = Task.query.get(task_id)
        if not task:
            continue

        if not check_task_permission(task, user_id):
            continue
        
        old_date = task.target_date.strftime("%d.%m.%Y") if task.target_date else "-"
        task.target_date = new_date
        task.updated_at = datetime.now()
        
        new_date_str = new_date.strftime("%d.%m.%Y") if new_date else "-"
        
        # Log kaydet
        log_task_action(task.id, user_id, "field_change", 
                       field_name="target_date", old_value=old_date, new_value=new_date_str)
        updated += 1
    
    db.session.commit()
    return jsonify({"ok": True, "updated_count": updated})


@tasks_bp.route("/api/bulk/delete", methods=["POST"])
def api_bulk_delete():
    """Toplu sil (soft delete - statüyü İptal yap)"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    data = request.get_json() or {}
    task_ids = data.get("task_ids", [])
    
    if not task_ids:
        return jsonify({"ok": False, "error": "Eksik parametre"}), 400
    
    try:
        deleted = 0
        for task_id in task_ids:
            task = Task.query.get(task_id)
            if not task:
                continue
            
            # YETKİ KONTROLÜ
            if not check_task_permission(task, user_id):
                continue
            
            # Soft delete: Statüyü İptal yap ve kapat
            old_status = task.status
            task.status = "İptal"

            task.closed_at = datetime.now()
            task.updated_at = datetime.now()
            
            # Log kaydet
            log_task_action(task.id, user_id, "status_change", 
                           field_name="status", old_value=old_status, new_value="İptal",
                           comment="Toplu silme işlemi ile iptal edildi")
            deleted += 1
        
        db.session.commit()
        return jsonify({"ok": True, "deleted_count": deleted})
    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({"ok": False, "error": f"Server Error: {str(e)}", "trace": traceback.format_exc()}), 500
