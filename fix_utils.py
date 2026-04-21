
path = "utils.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("app.config", "current_app.config")
content = content.replace("app.instance_path", "current_app.instance_path")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed utils.py")
