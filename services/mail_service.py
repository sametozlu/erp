import logging
import re
import json
import base64
import time
from datetime import datetime, timedelta
from threading import Thread
from typing import List, Optional, Sequence, Union, Dict, Any

try:
    import os
except Exception:
    os = None

from utils import (
    send_email_smtp,
    create_mail_log,
    MailSendError,
    _mail_error_meta_from_exc,
)

log = logging.getLogger(__name__)


def _normalize_emails(value: Union[str, Sequence[str], None]) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        parts = [x.strip() for x in value.split(",") if x.strip()]
        return parts
    return [str(x).strip() for x in value if str(x).strip()]


def _parse_stored_list(value) -> List[str]:
    """
    Parse DB stored recipients/cc/bcc which should be JSON list, but may be a legacy
    Python list string like "['a@b.com']".
    """
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return _normalize_emails(value)
    s = str(value).strip()
    if not s:
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, (list, tuple, set)):
            return _normalize_emails(parsed)
    except Exception:
        pass
    try:
        import ast

        parsed = ast.literal_eval(s)
        if isinstance(parsed, (list, tuple, set)):
            return _normalize_emails(parsed)
    except Exception:
        pass
    # fallback: treat as comma-separated string
    return _normalize_emails(s)


def _is_permanent_send_error(exc: Exception) -> bool:
    """
    Decide whether retrying is pointless.
    - recipient/address syntax errors (501/5.1.3) will never succeed without data change
    - auth/config issues are also permanent until settings change
    """
    if isinstance(exc, MailSendError):
        return exc.code in {
            "recipient_refused",
            "recipient",
            "from_refused",
            "authentication",
            "config",
        }
    return False


def _format_queue_error(exc: Exception) -> str:
    try:
        if isinstance(exc, MailSendError):
            detail = (exc.debug_detail or "").strip()
            if detail:
                return f"{exc.user_message} ({exc.code}) {detail}"
            return f"{exc.user_message} ({exc.code})"
        return str(exc) or type(exc).__name__
    except Exception:
        return str(exc) or "unknown"


def _try_acquire_worker_lock(app) -> bool:
    """
    Best-effort inter-process lock so we don't start multiple mail workers.
    Uses a file lock under instance_path.
    """
    try:
        if getattr(app, "config", {}).get("TESTING"):
            return False

        if os is None:
            return True

        instance_path = getattr(app, "instance_path", None) or "instance"
        os.makedirs(instance_path, exist_ok=True)
        lock_path = os.path.join(instance_path, "mail_worker.lock")

        f = open(lock_path, "a+")
        # store handle on app to keep lock alive
        setattr(app, "_mail_worker_lock_handle", f)

        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                return False
        else:
            import fcntl

            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except OSError:
                return False
    except Exception:
        # If locking fails for any unexpected reason, don't block the app from starting.
        return True


