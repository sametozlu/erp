
import os
import re

app_path = "app.py"

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

reg_lines = []
reg_indices = []
import_end_idx = -1

for i, line in enumerate(lines):
    if "app.register_blueprint" in line:
        reg_lines.append(line)
        reg_indices.append(i)
    if "from routes." in line:
        import_end_idx = i

if not reg_indices or import_end_idx == -1:
    print("Nothing to move")
    exit(0)

# Check if order is wrong
first_reg = reg_indices[0]
if first_reg < import_end_idx:
    print("Fixing order...")
    # Remove reg lines
    new_lines = [line for i, line in enumerate(lines) if i not in reg_indices]
    
    # Find where to insert (after imports)
    # Re-calculate insert index on new_lines
    insert_idx = -1
    for i, line in enumerate(new_lines):
        if "from routes." in line:
            insert_idx = i
    
    # Insert after the last route import
    if insert_idx != -1:
        # Check if there are multiple route imports, find the last one
        for i in range(len(new_lines) - 1, -1, -1):
            if "from routes." in new_lines[i]:
                insert_idx = i
                break
        
        insert_pos = insert_idx + 1
        for l in reg_lines:
            new_lines.insert(insert_pos, l)
            insert_pos += 1
            
        with open(app_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("Order fixed.")
    else:
        print("Could not find insert position")
else:
    print("Order is correct")
