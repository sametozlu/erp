
import sqlite3
import os

def migrate():
    print("Migration basliyor...")
    
    # instance/planner.db kontrol et
    db_path = os.path.join('instance', 'planner.db')
    if not os.path.exists(db_path):
        # Kök dizinde planner.db var mı?
        if os.path.exists('planner.db'):
            db_path = 'planner.db'
        else:
            print("Veritabani bulunamadi!")
            return

    print(f"Veritabani yolu: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Sütunun var olup olmadığını kontrol et
        cursor.execute("PRAGMA table_info(personnel_status_type)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'visible_in_summary' not in columns:
            print("'visible_in_summary' sütunu ekleniyor...")
            cursor.execute("ALTER TABLE personnel_status_type ADD COLUMN visible_in_summary BOOLEAN NOT NULL DEFAULT 1")
            conn.commit()
            print("Sütun başarıyla eklendi.")
        else:
            print("'visible_in_summary' sütunu zaten var.")
            
    except Exception as e:
        print(f"Hata oluştu: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
