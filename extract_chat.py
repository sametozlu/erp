
import os

app_path = "app.py"
route_path = "routes/chat.py"

# Try to find start
with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_markers = ["def _chat_pair_key", "def _is_user_online", '@app.get("/chat")']
start_idx = -1
for m in start_markers:
    for i, line in enumerate(lines):
        if m in line:
            start_idx = i
            break
    if start_idx != -1:
        break

end_marker = "from routes.auth"
end_idx = -1
for i, line in enumerate(lines):
    if end_marker in line:
        end_idx = i
        break

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found. start={start_idx}, end={end_idx}")
    # Fallback end: define index
    for i, line in enumerate(lines):
        if "def index():" in line:
            end_idx = i # We want to stop before index, but wait, auth import is before index?
            # If auth import is not found (maybe I made a mistake), index is the sync point.
            # But auth routes were extracted.
            break
    
    # If still not found
    if end_idx == -1:
         print("Fatal: End marker not found")
         exit(1)

extracted_lines = lines[start_idx:end_idx]
remaining_lines = lines[:start_idx] + lines[end_idx:]

content = []
imports = [
    "from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, g",
    "from extensions import db, socketio",
    "from models import User, ChatMessage, ChatUserMessage, Announcement, AnnouncementRead, Team",
    "from utils import login_required, get_current_user, _fetch_announcements, ONLINE_WINDOW, _is_user_online",
    "from datetime import datetime",
    "from sqlalchemy import or_, and_, desc, func",
    "",
    "chat_bp = Blueprint('chat', __name__)",
    "",
]
content.extend([l + "\n" for l in imports])

for line in extracted_lines:
    if "@app.route" in line:
        line = line.replace("@app.route", "@chat_bp.route")
    if "@app.get" in line:
        line = line.replace("@app.get", "@chat_bp.get")
    if "@app.post" in line:
        line = line.replace("@app.post", "@chat_bp.post")
    content.append(line)

with open(route_path, "w", encoding="utf-8") as f:
    f.writelines(content)

# Update app.py
insert_idx = -1
for i, line in enumerate(remaining_lines):
    if "from routes.api" in line:
        insert_idx = i + 1
        break

if insert_idx != -1:
    remaining_lines.insert(insert_idx, "from routes.chat import chat_bp\n")
    
    app_idx = -1
    for i, line in enumerate(remaining_lines):
        if "app = Flask(__name__)" in line:
            app_idx = i
            break
    if app_idx != -1:
        remaining_lines.insert(app_idx + 6, "app.register_blueprint(chat_bp)\n")

with open(app_path, "w", encoding="utf-8") as f:
    f.writelines(remaining_lines)

print("Chat extraction complete.")
