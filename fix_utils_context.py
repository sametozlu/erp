
path = "utils.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "MAIL_SETTINGS_PATH =" in line:
        continue # Remove global definition
    if "start_time = _time.time()" in line: # Example of something else? No.
        pass
    
    # Replace usages
    if "MAIL_SETTINGS_PATH" in line:
        line = line.replace("MAIL_SETTINGS_PATH", 'os.path.join(current_app.instance_path, "mail_settings.json")')
    
    new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Fixed utils context.")
