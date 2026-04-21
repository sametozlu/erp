from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory, current_app, jsonify, abort, send_file
from extensions import db
from models import MailLog, MailQueue
from services.mail_service import MailService
from utils import (
    login_required, admin_required, load_mail_settings, _load_mail_settings_file, 
    _csrf_verify, _is_valid_email_address, save_mail_settings, MAIL_PASSWORD_PLACEHOLDER,
    render_test_email, get_current_user
)
from datetime import datetime
import logging
import os
log = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/mail/settings", methods=["GET", "POST"])
@admin_bp.route("/admin/mail-settings", methods=["GET", "POST"])
@admin_required
def mail_settings_page():
    cfg_file = _load_mail_settings_file()
    cfg = load_mail_settings()
    has_saved_password = bool(cfg_file.get("password"))
    try:
        mail_logs = MailLog.query.order_by(MailLog.created_at.desc()).limit(10).all()
    except Exception:
        mail_logs = []

    if request.method == "POST":
        if not _csrf_verify(request.form.get("csrf_token", "")):
            flash("GÃ¼venlik doÄŸrulamasÄ± baÅŸarÄ±sÄ±z (CSRF). SayfayÄ± yenileyip tekrar deneyin.", "danger")
            return redirect(url_for('admin.mail_settings_page'))

        action = (request.form.get("action") or "save").strip()
        if action == "test":
            test_to = (request.form.get("test_to") or "").strip()
            if not test_to or "@" not in test_to:
                flash("Test hedef mail adresi gecersiz.", "danger")
                return redirect(url_for('admin.mail_settings_page'))

        host = (request.form.get("host") or "").strip()
        port_str = (request.form.get("port") or "").strip()
        user = (request.form.get("user") or "").strip()
        password = (request.form.get("password") or "").strip()
        from_name = (request.form.get("from_name") or "").strip()
        from_addr = (request.form.get("from_addr") or "").strip()
        notify_to = (request.form.get("notify_to") or "").strip()
        notify_cc = (request.form.get("notify_cc") or "").strip()
        use_tls = (request.form.get("use_tls") == "1")

        if not host:
            flash("Host zorunlu.", "danger")
            return redirect(url_for('admin.mail_settings_page'))
        try:
            port = int(port_str or 587)
        except Exception:
            flash("Port geÃ§ersiz.", "danger")
            return redirect(url_for('admin.mail_settings_page'))

        if not _is_valid_email_address(from_addr):
            flash("GÃ¶nderen (From) geÃ§ersiz. Ã–rnek: ad@domain.com veya \"Ad Soyad <ad@domain.com>\".", "danger")
            return redirect(url_for('admin.mail_settings_page'))

        # Password is optional in the form: if empty, keep the existing JSON value.
        data = dict(cfg_file or {})
        data.update({
            "host": host,
            "port": port,
            "user": user,
            "from_name": from_name,
            "from_addr": from_addr,
            "use_tls": use_tls,
            "use_ssl": (request.form.get("use_ssl") == "1"),
            "notify_to": notify_to,
            "notify_cc": notify_cc,
        })
        use_ssl = bool(data.get("use_ssl"))
        if password and password != MAIL_PASSWORD_PLACEHOLDER:
            data["password"] = password
        if not (data["host"] and data["port"] and data["user"] and data["from_addr"]):
            flash("Host/Port/User/From alanlarÄ± zorunlu.", "danger")
            return redirect(url_for('admin.mail_settings_page'))
        if not data.get("password"):
            flash("Åifre zorunlu (boÅŸ kaydedilemez).", "danger")
            return redirect(url_for('admin.mail_settings_page'))

        if use_ssl and use_tls:
            flash("Not: SSL seciliyse STARTTLS uygulanmaz (SSL onceliklidir).", "warning")
        save_mail_settings(data)
        flash("Mail ayarlarÄ± kaydedildi.", "success")
        return redirect(url_for('admin.mail_settings_page'))

    return render_template(
        "mail_settings.html",
        cfg=cfg,
        has_saved_password=has_saved_password,
        password_placeholder=MAIL_PASSWORD_PLACEHOLDER,
        mail_logs=mail_logs,
    )




