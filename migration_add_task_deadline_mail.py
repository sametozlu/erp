"""
Görev süresi bitim maili alanı ekleme migrasyonu.
Kullanım: `py -3 migration_add_task_deadline_mail.py`
"""

import sqlite3

DB_PATH = "instance/planner.db"
COLUMN_NAME = "last_deadline_mail_at"


def upgrade():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(task)")
    columns = [row[1] for row in cur.fetchall()]

    if COLUMN_NAME not in columns:
        try:
            cur.execute(f"ALTER TABLE task ADD COLUMN {COLUMN_NAME} DATETIME")
            conn.commit()
            print(f"Kolon eklendi: {COLUMN_NAME}")
        except Exception as exc:
            print(f"Hata: {exc}")
            conn.rollback()
    else:
        print(f"{COLUMN_NAME} zaten mevcut, işlem yok.")

    conn.close()


if __name__ == "__main__":
    upgrade()
