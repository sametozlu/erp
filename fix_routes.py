
import os
import glob

def fix_route_file(path, bp_name):
    print(f"Fixing {path} (BP: {bp_name})...")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    new_lines = []
    shortcuts = ["@app.get", "@app.post", "@app.route", "@app.before_request", "@app.after_request"]
    
    # Check if current_app is imported
    has_current_app = False
    for line in lines:
        if "from flask import" in line and "current_app" in line:
            has_current_app = True
            break
            
    if not has_current_app:
        # Add it to the flask import
        for i, line in enumerate(lines):
            if "from flask import" in line:
                if "(" in line:
                    # multiline import - simplified handling: just append a new line
                    lines.insert(i+1, "from flask import current_app\n")
                else:
                    lines[i] = line.strip() + ", current_app\n"
                break
    
    for line in lines:
        # Replace decorators
        if line.strip().startswith("@app."):
            if "before_request" in line:
                # Blueprint before_request applies to blueprint routes.
                # If we want global, use before_app_request.
                # Assuming intent is local to blueprint or just copy-paste error.
                # We'll use bp.before_request
                line = line.replace("@app.before_request", f"@{bp_name}.before_request")
            elif "after_request" in line:
                line = line.replace("@app.after_request", f"@{bp_name}.after_request")
            else:
                line = line.replace("@app.", f"@{bp_name}.")
        
        # Replace usage
        line = line.replace("app.config", "current_app.config")
        line = line.replace("app.instance_path", "current_app.instance_path")
        
        new_lines.append(line)
        
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

fix_route_file("routes/admin.py", "admin_bp")
fix_route_file("routes/planner.py", "planner_bp")
fix_route_file("routes/auth.py", "auth_bp")
fix_route_file("routes/chat.py", "chat_bp")
fix_route_file("routes/api.py", "api_bp")
print("Route files fixed.")
