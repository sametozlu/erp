
import os

app_path = "app.py"
utils_path = "utils.py"

with open(app_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

def find_block(start_sig, end_sig):
    s = -1
    e = -1
    for i, line in enumerate(lines):
        if start_sig in line:
            s = i
        if end_sig in line and s != -1:
            e = i
            break
    return s, e

# 1. get_current_user
s1, e1 = find_block("def get_current_user():", "@socketio.on")
if s1 == -1 or e1 == -1:
    # Try alternate
    s1, e1 = find_block("def get_current_user():", "def _socket_connect():")

# 2. observer_required
s2, e2 = find_block("def observer_required(f):", "@app.get")

to_remove = []
to_append = []

if s1 != -1 and e1 != -1:
    to_append.extend(lines[s1:e1])
    to_remove.append((s1, e1))
else:
    print("get_current_user not found")

if s2 != -1 and e2 != -1:
    to_append.extend(lines[s2:e2])
    to_remove.append((s2, e2))
else:
    print("observer_required not found")

if not to_remove:
    print("Nothing to move.")
    exit(1)

# Sort removal intervals reverse
to_remove.sort(key=lambda x: x[0], reverse=True)

# Append to utils
with open(utils_path, "a", encoding="utf-8") as f:
    f.write("\n\n")
    f.writelines(to_append)

# Remove from app
new_lines = list(lines)
for s, e in to_remove:
    new_lines[s:e] = []

with open(app_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Moved auth helpers.")
