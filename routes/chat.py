from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, g, current_app
from extensions import db, socketio
from flask_socketio import join_room
from models import User, ChatMessage, ChatUserMessage, Announcement, AnnouncementRead, Team
from utils import login_required, get_current_user, _fetch_announcements, ONLINE_WINDOW, _is_user_online, _user_is_admin_or_planner, _can_access_chat_team, planner_or_admin_required, _csrf_verify
from datetime import datetime
from sqlalchemy import or_, and_, desc, func
from typing import Optional

chat_bp = Blueprint('chat', __name__)

def _chat_pair_key(a: int, b: int) -> str:
    try:
        a = int(a or 0)
    except Exception:
        a = 0
    try:
        b = int(b or 0)
    except Exception:
        b = 0
    if a <= 0 or b <= 0:
        return ""
    lo = min(a, b)
    hi = max(a, b)
    return f"{lo}:{hi}"


def _is_user_online(user_obj: "User", *, now: Optional[datetime] = None) -> bool:
    if not user_obj:
        return False
    now = now or datetime.now()
    cutoff = now - ONLINE_WINDOW
    last_seen = getattr(user_obj, "last_seen", None)
    return bool(last_seen and last_seen >= cutoff)


@chat_bp.get("/chat")
@login_required
def chat_redirect():
    """
    Backward-compatible entry; main chat is /chat/users.
    """
    try:
        return redirect(url_for("chat_page", **(request.args or {})))
    except Exception:
        return redirect(url_for('chat.chat_page'))


@chat_bp.get("/chat/users")
@login_required
def chat_page():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    now = datetime.now()
    cutoff = now - ONLINE_WINDOW
    try:
        rows = User.query.filter(User.is_active == True, User.id != int(user.id)).order_by(User.full_name.asc().nullslast(), User.email.asc()).all()
    except Exception:
        rows = User.query.filter(User.is_active == True, User.id != int(user.id)).order_by(User.email.asc()).all()

    items = []
    for u in rows:
        last_seen = getattr(u, "last_seen", None)
        is_online = bool(last_seen and last_seen >= cutoff)
        items.append({
            "id": int(u.id),
            "name": (u.full_name or u.email or u.username or "").strip() or f"User {u.id}",
            "role": (u.role or "").strip() or "user",
            "is_online": bool(is_online),
        })
    items.sort(key=lambda it: (not bool(it.get("is_online")), (it.get("name") or "").lower()))

    online_users = [it for it in items if it.get("is_online")]
    offline_users = [it for it in items if not it.get("is_online")]

    try:
        selected_user_id = int(request.args.get("user_id", 0) or 0)
    except Exception:
        selected_user_id = 0

    allowed_ids = {int(it.get("id") or 0) for it in items if it and it.get("id")}
    if allowed_ids and selected_user_id not in allowed_ids:
        try:
            selected_user_id = int(items[0].get("id") or 0)
        except Exception:
            selected_user_id = 0
    if not allowed_ids:
        selected_user_id = 0

    announcements_preview = []
    announcements_unread = 0
    try:
        announcements_preview = _fetch_announcements(user, limit=5)
        announcements_unread = sum(1 for a in announcements_preview if not a.get("is_read"))
    except Exception:
        announcements_preview = []
        announcements_unread = 0

    return render_template(
        "chat.html",
        user=user,
        online_users=online_users,
        offline_users=offline_users,
        selected_user_id=selected_user_id,
        online_window_sec=int(ONLINE_WINDOW.total_seconds()),
        announcements_preview=announcements_preview,
        announcements_unread_count=announcements_unread,
    )


