
from datetime import datetime
from sqlalchemy import or_, and_, desc

path = "utils.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Check if already exists to avoid duplication
if "def _is_user_online" in content:
    print("Already has _is_user_online")
else:
    print("Appending _is_user_online...")
    with open(path, "a", encoding="utf-8") as f:
        f.write('\n\ndef _is_user_online(user_obj, *, now=None):\n')
        f.write('    if not user_obj:\n')
        f.write('        return False\n')
        f.write('    now = now or datetime.now()\n')
        f.write('    cutoff = now - ONLINE_WINDOW\n')
        f.write('    last_seen = getattr(user_obj, "last_seen", None)\n')
        f.write('    return bool(last_seen and last_seen >= cutoff)\n')

if "def _fetch_announcements" in content:
    print("Already has _fetch_announcements")
else:
    print("Appending _fetch_announcements...")
    with open(path, "a", encoding="utf-8") as f:
        f.write('\n\ndef _fetch_announcements(user, limit=5):\n')
        f.write('    if not user:\n')
        f.write('        return []\n')
        f.write('    clauses = [Announcement.audience_type == "all"]\n')
        f.write('    if user.team_id:\n')
        f.write('        clauses.append(and_(Announcement.audience_type == "team", Announcement.audience_id == user.team_id))\n')
        f.write('    clauses.append(and_(Announcement.audience_type == "user", Announcement.audience_id == user.id))\n')
        f.write('    q = Announcement.query.filter(or_(*clauses)).order_by(Announcement.created_at.desc())\n')
        f.write('    rows = q.limit(limit).all()\n')
        f.write('    out = []\n')
        f.write('    for a in rows:\n')
        f.write('        is_read = AnnouncementRead.query.filter_by(announcement_id=a.id, user_id=user.id).count() > 0\n')
        f.write('        out.append({"id": a.id, "title": a.title, "body": a.body, "created_at": a.created_at.strftime("%d.%m.%Y %H:%M"), "is_read": is_read})\n')
        f.write('    return out\n')

print("Done appending to utils.py")
