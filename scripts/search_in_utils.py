try:
    with open("utils.py", "r", encoding="utf-8") as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if "from jinja2" in line:
                print(f"[IMPORTS] {i}: {line.strip()}")
            if "_mail_body_env" in line:
                print(f"[ENV_BODY] {i}: {line.strip()}")
            if "_mail_subject_env" in line:
                print(f"[ENV_SUBJ] {i}: {line.strip()}")
except Exception as e:
    print(f"Error: {e}")