class MailService:
    """
    Central mail sender + logger with Queue support.
    
    Mail şablon sistemi kaldırıldı. Artık sabit HTML şablonları utils.py'de tanımlı.
    Asenkron gönderim için MailQueue kullanılır.
    """

    @staticmethod
    def _preview(html: str, limit: int = 1200) -> str:
        if not html:
            return ""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:limit]

    @staticmethod
    def _body_size(html: str) -> int:
        return len((html or "").encode("utf-8"))

    @staticmethod
    def send(
        *,
        mail_type: str,
        recipients: Union[str, Sequence[str]],
        subject: str,
        html: str,
        attachments: Optional[List[dict]] = None,
        cc: Union[str, Sequence[str], None] = None,
        bcc: Union[str, Sequence[str], None] = None,
        context: Optional[dict] = None,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        job_id: Optional[int] = None,
        task_id: Optional[int] = None,
        team_name: Optional[str] = None,
        week_start=None,
        meta: Optional[Dict[str, Any]] = None,
        cfg_override: Optional[dict] = None,
    ):
        """
        Maili kuyruğa ekler (Asenkron gönderim).
        """
        from extensions import db
        from models import MailQueue

        rcpt_list = _normalize_emails(recipients)
        if not rcpt_list:
            log.warning(f"MailQueue: Alıcı listesi boş, mail kuyruğa eklenmedi. Subject: {subject}")
            return False

        try:
            # Attachment'ları serialize et (varsa)
            atts_data = []
            if attachments:
                for att in attachments:
                    try:
                        # binary veriyi base64 string'e çevir
                        data_b64 = None
                        if att.get("data"):
                            data_b64 = base64.b64encode(att["data"]).decode("utf-8")
                        
                        atts_data.append({
                            "filename": att.get("filename"),
                            "content_type": att.get("content_type"),
                            "data_b64": data_b64
                        })
                    except Exception as e:
                        log.error(f"Attachment serialization error: {e}")

            # Meta verisini hazırla
            meta_final = meta or {}
            if atts_data:
                meta_final["_attachments"] = atts_data
            
            # Diğer opsiyonel alanları meta içinde sakla (week_start, team_name vb. loglama için gerekli olabilir)
            if week_start:
                meta_final["_week_start"] = str(week_start)
            if team_name:
                meta_final["_team_name"] = team_name
            if cfg_override:
                meta_final["_cfg_override"] = cfg_override

            # Kuyruğa ekle
            mq = MailQueue(
                mail_type=mail_type,
                recipients=json.dumps(rcpt_list, ensure_ascii=False),
                subject=subject,
                html_content=html,
                cc=json.dumps(_normalize_emails(cc), ensure_ascii=False) if cc else None,
                bcc=json.dumps(_normalize_emails(bcc), ensure_ascii=False) if bcc else None,
                meta_json=json.dumps(meta_final, ensure_ascii=False),
                user_id=user_id,
                project_id=project_id,
                job_id=job_id,
                task_id=task_id,
                status="pending",
                created_at=datetime.now(),
                retry_count=0
            )
            
            db.session.add(mq)
            db.session.commit()
            return True
            
        except Exception as e:
            log.exception(f"MailQueue insert failed: {e}")
            return False

    @staticmethod
    def process_queue(app):
        """
        Kuyruktaki pending mailleri işler.
        """
        with app.app_context():
            from extensions import db
            from models import MailQueue
            from sqlalchemy import text as _sql_text

            # Pending veya Retry durumundaki mailleri al (En eski 5 tane)
            # Basit kilitleme mekanizması: status='processing' yapacağız.
            # Race condition ihtimali var ama tek worker olduğu sürece sorun yok.
            
            try:
                # --- RECOVERY ---
                # 5 dakikadan uzun süredir 'processing' durumunda kalanları kurtar
                timeout_threshold = datetime.now() - timedelta(minutes=5)
                stuck_items = MailQueue.query.filter(
                    MailQueue.status == 'processing',
                    (MailQueue.processed_at < timeout_threshold) | (MailQueue.processed_at == None)
                ).all()
                
                if stuck_items:
                    log.warning(f"MailQueue: Recovering {len(stuck_items)} stuck items.")
                    for item in stuck_items:
                        item.error_message = f"Timeout/Crash recovery. Last status: {item.status}"
                        item.retry_count += 1
                        if item.retry_count < 3:
                            item.status = 'pending' # Tekrar dene
                        else:
                            item.status = 'failed'
                    db.session.commit()

                # Retry zamanı gelmiş olanları da al (basit mantık: failed ve retry_count < 3)
                # Şimdilik sadece pending'e odaklanalım veya failed olup retry hakkı olanları pending'e çeken ayrı bir job yapabiliriz.
                # Basitlik adına: Sadece 'pending' olanları al.
                # IMPORTANT: Claim items atomically to avoid double-send if multiple workers exist.
                # We select candidates, then update with status='pending' guard. Only claimed rows are processed.
                candidates = (
                    MailQueue.query.filter_by(status="pending")
                    .order_by(MailQueue.priority.desc(), MailQueue.created_at.asc())
                    .limit(5)
                    .all()
                )

                if not candidates:
                    return

                now = datetime.now()
                claimed_ids = []
                for it in candidates:
                    try:
                        res = db.session.execute(
                            _sql_text(
                                "UPDATE mail_queue "
                                "SET status='processing', processed_at=:now "
                                "WHERE id=:id AND status='pending'"
                            ),
                            {"now": now, "id": int(it.id)},
                        )
                        if getattr(res, "rowcount", 0) == 1:
                            claimed_ids.append(int(it.id))
                    except Exception:
                        # If claim fails for a row, skip it rather than risking double-send.
                        continue

                db.session.commit()

                if not claimed_ids:
                    return

                queue_items = (
                    MailQueue.query.filter(MailQueue.id.in_(claimed_ids))
                    .order_by(MailQueue.priority.desc(), MailQueue.created_at.asc())
                    .all()
                )

                for item in queue_items:
                    try:
                        # Verileri hazırla
                        recipients = _parse_stored_list(item.recipients)
                        cc = _parse_stored_list(item.cc) if item.cc else []
                        bcc = _parse_stored_list(item.bcc) if item.bcc else []
                        meta = json.loads(item.meta_json) if item.meta_json else {}
                        
                        # Attachment'ları deserialize et
                        attachments = []
                        if meta.get("_attachments"):
                            for att in meta["_attachments"]:
                                if att.get("data_b64"):
                                    attachments.append({
                                        "filename": att.get("filename"),
                                        "content_type": att.get("content_type"),
                                        "data": base64.b64decode(att["data_b64"])
                                    })
                        
                        cfg_override = meta.get("_cfg_override")
                        
                        # Gönder
                        # send_email_smtp loglama yapmaz, exception fırlatır.
                        send_email_smtp(
                            # Always pass a comma separated string to avoid list->str bugs
                            to_addr=",".join(_normalize_emails(recipients)),
                            subject=item.subject,
                            html_body=item.html_content,
                            attachments=attachments,
                            cc_addrs=",".join(_normalize_emails(cc)) if cc else None,
                            bcc_addrs=",".join(_normalize_emails(bcc)) if bcc else None,
                            cfg_override=cfg_override
                        )
                        
                        # Başarılı -> önce status'u kalıcı hale getir, sonra logla.
                        item.status = 'sent'
                        item.error_message = None
                        try:
                            db.session.commit()
                        except Exception:
                            try:
                                db.session.rollback()
                            except Exception:
                                pass
                            # If we cannot persist status, don't log (it could cause retries/double-send).
                            continue

                        create_mail_log(
                            kind="send",
                            ok=True,
                            to_addr=",".join(recipients),
                            subject=item.subject,
                            mail_type=item.mail_type,
                            body_preview=MailService._preview(item.html_content),
                            body_size=MailService._body_size(item.html_content),
                            cc_addrs=",".join(cc) if cc else None,
                            user_id=item.user_id,
                            project_id=item.project_id,
                            job_id=item.job_id,
                            task_id=item.task_id,
                            meta=meta
                        )

                    except Exception as e:
                        # Başarısız -> Logla ve retry mantığı
                        log.error(f"MailQueue send error (ID: {item.id}): {e}")
                        item.error_message = _format_queue_error(e)

                        permanent = _is_permanent_send_error(e)
                        if permanent:
                            item.status = "failed"
                            item.retry_count = max(int(item.retry_count or 0), 3)
                        else:
                            item.retry_count += 1
                            if item.retry_count < 3:
                                item.status = "pending"
                            else:
                                item.status = "failed"

                        # Persist queue state first; mail logging must not rollback the queue update.
                        try:
                            db.session.commit()
                        except Exception:
                            try:
                                db.session.rollback()
                            except Exception:
                                pass
                            continue

                        if item.status == "failed":
                            try:
                                # Log only when we permanently fail (or retries exhausted)
                                meta_err = _mail_error_meta_from_exc(e)
                                create_mail_log(
                                    kind="send",
                                    ok=False,
                                    to_addr=",".join(_normalize_emails(recipients)) if 'recipients' in locals() else "unknown",
                                    subject=item.subject,
                                    mail_type=item.mail_type,
                                    body_preview=MailService._preview(item.html_content),
                                    body_html=item.html_content,
                                    error=meta_err.get("user_message") or str(e),
                                    meta=meta_err,
                                    user_id=item.user_id,
                                    project_id=item.project_id,
                                    job_id=item.job_id,
                                    task_id=item.task_id
                                )
                            except Exception:
                                # If logging fails, don't revert the queue status.
                                pass
                     
                    # No extra commit here: each branch commits in its own safe place.
                    
            except Exception as e:
                log.exception(f"MailQueue worker loop error: {e}")

