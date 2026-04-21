
path = "app.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# We want to keep lines 1 to 1197 (index 0 to 1196)
# And lines 2420 to end (index 2419 to end)

new_lines = lines[:1197] + lines[2419:]

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Cleaned up app.py. Old length: {len(lines)}, New length: {len(new_lines)}")
