from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from extensions import db
from models import MailQueue
from services.mail_service import MailService
from utils import admin_required
from datetime import datetime

admin_mq_bp = Blueprint('admin_mq', __name__)

@admin_mq_bp.get("/admin/mail-queue")
@admin_required
def mail_queue_page():
    try:
        pending = MailQueue.query.filter(MailQueue.status.in_(['pending', 'processing'])).order_by(MailQueue.priority.desc(), MailQueue.created_at.asc()).all()
        # Failed but might retry
        failed = MailQueue.query.filter_by(status='failed').order_by(MailQueue.created_at.desc()).limit(50).all()
        # Sent
        sent = MailQueue.query.filter_by(status='sent').order_by(MailQueue.processed_at.desc()).limit(50).all()
    except Exception as e:
        if "no such table" in str(e).lower():
            flash("MailQueue tablosu henüz oluşturulmamış.", "warning")
        else:
            flash(f"Kuyruk verisi alınamadı: {e}", "danger")
        pending, failed, sent = [], [], []

    return render_template(
        "admin_mail_queue.html",
        pending=pending,
        failed=failed,
        sent=sent,
        now=datetime.now()
    )

@admin_mq_bp.post("/admin/mail-queue/process")
@admin_required
def mail_queue_process():
    try:
        # Manuel tetikleme
        MailService.process_queue(current_app._get_current_object())
        flash("Kuyruk işleme komutu gönderildi.", "success")
    except Exception as e:
        flash(f"İşlem hatası: {e}", "danger")
    return redirect(url_for('admin_mq.mail_queue_page'))

@admin_mq_bp.post("/admin/mail-queue/retry/<int:mq_id>")
@admin_required
def mail_queue_retry(mq_id):
    try:
        mq = db.session.get(MailQueue, mq_id)
        if mq:
            mq.status = 'pending'
            mq.retry_count = 0
            mq.error_message = None
            db.session.commit()
            flash(f"Mail ID {mq_id} tekrar kuyruğa alındı.", "success")
        else:
            flash("Kayıt bulunamadı", "warning")
    except Exception as e:
        flash(f"Hata: {e}", "danger")
    return redirect(url_for('admin_mq.mail_queue_page'))

@admin_mq_bp.post("/admin/mail-queue/delete/<int:mq_id>")
@admin_required
def mail_queue_delete(mq_id):
    try:
        mq = db.session.get(MailQueue, mq_id)
        if mq:
            db.session.delete(mq)
            db.session.commit()
            flash(f"Mail ID {mq_id} silindi.", "success")
        else:
            flash("Kayıt bulunamadı", "warning")
    except Exception as e:
        flash(f"Hata: {e}", "danger")
    return redirect(url_for('admin_mq.mail_queue_page'))

@admin_mq_bp.post("/admin/mail-queue/clear-failed")
@admin_required
def mail_queue_clear_failed():
    try:
        MailQueue.query.filter_by(status='failed').delete()
        db.session.commit()
        flash("Tüm hatalı kayıtlar temizlendi.", "success")
    except Exception as e:
        flash(f"Hata: {e}", "danger")
    return redirect(url_for('admin_mq.mail_queue_page'))