def start_mail_worker(app):
    """
    Arka planda mail kuyruğunu işleyen thread'i başlatır.
    """
    # In-process guard: this may be called from multiple startup paths.
    # Ensure we only spawn a single worker thread per process.
    try:
        if getattr(app, "_mail_worker_started", False):
            return
    except Exception:
        pass

    # Avoid spawning workers during tests; queue can still be processed manually if needed.
    try:
        if getattr(app, "config", {}).get("TESTING"):
            log.info("MailQueue worker skipped (TESTING=1).")
            return
    except Exception:
        pass

    # Optional env-based gate (useful for multi-process deployments).
    try:
        if os is not None and str(os.getenv("MAIL_WORKER_ENABLE", "1") or "").strip() in ("0", "false", "no", "off"):
            log.info("MailQueue worker disabled via MAIL_WORKER_ENABLE=0.")
            return
    except Exception:
        pass

    # Inter-process lock (best effort). If we cannot lock, don't start another worker.
    if not _try_acquire_worker_lock(app):
        log.info("MailQueue worker not started (another process holds the lock).")
        return

    def worker():
        log.info("MailQueue worker started.")
        while True:
            try:
                MailService.process_queue(app)
            except Exception as e:
                log.error(f"MailQueue worker fatal error: {e}")
            
            # 10 saniye bekle
            time.sleep(10)

    t = Thread(target=worker, daemon=True)
    t.start()
    try:
        setattr(app, "_mail_worker_started", True)
        setattr(app, "_mail_worker_thread", t)
    except Exception:
        pass
