
import os

app_path = "app.py"
route_path = "routes/api.py"

start_marker = '@app.get("/api/notifications/unread_count")'
end_marker = 'def _chat_pair_key' # Assumption

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if start_marker in line:
        start_idx = i
    if end_marker in line:
        end_idx = i
        break

if start_idx == -1:
    print("Start marker not found")
if end_idx == -1:
    # Try alternate end: _is_user_online
    for i, line in enumerate(lines):
        if "def _is_user_online" in line:
            end_idx = i
            break
            
if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found. start={start_idx}, end={end_idx}")
    exit(1)

extracted_lines = lines[start_idx:end_idx]
remaining_lines = lines[:start_idx] + lines[end_idx:]

content = []
imports = [
    "from flask import Blueprint, jsonify, request, session, g",
    "from extensions import db",
    "from models import User, Notification",
    "from utils import login_required, _csrf_verify, ONLINE_WINDOW",
    "from datetime import datetime",
    "import time as _time",
    "",
    "api_bp = Blueprint('api', __name__)",
    "",
]
content.extend([l + "\n" for l in imports])

for line in extracted_lines:
    if "@app.route" in line:
        line = line.replace("@app.route", "@api_bp.route")
    if "@app.get" in line:
        line = line.replace("@app.get", "@api_bp.get")
    if "@app.post" in line:
        line = line.replace("@app.post", "@api_bp.post")
    content.append(line)

with open(route_path, "w", encoding="utf-8") as f:
    f.writelines(content)

# Update app.py
insert_idx = -1
for i, line in enumerate(remaining_lines):
    if "from routes.auth" in line:
        insert_idx = i + 1
        break

if insert_idx != -1:
    remaining_lines.insert(insert_idx, "from routes.api import api_bp\n")
    
    app_idx = -1
    for i, line in enumerate(remaining_lines):
        if "app = Flask(__name__)" in line:
            app_idx = i
            break
    if app_idx != -1:
        remaining_lines.insert(app_idx + 5, "app.register_blueprint(api_bp)\n")

with open(app_path, "w", encoding="utf-8") as f:
    f.writelines(remaining_lines)

print("API extraction complete.")
