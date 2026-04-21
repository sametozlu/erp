
import os

app_path = "app.py"
route_path = "routes/admin.py"

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_marker = '@app.route("/mail/settings"'
end_marker = '@socketio.on'

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
    # Try alternate
    for i, line in enumerate(lines):
        if "def _socket_connect" in line:
            end_idx = i
            break

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found. start={start_idx}, end={end_idx}")
    exit(1)

extracted_lines = lines[start_idx:end_idx]
remaining_lines = lines[:start_idx] + lines[end_idx:]

content = []
imports = [
    "from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory, current_app",
    "from extensions import db",
    "from models import MailLog, MailTemplate",
    "from utils import admin_required, load_mail_settings, _load_mail_settings_file, _csrf_verify, _is_valid_email_address, save_mail_settings, MAIL_PASSWORD_PLACEHOLDER, send_email_smtp, allowed_upload",
    "from datetime import datetime",
    "import os",
    "",
    "admin_bp = Blueprint('admin', __name__)",
    "",
]
content.extend([l + "\n" for l in imports])

for line in extracted_lines:
    if "@app.route" in line:
        line = line.replace("@app.route", "@admin_bp.route")
    if "@app.get" in line:
        line = line.replace("@app.get", "@admin_bp.get")
    if "@app.post" in line:
        line = line.replace("@app.post", "@admin_bp.post")
    content.append(line)

with open(route_path, "w", encoding="utf-8") as f:
    f.writelines(content)

# Update app.py
insert_idx = -1
for i, line in enumerate(remaining_lines):
    if "from routes.chat" in line:
        insert_idx = i + 1
        break

if insert_idx != -1:
    remaining_lines.insert(insert_idx, "from routes.admin import admin_bp\n")
    
    app_idx = -1
    for i, line in enumerate(remaining_lines):
        if "app = Flask(__name__)" in line:
            app_idx = i
            break
    if app_idx != -1:
        remaining_lines.insert(app_idx + 7, "app.register_blueprint(admin_bp)\n")

with open(app_path, "w", encoding="utf-8") as f:
    f.writelines(remaining_lines)

print("Admin extraction complete.")
