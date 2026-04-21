from pathlib import Path
text=Path("static/app.js").read_text(encoding="utf-8",errors="ignore").splitlines()
inds=[i for i,l in enumerate(text) if '"use strict"' in l]
print(inds)
