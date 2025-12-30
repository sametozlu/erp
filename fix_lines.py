from pathlib import Path
p=Path('static/app.js')
lines=p.read_text(encoding='utf-8').splitlines()
for idx in sorted([1779,1765], reverse=True):
    if 0 <= idx < len(lines):
        lines.pop(idx)
p.write_text('\n'.join(lines), encoding='utf-8')
