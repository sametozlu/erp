
import sqlite3
import os

def migrate():
    print("Migration basliyor: notification_enabled ekleniyor...")
    
    # instance/app.db ve instance/planner.db kontrol edilecek
    dbs = ['instance/app.db', 'instance/planner.db', 'app.db', 'planner.db']
    
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
        
        # Tablolari kontrol et
        tables_to_check = ['task', 'project']
        
        for table_name in tables_to_check:
            try:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if not cursor.fetchone():
                    print(f"Tablo bulunamadi: {table_name} ({db_path})")
                    continue
                    
                print(f"Tablo inceleniyor: {table_name}")
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'notification_enabled' not in columns:
                    print(f"'notification_enabled' sütunu {table_name} tablosuna ekleniyor...")
                    # Boolean default True (1)
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN notification_enabled BOOLEAN NOT NULL DEFAULT 1")
                    print(f"Sütun başarıyla eklendi: {table_name}")
                else:
                    print(f"'notification_enabled' sütunu zaten var: {table_name}")
                    
            except Exception as e:
                print(f"Hata ({table_name}): {e}")
                
        conn.commit()
        conn.close()

if __name__ == "__main__":
    migrate()