@chat_bp.get("/api/chat/users")
@login_required
def api_chat_users():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401

    q_text = (request.args.get("q") or "").strip().lower()
    only_online_raw = (request.args.get("only_online") or "").strip().lower()
    only_online = only_online_raw in ("1", "true", "yes", "on")

    now = datetime.now()
    cutoff = now - ONLINE_WINDOW
    try:
        rows = User.query.filter(User.is_active == True, User.id != int(user.id)).order_by(User.full_name.asc().nullslast(), User.email.asc()).all()
    except Exception:
        rows = User.query.filter(User.is_active == True, User.id != int(user.id)).order_by(User.email.asc()).all()

    items = []
    for u in rows:
        name = (u.full_name or u.email or u.username or "").strip() or f"User {u.id}"
        if q_text and q_text not in name.lower():
            continue
        last_seen = getattr(u, "last_seen", None)
        is_online = bool(last_seen and last_seen >= cutoff)
        if only_online and not is_online:
            continue
        items.append({
            "id": int(u.id),
            "name": name,
            "role": (u.role or "").strip() or "user",
            "is_online": bool(is_online),
        })
    items.sort(key=lambda it: (not bool(it.get("is_online")), (it.get("name") or "").lower()))
    online_count = sum(1 for it in items if it.get("is_online"))
    return jsonify({
        "ok": True,
        "items": items,
        "window_sec": int(ONLINE_WINDOW.total_seconds()),
        "online_count": int(online_count),
        "total": int(len(items)),
    })


