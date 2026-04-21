
import os

app_path = "app.py"
route_path = "routes/chat.py"

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_marker = 'def _chat_pair_key'
end_marker = 'def index():'

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if start_marker in line:
        start_idx = i
    if end_marker in line:
        end_idx = i
        break
        
if start_idx == -1:
    # Try alternate start
    for i, line in enumerate(lines):
        if 'def _is_user_online' in line:
            start_idx = i
            break
            
if start_idx == -1:
    # Try alternate start 2
    for i, line in enumerate(lines):
        if '@app.get("/chat")' in line:
            start_idx = i
            break

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found. start={start_idx}, end={end_idx}")
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
# Check if import exists
import_exists = False
for line in remaining_lines:
    if "from routes.chat import chat_bp" in line:
        import_exists = True
        break

if not import_exists:
    # Insert import
    insert_idx = -1
    for i, line in enumerate(remaining_lines):
        if "from routes.api" in line:
            insert_idx = i + 1
            break
    if insert_idx != -1:
        remaining_lines.insert(insert_idx, "from routes.chat import chat_bp\n")

with open(app_path, "w", encoding="utf-8") as f:
    f.writelines(remaining_lines)

print("Chat extraction fix complete.")
