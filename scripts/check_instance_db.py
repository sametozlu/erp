import sqlite3
import os

DB_PATH = os.path.join("instance", "planner.db")

def check_db():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] {DB_PATH} bulunamadı!")
        return

    print(f"[CHECK] {DB_PATH} kontrol ediliyor...")
    
    # Integrity Check
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    res = cursor.fetchone()
    if res and res[0] == "ok":
        print("[OK] Integrity Check PASS.")
    else:
        print(f"[FAIL] Integrity Check FAIL: {res}")
        conn.close()
        return

    # MailLog Schema Check
    cursor.execute("PRAGMA table_info(mail_log);")
    cols = [r[1] for r in cursor.fetchall()]
    print(f"MailLog Columns: {cols}")
    
    if "team_id" not in cols:
        print("[ACTION] adding team_id column...")
        try:
            cursor.execute("ALTER TABLE mail_log ADD COLUMN team_id INTEGER;")
            conn.commit()
            print("[SUCCESS] team_id added.")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_mail_log_team_id ON mail_log (team_id);")
            conn.commit()
            print("[SUCCESS] index added.")
        except Exception as e:
            print(f"[ERROR] Alter table failed: {e}")
    else:
        print("[OK] team_id already exists.")
        
    conn.close()

if __name__ == "__main__":
    check_db()