@chat_bp.get("/api/chat/messages")
@login_required
def api_chat_messages():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401

    try:
        other_user_id = int(request.args.get("user_id", 0) or 0)
    except Exception:
        other_user_id = 0
    if other_user_id <= 0 or int(other_user_id) == int(user.id):
        return jsonify({"ok": False, "error": "user_id_invalid"}), 400

    other = User.query.get(other_user_id)
    if not other or not bool(getattr(other, "is_active", True)):
        return jsonify({"ok": False, "error": "user_not_found"}), 404

    pair_key = _chat_pair_key(int(user.id), int(other_user_id))
    if not pair_key:
        return jsonify({"ok": False, "error": "pair_invalid"}), 400

    try:
        limit = int(request.args.get("limit", 200) or 200)
    except Exception:
        limit = 200
    limit = max(1, min(200, limit))

    try:
        after_id = int(request.args.get("after_id", 0) or 0)
    except Exception:
        after_id = 0

    q = (
        db.session.query(ChatUserMessage, User)
        .join(User, User.id == ChatUserMessage.from_user_id)
        .filter(ChatUserMessage.pair_key == pair_key)
    )
    if after_id > 0:
        q = q.filter(ChatUserMessage.id > after_id)

    rows = q.order_by(ChatUserMessage.id.desc()).limit(limit).all()
    rows = list(reversed(rows))

    items = []
    for m, u in rows:
        name = (u.full_name or u.email or u.username or "").strip() or f"User {u.id}"
        items.append({
            "id": int(m.id),
            "pair_key": pair_key,
            "from_user_id": int(m.from_user_id),
            "to_user_id": int(m.to_user_id),
            "from_user_name": name,
            "text": m.text or "",
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return jsonify({"ok": True, "messages": items})


@chat_bp.post("/api/chat/send")
@login_required
def api_chat_send():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401

    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400

    try:
        to_user_id = int(data.get("to_user_id", 0) or 0)
    except Exception:
        to_user_id = 0
    if to_user_id <= 0 or int(to_user_id) == int(user.id):
        return jsonify({"ok": False, "error": "to_user_invalid"}), 400

    other = User.query.get(to_user_id)
    if not other or not bool(getattr(other, "is_active", True)):
        return jsonify({"ok": False, "error": "user_not_found"}), 404

    now = datetime.now()

    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text_required"}), 400
    if len(text) > 2000:
        return jsonify({"ok": False, "error": "text_too_long"}), 400

    pair_key = _chat_pair_key(int(user.id), int(to_user_id))
    if not pair_key:
        return jsonify({"ok": False, "error": "pair_invalid"}), 400

    m = ChatUserMessage(pair_key=pair_key, from_user_id=int(user.id), to_user_id=int(to_user_id), text=text, created_at=now)
    db.session.add(m)
    db.session.commit()

    payload = {
        "id": int(m.id),
        "pair_key": pair_key,
        "from_user_id": int(user.id),
        "to_user_id": int(to_user_id),
        "from_user_name": (user.full_name or user.email or user.username or "").strip() or f"User {user.id}",
        "text": text,
        "created_at": now.isoformat(),
    }

    try:
        # Mevcut chat_message eventi
        socketio.emit("chat_message", payload, room=f"chat_user_{to_user_id}", namespace="/")
        socketio.emit("chat_message", payload, room=f"chat_user_{int(user.id)}", namespace="/")

        # Yeni GÖREV gereği new_message eventi
        new_msg_payload = {
            "sender": (user.full_name or user.email or user.username or "").strip() or f"User {user.id}",
            "text": text,
            "from_user_id": int(user.id),
            "to_user_id": int(to_user_id),
            "created_at": now.isoformat()
        }
        # Hem alıcıya hem gönderene gönderelim
        socketio.emit("new_message", new_msg_payload, room=f"user_{to_user_id}", namespace="/")
        socketio.emit("new_message", new_msg_payload, room=f"user_{int(user.id)}", namespace="/")

    except Exception as e:
        print(f"SocketIO Error: {e}")
        # Socket hatası olsa bile mesaj kaydedildi, işlem başarılı sayılmalı
        pass

    return jsonify({"ok": True, "message": payload})




@socketio.on("join_chat")
def on_join_chat():
    current_user = get_current_user()
    if current_user and current_user.is_authenticated:
        # Kullanıcıyı kendi odasına al: user_{id}
        join_room(f"user_{int(current_user.id)}")
        # Eski uyumluluk için buna da katılıyoruz (app.py vb. kullanıyorsa)
        join_room(f"chat_user_{int(current_user.id)}")



# ---------- ANNOUNCEMENTS ----------
def _announcement_is_visible_to_user(ann: "Announcement", user: "User") -> bool:
    if not ann or not user:
        return False
    if _user_is_admin_or_planner(user):
        return True
    a_type = (getattr(ann, "audience_type", "") or "").strip().lower()
    a_id = int(getattr(ann, "audience_id", 0) or 0)
    if a_type in ("", "all"):
        return True
    if a_type == "team":
        return bool(a_id) and int(getattr(user, "team_id", 0) or 0) == a_id
    if a_type == "user":
        return bool(a_id) and int(getattr(user, "id", 0) or 0) == a_id
    return False


def _announcements_query_for_user(user: "User"):
    q = Announcement.query
    if not user:
        return q.filter(False)
    if _user_is_admin_or_planner(user):
        return q

    clauses = [Announcement.audience_type.in_(["", "all"])]
    tid = int(getattr(user, "team_id", 0) or 0)
    if tid:
        clauses.append((Announcement.audience_type == "team") & (Announcement.audience_id == tid))
    clauses.append((Announcement.audience_type == "user") & (Announcement.audience_id == int(user.id)))
    return q.filter(or_(*clauses))


def _fetch_announcements(user: "User", *, limit: int = 50) -> list[dict]:
    try:
        limit = int(limit or 50)
    except Exception:
        limit = 50
    limit = max(1, min(200, limit))

    rows = (
        _announcements_query_for_user(user)
        .order_by(Announcement.created_at.desc())
        .limit(limit)
        .all()
    )

    ids = [int(a.id) for a in rows if a and getattr(a, "id", None)]
    read_ids = set()
    if ids and user:
        for (aid,) in (
            db.session.query(AnnouncementRead.announcement_id)
            .filter(AnnouncementRead.user_id == int(user.id), AnnouncementRead.announcement_id.in_(ids))
            .distinct()
            .all()
        ):
            if aid:
                read_ids.add(int(aid))

    out = []
    for a in rows:
        creator = getattr(a, "created_by", None)
        creator_name = ""
        if creator:
            creator_name = (creator.full_name or creator.email or creator.username or "").strip()
        out.append({
            "id": int(a.id),
            "title": (a.title or "").strip() or "Duyuru",
            "body": a.body or "",
            "created_at": a.created_at,
            "created_by_name": creator_name,
            "audience_type": (a.audience_type or "").strip().lower() or "all",
            "audience_id": int(a.audience_id or 0) if getattr(a, "audience_id", None) else 0,
            "is_read": bool(int(a.id) in read_ids),
        })
    return out


@chat_bp.get("/announcements")
@login_required
def announcements_page():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    items = _fetch_announcements(user, limit=200)
    unread_count = sum(1 for a in items if not a.get("is_read"))
    return render_template("announcements.html", user=user, announcements=items, unread_count=unread_count)


@chat_bp.post("/api/announcements/<int:announcement_id>/read")
@login_required
def api_announcement_mark_read(announcement_id: int):
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401

    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400

    ann = Announcement.query.get(int(announcement_id or 0))
    if not ann:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if not _announcement_is_visible_to_user(ann, user):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    try:
        row = AnnouncementRead.query.filter_by(announcement_id=int(ann.id), user_id=int(user.id)).first()
        if not row:
            row = AnnouncementRead(announcement_id=int(ann.id), user_id=int(user.id), read_at=datetime.now())
            db.session.add(row)
        else:
            row.read_at = datetime.now()
            db.session.add(row)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({"ok": False, "error": "db"}), 500

    return jsonify({"ok": True})


@chat_bp.route("/admin/messages", methods=["GET", "POST"])
@planner_or_admin_required
def admin_messages_page():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    if request.method == "POST":
        if not _csrf_verify((request.form.get("csrf_token") or "").strip()):
            flash("CSRF doğrulaması başarısız.", "danger")
            return redirect(url_for('chat.admin_messages_page'))

        target_type = (request.form.get("target_type") or "").strip().lower()
        title = (request.form.get("title") or "").strip()
        message = (request.form.get("message") or "").strip()
        popup_raw = (request.form.get("is_popup") or "").strip().lower()
        is_popup = popup_raw in ("1", "true", "on", "yes")

        if not message:
            flash("Mesaj boş olamaz.", "danger")
            return redirect(url_for('chat.admin_messages_page'))
        if len(message) > 2000:
            flash("Mesaj çok uzun (maksimum 2000 karakter).", "danger")
            return redirect(url_for('chat.admin_messages_page'))

        try:
            if target_type == "user":
                to_user_id = int(request.form.get("to_user_id", 0) or 0)
                if to_user_id <= 0 or int(to_user_id) == int(user.id):
                    flash("Hedef kullanıcı seçin.", "danger")
                    return redirect(url_for('chat.admin_messages_page'))
                other = User.query.get(to_user_id)
                if not other or not bool(getattr(other, "is_active", True)):
                    flash("Kullanıcı bulunamadı.", "danger")
                    return redirect(url_for('chat.admin_messages_page'))

                now = datetime.now()
                pair_key = _chat_pair_key(int(user.id), int(to_user_id))
                if not pair_key:
                    flash("Mesaj gönderilemedi.", "danger")
                    return redirect(url_for('chat.admin_messages_page'))
                m = ChatUserMessage(
                    pair_key=pair_key,
                    from_user_id=int(user.id),
                    to_user_id=int(to_user_id),
                    text=message,
                    created_at=now,
                )
                db.session.add(m)
                db.session.commit()

                try:
                    payload = {
                        "id": int(m.id),
                        "pair_key": pair_key,
                        "from_user_id": int(user.id),
                        "to_user_id": int(to_user_id),
                        "from_user_name": (user.full_name or user.email or user.username or "").strip() or f"User {user.id}",
                        "text": message,
                        "created_at": now.isoformat(),
                    }
                    socketio.emit("chat_message", payload, room=f"chat_user_{to_user_id}", namespace="/")
                    socketio.emit("chat_message", payload, room=f"chat_user_{int(user.id)}", namespace="/")
                except Exception:
                    pass

                flash("Mesaj gönderildi.", "success")
                return redirect(url_for('chat.admin_messages_page'))

            if target_type == "team":
                team_id = int(request.form.get("team_id", 0) or 0)
                if team_id <= 0:
                    flash("Hedef ekip seçin.", "danger")
                    return redirect(url_for('chat.admin_messages_page'))
                t = Team.query.get(team_id)
                if not t:
                    flash("Ekip bulunamadı.", "danger")
                    return redirect(url_for('chat.admin_messages_page'))

                a = Announcement(
                    created_by_user_id=int(user.id),
                    title=title or "Duyuru",
                    body=message,
                    audience_type="team",
                    audience_id=int(team_id),
                    is_popup=bool(is_popup),
                )
                db.session.add(a)
                db.session.commit()
                flash("Ekip duyurusu gönderildi.", "success")
                return redirect(url_for('chat.admin_messages_page'))

            if target_type == "all":
                a = Announcement(
                    created_by_user_id=int(user.id),
                    title=title or "Duyuru",
                    body=message,
                    audience_type="all",
                    audience_id=None,
                    is_popup=bool(is_popup),
                )
                db.session.add(a)
                db.session.commit()
                flash("Genel duyuru gönderildi.", "success")
                return redirect(url_for('chat.admin_messages_page'))

            flash("Hedef türü geçersiz.", "danger")
            return redirect(url_for('chat.admin_messages_page'))
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            flash("Kayıt sırasında hata oluştu.", "danger")
            return redirect(url_for('chat.admin_messages_page'))

    # GET
    try:
        users = User.query.filter(User.is_active == True).order_by(User.full_name.asc().nullslast(), User.email.asc()).all()
    except Exception:
        users = User.query.filter(User.is_active == True).order_by(User.email.asc()).all()
    teams = Team.query.order_by(Team.name.asc()).all()
    return render_template("admin_messages.html", user=user, users=users, teams=teams)


# ---------- TEAM CHAT (Rooms) ----------
@chat_bp.get("/me/chat")
@login_required
def team_chat_page():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    # Team chat is deprecated; keep only for admin/planlayıcı access.
    if not _user_is_admin_or_planner(user):
        return redirect(url_for('chat.chat_page'))

    teams = Team.query.order_by(Team.name.asc()).all()

    try:
        selected_team_id = int(request.args.get("team_id", 0) or 0)
    except Exception:
        selected_team_id = 0

    allowed_ids = {int(t.id) for t in teams if t and getattr(t, "id", None)}
    if allowed_ids and selected_team_id not in allowed_ids:
        try:
            selected_team_id = int(teams[0].id)
        except Exception:
            selected_team_id = 0
    if not allowed_ids:
        selected_team_id = 0

    return render_template(
        "team_chat.html",
        user=user,
        teams=teams,
        selected_team_id=selected_team_id,
        online_window_sec=int(ONLINE_WINDOW.total_seconds()),
        is_admin=bool(getattr(user, "is_admin", False)),
        is_planner=bool(_user_is_admin_or_planner(user) and not bool(getattr(user, "is_admin", False))),
    )


@chat_bp.get("/api/team_chat/messages")
@login_required
def api_team_chat_messages():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    if not _user_is_admin_or_planner(user):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    try:
        team_id = int(request.args.get("team_id", 0) or 0)
    except Exception:
        team_id = 0
    if not _can_access_chat_team(user, team_id=team_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    try:
        limit = int(request.args.get("limit", 200) or 200)
    except Exception:
        limit = 200
    limit = max(1, min(200, limit))

    try:
        after_id = int(request.args.get("after_id", 0) or 0)
    except Exception:
        after_id = 0

    q = (
        db.session.query(ChatMessage, User)
        .join(User, User.id == ChatMessage.user_id)
        .filter(ChatMessage.team_id == team_id)
    )
    if after_id > 0:
        q = q.filter(ChatMessage.id > after_id)

    rows = q.order_by(ChatMessage.id.desc()).limit(limit).all()
    rows = list(reversed(rows))

    items = []
    for m, u in rows:
        name = (u.full_name or u.email or u.username or "").strip() or f"User {u.id}"
        items.append({
            "id": int(m.id),
            "team_id": int(m.team_id),
            "user_id": int(m.user_id),
            "user_name": name,
            "text": m.text or "",
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return jsonify({"ok": True, "messages": items})


@chat_bp.post("/api/team_chat/send")
@login_required
def api_team_chat_send():
    user = get_current_user()
    if not user:
        return jsonify({"ok": False, "error": "auth"}), 401
    if not _user_is_admin_or_planner(user):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    data = request.get_json(force=True, silent=True) or {}
    if not _csrf_verify((data.get("csrf_token") or "").strip()):
        return jsonify({"ok": False, "error": "csrf"}), 400

    try:
        team_id = int(data.get("team_id", 0) or 0)
    except Exception:
        team_id = 0
    if not _can_access_chat_team(user, team_id=team_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text_required"}), 400
    if len(text) > 2000:
        return jsonify({"ok": False, "error": "text_too_long"}), 400

    now = datetime.now()
    m = ChatMessage(team_id=team_id, user_id=int(user.id), text=text, created_at=now)
    db.session.add(m)
    db.session.commit()

    payload = {
        "id": int(m.id),
        "team_id": int(team_id),
        "user_id": int(user.id),
        "user_name": (user.full_name or user.email or user.username or "").strip() or f"User {user.id}",
        "text": text,
        "created_at": now.isoformat(),
    }

    try:
        socketio.emit("chat_message", payload, room=f"chat_team_{team_id}", namespace="/")
    except Exception:
        pass

    return jsonify({"ok": True, "message": payload})

