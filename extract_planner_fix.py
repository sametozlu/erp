
import os

app_path = "app.py"
route_path = "routes/planner.py"

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_marker = "def index():"
end_marker = 'if __name__ == "__main__":'

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if start_marker in line:
        start_idx = i
    if end_marker in line:
        end_idx = i
        break
        
if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found. start={start_idx}, end={end_idx}")
    exit(1)

extracted_lines = lines[start_idx:end_idx]
remaining_lines = lines[:start_idx] + lines[end_idx:]

content = []
imports = [
    "from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file, make_response, current_app",
    "from extensions import db",
    "from models import *",
    "from utils import *",
    "from datetime import date, datetime, timedelta",
    "from sqlalchemy import or_, and_, desc, func, case",
    "import json",
    "import io",
    "import os",
    "import math",
    "import re",
    "import time as _time",
    "from openpyxl import Workbook",
    "from openpyxl.utils import get_column_letter",
    "from openpyxl.styles import Font, Alignment, PatternFill",
    "from openpyxl.styles.colors import Color",
    "",
    "planner_bp = Blueprint('planner', __name__)",
    "",
]
content.extend([l + "\n" for l in imports])

# Add the missing decorator for index
content.append('@planner_bp.route("/")\n')

for line in extracted_lines:
    if "@app.route" in line:
        line = line.replace("@app.route", "@planner_bp.route")
    if "@app.get" in line:
        line = line.replace("@app.get", "@planner_bp.get")
    if "@app.post" in line:
        line = line.replace("@app.post", "@planner_bp.post")
    content.append(line)

with open(route_path, "w", encoding="utf-8") as f:
    f.writelines(content)

# Update app.py
insert_idx = -1
for i, line in enumerate(remaining_lines):
    if "from routes.admin" in line:
        insert_idx = i + 1
        break

if insert_idx != -1:
    # Check if we already added it (failed run)
    if not any("from routes.planner" in l for l in remaining_lines):
        remaining_lines.insert(insert_idx, "from routes.planner import planner_bp\n")
    
    app_idx = -1
    for i, line in enumerate(remaining_lines):
        if "app = Flask(__name__)" in line:
            app_idx = i
            break
    if app_idx != -1:
        if not any("app.register_blueprint(planner_bp)" in l for l in remaining_lines):
            remaining_lines.insert(app_idx + 8, "app.register_blueprint(planner_bp)\n")

with open(app_path, "w", encoding="utf-8") as f:
    f.writelines(remaining_lines)

print("Planner extraction fix complete.")
