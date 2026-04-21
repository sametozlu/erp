
import os

file_path = "routes/planner.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
skipped_analytics_page = False
skipped_export = False

for i, line in enumerate(lines):
    # Check for start of analytics page
    if '@planner_bp.get("/reports-analytics")' in line:
        skip = True
        skipped_analytics_page = True
        print(f"Skipping started at line {i+1}: {line.strip()}")
    
    # Check for start of analytics export
    if '@planner_bp.get("/analytics/export/excel")' in line:
        skip = True
        skipped_export = True
        print(f"Skipping started at line {i+1}: {line.strip()}")

    if not skip:
        new_lines.append(line)
    
    # Check for end of analytics page
    # It ends before @planner_bp.post("/projects/<int:project_id>/delete")
    if skip and skipped_analytics_page and not skipped_export:
        # Looking for the next route definition to stop skipping
        if i + 1 < len(lines) and '@planner_bp.post("/projects/<int:project_id>/delete")' in lines[i+1]:
            skip = False
            print(f"Skipping ended at line {i+1}")
            
    # Check for end of file for export
    # If we are in export, we just skip until the end essentially, 
    # OR until we see another route if it wasn't the last one. 
    # But it WAS the last one.
    # However, let's be safe.
    if skip and skipped_export:
        # It's at the end of the file, so we just skip everything.
        pass

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Done.")
