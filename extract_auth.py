
import os

app_path = "app.py"
route_path = "routes/auth.py"

start_marker = "# Initialize default users if they don't exist"
end_marker = '@app.route("/")'  # Fixed end marker

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
    # Fallback start search
    for i, line in enumerate(lines):
        if "def init_users():" in line:
            start_idx = i
            break

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found. start={start_idx}, end={end_idx}")
    exit(1)

# Extract content (exclude end_marker line, keep it in app.py)
extracted_lines = lines[start_idx:end_idx]
remaining_lines = lines[:start_idx] + lines[end_idx:]

# Process extracted lines
content = []
imports = [
    "from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g",
    "from extensions import db",
    "from models import User, Firma, Seviye, Person",
    "from utils import login_required, admin_required, _csrf_verify, _is_valid_email_address",
    "from datetime import datetime",
    "from werkzeug.security import generate_password_hash, check_password_hash",
    "",
    "auth_bp = Blueprint('auth', __name__)",
    "",
]
content.extend([l + "\n" for l in imports])

for line in extracted_lines:
    if "@app.route" in line:
        line = line.replace("@app.route", "@auth_bp.route")
    if "from utils import *" in line:
        continue # Avoid re-importing in extracted code if present
    content.append(line)

# Write routes/auth.py
with open(route_path, "w", encoding="utf-8") as f:
    f.writelines(content)

# Update app.py
# Insert import
insert_idx = -1
for i, line in enumerate(remaining_lines):
    if "from utils import" in line:
        insert_idx = i + 1
        break

if insert_idx != -1:
    remaining_lines.insert(insert_idx, "from routes.auth import auth_bp, init_users\n")
    
    # Register blueprint
    app_idx = -1
    for i, line in enumerate(remaining_lines):
        if "app = Flask(__name__)" in line:
            app_idx = i
            break
    if app_idx != -1:
        remaining_lines.insert(app_idx + 4, "app.register_blueprint(auth_bp)\n")

with open(app_path, "w", encoding="utf-8") as f:
    f.writelines(remaining_lines)

print("Auth extraction complete.")
