
path = "utils.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
funcs = []
for i, line in enumerate(lines):
    if line.strip().startswith("@app."):
        new_lines.append("# " + line)
        # Check next line for def
        if i+1 < len(lines) and "def " in lines[i+1]:
             fname = lines[i+1].split("def ")[1].split("(")[0].strip()
             funcs.append(fname)
    else:
        new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Commented app decorators in utils.py")
print("Functions to register:", funcs)
