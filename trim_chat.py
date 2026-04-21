
path = "routes/chat.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Check if last line is partial decorator
if lines and "@chat_bp.route" in lines[-1]:
    # remove it
    lines.pop()
if lines and lines[-1].strip() == "":
    lines.pop()
# Check one more time just in case there was a newline
if lines and "@chat_bp.route" in lines[-1]:
    lines.pop()

with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Trimmed chat.py")
