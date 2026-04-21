import sqlite3
import os


def migrate():
    print("Migration basliyor: announcement.is_popup ekleniyor...")

    dbs = ["instance/app.db", "instance/planner.db", "app.db", "planner.db"]
    found_dbs = []

    for db_path in dbs:
        if os.path.exists(db_path):
            print(f"Veritabani bulundu: {db_path}")
            found_dbs.append(db_path)

    if not found_dbs:
        print("Hicbir veritabani bulunamadi!")
        return

    for db_path in found_dbs:
        print(f"Islem yapiliyor: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='announcement'")
            if not cursor.fetchone():
                print("Tablo bulunamadi: announcement")
                conn.close()
                continue

            cursor.execute("PRAGMA table_info(announcement)")
            columns = [column[1] for column in cursor.fetchall()]
            if "is_popup" not in columns:
                print("'is_popup' sutunu ekleniyor...")
                cursor.execute("ALTER TABLE announcement ADD COLUMN is_popup BOOLEAN NOT NULL DEFAULT 0")
                print("Sutun eklendi.")
            else:
                print("'is_popup' sutunu zaten var.")

            conn.commit()
        except Exception as e:
            print(f"Hata: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()


if __name__ == "__main__":
    migrate()