@admin_bp.post("/mail/settings/test")
@admin_bp.post("/admin/mail-settings/test")
@admin_required
def mail_settings_test():
    # Accept both form and JSON
    if request.is_json:
        data = request.get_json(force=True, silent=True) or {}
        token = str(data.get("csrf_token") or "")
        test_to = (data.get("test_to") or data.get("to") or "").strip()
        host = (data.get("host") or "").strip()
        port_str = str(data.get("port") or "").strip()
        user = (data.get("user") or "").strip()
        password = (data.get("password") or "").strip()
        from_addr = (data.get("from_addr") or "").strip()
        use_tls = bool(data.get("use_tls"))
        use_ssl = bool(data.get("use_ssl"))
    else:
        token = request.form.get("csrf_token", "")
        test_to = (request.form.get("test_to") or "").strip()
        host = (request.form.get("host") or "").strip()
        port_str = (request.form.get("port") or "").strip()
        user = (request.form.get("user") or "").strip()
        password = (request.form.get("password") or "").strip()
        from_addr = (request.form.get("from_addr") or "").strip()
        use_tls = (request.form.get("use_tls") == "1")
        use_ssl = (request.form.get("use_ssl") == "1")

    if not _csrf_verify((token or "").strip()):
        msg = "CSRF dogrulamasi basarisiz."
        if request.is_json:
            return jsonify({"ok": False, "code": "csrf", "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('admin.mail_settings_page'))

    if not test_to or "@" not in test_to:
        msg = "Test hedef mail adresi gecersiz."
        if request.is_json:
            return jsonify({"ok": False, "code": "recipient", "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('admin.mail_settings_page'))

    if not host:
        msg = "Host zorunlu."
        if request.is_json:
            return jsonify({"ok": False, "code": "config", "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('admin.mail_settings_page'))

    try:
        port = int(port_str or 587)
    except Exception:
        msg = "Port gecersiz."
        if request.is_json:
            return jsonify({"ok": False, "code": "config", "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('admin.mail_settings_page'))

    if not _is_valid_email_address(from_addr):
        msg = "GÃ¶nderen (From) geÃ§ersiz. Ã–rnek: ad@domain.com veya \"Ad Soyad <ad@domain.com>\"."
        if request.is_json:
            return jsonify({"ok": False, "code": "from_refused", "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('admin.mail_settings_page'))

    cfg_file = _load_mail_settings_file()
    # preserve password if left blank
    cfg_override = dict(cfg_file or {})
    cfg_override.update({
        "host": host,
        "port": port,
        "user": user,
        "from_addr": from_addr,
        "use_tls": bool(use_tls),
        "use_ssl": bool(use_ssl),
    })
    if password and password != MAIL_PASSWORD_PLACEHOLDER:
        cfg_override["password"] = password
    meta = {
        "type": "smtp_test",
        "smtp": {"host": host, "port": int(port), "use_ssl": bool(use_ssl), "use_tls": bool(use_tls)},
    }
    
    # Yeni sabit ÅŸablon sistemi kullan
    subject, html = render_test_email(
        recipient_name="Test KullanÄ±cÄ±",
        sender_name="Sistem"
    )
    
    ok = MailService.send(
        mail_type="test",
        recipients=[test_to],
        subject=subject,
        html=html,
        user_id=session.get("user_id"),
        meta=meta,
        cfg_override=cfg_override,
    )
    
    if ok:
        if request.is_json:
            return jsonify({"ok": True}), 200
        flash("Test mail gonderildi.", "success")
        return redirect(url_for('admin.mail_settings_page'))
    else:
        if request.is_json:
            return jsonify({"ok": False, "code": "send_failed", "error": "Gonderilemedi"}), 500
        flash("Test mail gonderilemedi. Detay icin loglari kontrol edin.", "danger")
        return redirect(url_for('admin.mail_settings_page'))
@admin_bp.get("/api/mail/logs")
@admin_required
def api_mail_logs():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        date_start_str = request.args.get("date_start")
        date_end_str = request.args.get("date_end")
        m_type = request.args.get("type")
        status = request.args.get("status") # ok/error
        q = (request.args.get("q") or "").strip().lower()

        query = MailLog.query

        if date_start_str:
            try:
                ds = datetime.strptime(date_start_str, "%Y-%m-%d")
                query = query.filter(MailLog.created_at >= ds)
            except: pass
        
        if date_end_str:
            try:
                de = datetime.strptime(date_end_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                query = query.filter(MailLog.created_at <= de)
            except: pass

        if m_type and m_type != "all":
            # Hem kind hem mail_type kontrol edelim
            query = query.filter(db.or_(MailLog.kind == m_type, MailLog.mail_type == m_type))
        
        if status:
            if status == "ok":
                query = query.filter(MailLog.ok == True)
            elif status == "error":
                query = query.filter(MailLog.ok == False)
        
        if q:
            query = query.filter(db.or_(
                MailLog.to_addr.ilike(f"%{q}%"),
                MailLog.subject.ilike(f"%{q}%"),
                MailLog.team_name.ilike(f"%{q}%")
            ))

        paginated = query.order_by(MailLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        
        logs = []
        for row in paginated.items:
            logs.append({
                "id": row.id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "kind": row.kind,
                "mail_type": getattr(row, "mail_type", row.kind),
                "ok": row.ok,
                "to_addr": row.to_addr,
                "subject": row.subject,
                "team_name": row.team_name,
                "error": row.error,
                "error_code": getattr(row, "error_code", None),
                "attachments_count": getattr(row, "attachments_count", 0),
            })
            
        return jsonify({
            "ok": True,
            "logs": logs,
            "total": paginated.total,
            "page": paginated.page,
            "pages": paginated.pages
        })
    except Exception as e:
        log.exception("Mail log API hatasi")
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.get("/api/mail/logs/<int:log_id>")
@admin_required
def api_get_mail_log_detail(log_id):
    try:
        log_entry = MailLog.query.get(log_id)
        if not log_entry:
            return jsonify({"ok": False, "error": "Log not found"}), 404
            
        data = {
            "id": log_entry.id,
            "created_at": log_entry.created_at.isoformat() if log_entry.created_at else None,
            "kind": log_entry.kind,
            "mail_type": getattr(log_entry, "mail_type", log_entry.kind),
            "ok": log_entry.ok,
            "to_addr": log_entry.to_addr,
            "cc_addr": getattr(log_entry, "cc_addr", None),
            "bcc_addr": getattr(log_entry, "bcc_addr", None),
            "subject": log_entry.subject,
            "body_preview": getattr(log_entry, "body_preview", None),
            "body_html": getattr(log_entry, "body_html", None),  # Tam HTML iÃ§erik
            "body_size_bytes": getattr(log_entry, "body_size_bytes", 0),
            "attachments_count": getattr(log_entry, "attachments_count", 0),
            "error": log_entry.error,
            "error_code": getattr(log_entry, "error_code", None),
            "team_name": log_entry.team_name,
            "user_id": log_entry.user_id,
            "project_id": log_entry.project_id,
        }
        return jsonify({"ok": True, "log": data})
    except Exception as e:
        log.exception(f"Mail log detail error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.post("/api/mail/logs/resend/<int:log_id>")
@admin_required
def api_mail_log_resend(log_id: int):
    """Mail logunu yeniden gÃ¶nder (dÃ¼zenlenmiÅŸ iÃ§erikle)"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        mail_log = MailLog.query.get_or_404(log_id)
        
        # Yeni alÄ±cÄ±/konu bilgisi
        new_to = data.get("to_addr", mail_log.to_addr)
        new_subject = data.get("subject", mail_log.subject)
        new_cc = data.get("cc_addr", mail_log.cc_addr)
        
        # HTML body - dÃ¼zenlenmiÅŸ veya orijinal
        new_body_html = data.get("body_html")
        if not new_body_html:
            # Orijinal body_html varsa kullan, yoksa body_preview'den oluÅŸtur
            original_html = getattr(mail_log, "body_html", None)
            if original_html:
                new_body_html = original_html
            else:
                # Fallback: body_preview'den basit HTML oluÅŸtur
                new_body_html = f"""<!DOCTYPE html>
<html><body style="font-family: Arial, sans-serif; line-height: 1.6; padding: 20px;">
<h2>{new_subject}</h2>
<div style="white-space: pre-wrap;">{mail_log.body_preview or ''}</div>
<hr>
<p style="color: #666; font-size: 12px;">Bu mail yeniden gÃ¶nderildi. Orijinal gÃ¶nderim: {mail_log.created_at}</p>
</body></html>"""
        
        from services.mail_service import MailService
        
        # Meta bilgisini al
        meta = {}
        if mail_log.meta_json:
            import json
            try:
                meta = json.loads(mail_log.meta_json)
            except:
                pass
        
        ok = MailService.send(
            mail_type=mail_log.mail_type or "resend",
            recipients=new_to,
            subject=new_subject,
            html=new_body_html,
            cc=new_cc,
            user_id=session.get("user_id"),
            meta={
                **meta,
                "resend_of": mail_log.id,
                "original_subject": mail_log.subject,
            }
        )
        
        if ok:
            return jsonify({"ok": True, "message": "Mail baÅŸarÄ±yla yeniden gÃ¶nderildi"})
        else:
            return jsonify({"ok": False, "error": "Mail gÃ¶nderimi baÅŸarÄ±sÄ±z"}), 500
            
    except Exception as e:
        log.exception("Mail yeniden gÃ¶nderme hatasÄ±")
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.post("/api/mail/logs/delete/<int:log_id>")
@admin_required
def api_mail_log_delete(log_id: int):
    """Mail logunu sil"""
    try:
        log = MailLog.query.get_or_404(log_id)
        db.session.delete(log)
        db.session.commit()
        return jsonify({"ok": True, "message": "Log silindi"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.post("/api/mail/logs/bulk-resend")
@admin_required
def api_mail_logs_bulk_resend():
    """Birden fazla baÅŸarÄ±sÄ±z maili yeniden gÃ¶nder"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        log_ids = data.get("log_ids", [])
        
        if not log_ids:
            return jsonify({"ok": False, "error": "Log IDleri belirtilmedi"}), 400
        
        logs = MailLog.query.filter(MailLog.id.in_(log_ids)).all()
        results = []
        
        from services.mail_service import MailService
        
        for log in logs:
            try:
                meta = {}
                if log.meta_json:
                    import json
                    try:
                        meta = json.loads(log.meta_json)
                    except:
                        pass
                
                body_html = f"""<!DOCTYPE html>
<html><body style="font-family: Arial, sans-serif; line-height: 1.6; padding: 20px;">
<h2>{log.subject}</h2>
<div style="white-space: pre-wrap;">{log.body_preview or ''}</div>
<hr>
<p style="color: #666; font-size: 12px;">Toplu yeniden gÃ¶nderim. Orijinal: {log.created_at}</p>
</body></html>"""
                
                ok = MailService.send(
                    mail_type=log.mail_type or "resend",
                    recipients=log.to_addr,
                    subject=log.subject,
                    html=body_html,
                    cc=log.cc_addr,
                    user_id=session.get("user_id"),
                    meta={
                        **meta,
                        "bulk_resend_of": log.id,
                    }
                )
                
                results.append({
                    "log_id": log.id,
                    "to": log.to_addr,
                    "ok": ok,
                    "subject": log.subject
                })
                
            except Exception as ex:
                results.append({
                    "log_id": log.id,
                    "to": log.to_addr,
                    "ok": False,
                    "error": str(ex),
                    "subject": log.subject
                })
        
        success_count = sum(1 for r in results if r.get("ok"))
        return jsonify({
            "ok": True,
            "results": results,
            "success_count": success_count,
            "total_count": len(results)
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.get("/admin/mail-log/<int:log_id>")
@admin_required
def view_mail_log(log_id: int):
    log_entry = MailLog.query.get_or_404(log_id)
    return render_template("mail_log_detail.html", log=log_entry)

@admin_bp.get("/admin/fix-db")
@admin_required
def admin_fix_db():
    try:
        from sqlalchemy import text
        # Manuel migrasyon tetikleyici
        # MailLog eksik kolonlarÄ±
        try:
            with db.session.begin():
                # Check existing columns
                res = db.session.execute(text("PRAGMA table_info(mail_log)"))
                cols = [r[1] for r in res.fetchall()]
                
                new_cols = [
                    ("mail_type", "VARCHAR(50)"),
                    ("error_code", "VARCHAR(50)"),
                    ("cc_addr", "TEXT"),
                    ("bcc_addr", "TEXT"),
                    ("body_preview", "TEXT"),
                    ("body_html", "TEXT"),  # Tam HTML iÃ§erik
                    ("attachments_count", "INTEGER DEFAULT 0"),
                    ("body_size_bytes", "INTEGER DEFAULT 0"),
                    ("sent_at", "DATETIME"),
                    ("user_id", "INTEGER"),
                    ("project_id", "INTEGER"),
                    ("job_id", "INTEGER"),
                    ("task_id", "INTEGER"),
                    ("team_id", "INTEGER"),
                    ("week_start", "DATE")
                ]
                
                for col, dtype in new_cols:
                    if col not in cols:
                        db.session.execute(text(f"ALTER TABLE mail_log ADD COLUMN {col} {dtype}"))
                        
                # Update existing mail_type from kind if null
                if "mail_type" in cols or "mail_type" in [x[0] for x in new_cols]:
                     db.session.execute(text("UPDATE mail_log SET mail_type = kind WHERE mail_type IS NULL"))

        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
            
        return jsonify({"ok": True, "msg": "Veritabani semasi guncellendi."})
    except Exception as e:
         return jsonify({"ok": False, "error": f"Genel hata: {e}"}), 500


# ---------- MAIL TEMPLATES API (ADMIN) ----------
# NOT: Mail ÅŸablon sistemi kaldÄ±rÄ±ldÄ± (09.02.2026).
# ArtÄ±k sabit HTML ÅŸablonlarÄ± utils.py'de fonksiyon olarak tanÄ±mlÄ±:
# - render_task_created_email()
# - render_task_status_changed_email()
# - render_task_comment_email()
# - render_task_reminder_email()
# - render_task_deadline_expired_email()
# - render_weekly_plan_email()
# - render_team_report_email()
# - render_job_assignment_email()
# - render_test_email()

@admin_bp.before_request
def _csrf_protect_admin_posts():
    # Protect admin form posts (best-effort). JSON API endpoints are excluded.
    if request.method != "POST":
        return None
    if request.path.startswith("/api/"):
        return None
    if not (request.path.startswith("/admin/") or request.path == "/mail/settings"):
        return None
    if request.is_json:
        return None
    token = (request.form.get("csrf_token") or "").strip()
    if not _csrf_verify(token):
        flash("CSRF dogrulamasi basarisiz. Sayfayi yenileyip tekrar deneyin.", "danger")
        return redirect(request.referrer or url_for('planner.plan_week'))

def kivanc_required(f):
    """Decorator to require kivanc username for routes (only kivanc can access)"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        # Check if user is kivanc by email, username, or is_super_admin
        current_user = get_current_user()
        is_kivanc = False
        if current_user:
            if hasattr(current_user, 'is_super_admin') and current_user.is_super_admin:
                is_kivanc = True
            elif current_user.email == 'kivancozcan@netmon.com.tr' or current_user.username == 'kivanc':
                is_kivanc = True
        if not is_kivanc:
            flash("Bu sayfaya erişim yetkiniz yok.", "danger")
            return redirect(url_for('planner.plan_week'))
        return f(*args, **kwargs)
    return decorated_function


# ---------- FILES (UPLOAD/DOWNLOAD) ----------
@admin_bp.get("/files/<path:filename>")
@login_required
def download_file(filename: str):
    try:
        return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
    except Exception:
        flash("Dosya bulunamadı.", "danger")
        return redirect(request.referrer or url_for('planner.plan_week'))


@admin_bp.get("/files/view/<path:filename>")
@login_required
def view_file_inline(filename: str):
    try:
        return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, as_attachment=False)
    except Exception:
        flash("Dosya bulunamadi.", "danger")
        return redirect(request.referrer or url_for('planner.plan_week'))


@admin_bp.get("/admin/mail-logs/export")
@admin_required
def export_mail_logs():
    import io
    from openpyxl import Workbook
    from datetime import datetime
    
    # Simple export of all recent logs (limit 1000 for now)
    try:
        logs = MailLog.query.order_by(MailLog.created_at.desc()).limit(1000).all()
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Mail Loglari"
        
        headers = ["ID", "Tarih", "Tür", "Durum", "Alıcı", "Konu", "Hata Detayı"]
        ws.append(headers)
        
        for log in logs:
            ws.append([
                log.id,
                log.created_at,
                f"{log.mail_type} ({log.kind})",
                "Başarılı" if log.ok else "Hata",
                log.to_addr,
                log.subject,
                log.error or ""
            ])
        
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        
        fname = f"mail_logs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return send_file(
            out,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=fname
        )
    except Exception as e:
        flash(f"Excel oluşturma hatası: {e}", "danger")
        return redirect(url_for('admin.mail_settings_page'))

