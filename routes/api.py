from flask import Blueprint, jsonify, request, session, g, current_app
from extensions import db
from models import User, Notification
from utils import login_required, _csrf_verify, ONLINE_WINDOW, _touch_user_activity, get_current_user
from datetime import datetime
import time as _time

api_bp = Blueprint('api', __name__)

@api_bp.get("/api/notifications/unread_count")
@login_required
def api_notifications_unread_count():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "auth"}), 401
    cnt = Notification.query.filter(Notification.user_id == uid, Notification.read_at == None).count()
    return jsonify({"ok": True, "count": int(cnt or 0)})


@api_bp.get("/api/notifications/list")
@login_required
def api_notifications_list():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "auth"}), 401
    try:
        limit = int(request.args.get("limit", 20) or 20)
    except Exception:
        limit = 20
    limit = max(1, min(50, limit))

    rows = (
        Notification.query
        .filter(Notification.user_id == uid)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "event": r.event,
            "title": r.title,
            "body": r.body or "",
            "link_url": r.link_url or "",
            "job_id": r.job_id,
            "mail_log_id": r.mail_log_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "read": bool(r.read_at),
            "read_at": r.read_at.isoformat() if r.read_at else None,
        })

    return jsonify({"ok": True, "items": items})


@api_bp.post("/api/notifications/mark_read")
@login_required
def api_notifications_mark_read():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "auth"}), 401

    data = request.get_json(force=True, silent=True) or {}
    token = str(data.get("csrf_token") or "")
    if not _csrf_verify(token):
        return jsonify({"ok": False, "error": "CSRF dogrulamasi basarisiz."}), 400

    mark_all = bool(data.get("all"))
    ids = data.get("ids") or []
    if not isinstance(ids, list):
        ids = []
    ids = [int(x) for x in ids if str(x).isdigit()]

    now = datetime.now()
    try:
        q = Notification.query.filter(Notification.user_id == uid)
        if not mark_all:
            if not ids:
                return jsonify({"ok": True, "updated": 0})
            q = q.filter(Notification.id.in_(ids))
        updated = q.update({Notification.read_at: now}, synchronize_session=False)
        db.session.commit()
        return jsonify({"ok": True, "updated": int(updated or 0)})
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": "Guncelleme hatasi"}), 500

@api_bp.post("/api/heartbeat")
@login_required
def api_heartbeat():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"ok": False, "error": "auth"}), 401
    try:
        user = User.query.get(uid)
        if not user:
            return jsonify({"ok": False, "error": "user"}), 404
        now = datetime.now()
        ok = _touch_user_activity(user, now=now)
        if ok:
            session["_last_seen_touch_ts"] = now.timestamp()
        return jsonify({"ok": True})
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": "heartbeat_failed"}), 500


@api_bp.get("/api/online_users")
@login_required
def api_online_users():
    viewer = get_current_user()
    if not viewer:
        return jsonify({"ok": False, "error": "auth"}), 401

    only_online_raw = (request.args.get("only_online") or "").strip().lower()
    only_online = only_online_raw in ("1", "true", "yes", "on")

    now = datetime.now()
    cutoff = now - ONLINE_WINDOW

    q = User.query.filter(User.is_active == True)
    items = []
    try:
        rows = q.order_by(User.full_name.asc().nullslast(), User.email.asc()).all()
    except Exception:
        rows = q.order_by(User.email.asc()).all()

    for u in rows:
        last_seen = getattr(u, "last_seen", None)
        online_since = getattr(u, "online_since", None)
        is_online = bool(last_seen and last_seen >= cutoff)

        if only_online and not is_online:
            continue

        online_for_sec = None
        if is_online and online_since:
            try:
                online_for_sec = int((now - online_since).total_seconds())
            except Exception:
                online_for_sec = None

        payload = {
            "id": int(u.id),
            "name": (u.full_name or u.email or u.username or "").strip() or f"User {u.id}",
            "role": (u.role or "").strip() or "user",
            "is_online": bool(is_online),
        }

        if bool(viewer.is_admin):
            payload.update({
                "email": u.email or "",
                "last_seen": last_seen.isoformat() if last_seen else None,
                "online_since": online_since.isoformat() if online_since else None,
                "online_for_sec": online_for_sec,
            })

        items.append(payload)

    online_count = sum(1 for it in items if it.get("is_online"))
    return jsonify({
        "ok": True,
        "window_sec": int(ONLINE_WINDOW.total_seconds()),
        "online_count": int(online_count),
        "items": items,
    })


# ---------- CHAT (Users) ----------
