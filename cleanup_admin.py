
import os

app_path = "app.py"

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_marker = '@app.route("/mail/settings"'
# End marker should be the start of sockets
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

if start_idx != -1 and end_idx != -1:
    # Remove lines
    print(f"Removing lines {start_idx} to {end_idx}")
    remaining_lines = lines[:start_idx] + lines[end_idx:]
    
    # Check import
    if not any("from routes.admin" in l for l in remaining_lines):
        # Insert import
        insert_idx = -1
        for i, line in enumerate(remaining_lines):
            if "from routes.chat" in line:
                insert_idx = i + 1
                break
        if insert_idx != -1:
            remaining_lines.insert(insert_idx, "from routes.admin import admin_bp\n")
            
        # Register blueprint
        app_idx = -1
        for i, line in enumerate(remaining_lines):
            if "app = Flask(__name__)" in line:
                app_idx = i
                break
        if app_idx != -1:
            if not any("app.register_blueprint(admin_bp)" in l for l in remaining_lines):
                remaining_lines.insert(app_idx + 8, "app.register_blueprint(admin_bp)\n")

    with open(app_path, "w", encoding="utf-8") as f:
        f.writelines(remaining_lines)
    print("Cleanup complete.")
else:
    print(f"Markers not found. s={start_idx} e={end_idx}")
