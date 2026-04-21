from pathlib import Path
import re
text = Path('static/app.js').read_text(encoding='utf-8')
lines = text.splitlines()
bad = []
for i,l in enumerate(lines):
    if re.search(r'join\(\"$', l.strip()):
        bad.append((i+1,l))
print(bad)
