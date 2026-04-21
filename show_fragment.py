from pathlib import Path
lines = Path('app.py').read_text(encoding='utf-8').splitlines()
with open('tmp_fragment.txt','w',encoding='utf-8') as f:
    for i in range(2880,2966):
        if 0 <= i-1 < len(lines):
            f.write(f'{i}:{lines[i-1]}\n')
