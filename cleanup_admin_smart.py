
import os

app_path = "app.py"

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Target: mail_settings_test
# Look for def mail_settings_test
start_idx = -1
for i, line in enumerate(lines):
    if "def mail_settings_test" in line:
        start_idx = i
        break

if start_idx != -1:
    # Go back to find decorators
    while start_idx > 0 and (lines[start_idx-1].strip().startswith("@") or lines[start_idx-1].strip() == ""):
        start_idx -= 1
        
    # Find end: @socketio.on
    end_idx = -1
    for i in range(start_idx, len(lines)):
        if "@socketio.on" in lines[i]:
            end_idx = i
            break
            
    if end_idx != -1:
        print(f"Removing lines {start_idx} to {end_idx}")
        remaining_lines = lines[:start_idx] + lines[end_idx:]
        
        # Check import logic (same as before)
        if not any("from routes.admin" in l for l in remaining_lines):
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
                 if not any("app.register_blueprint(admin_bp)" in l for l in remaining_lines):
                    remaining_lines.insert(app_idx + 8, "app.register_blueprint(admin_bp)\n")

        with open(app_path, "w", encoding="utf-8") as f:
            f.writelines(remaining_lines)
        print("Cleanup complete.")
    else:
        print("End marker not found")
else:
    print("mail_settings_test not found")
