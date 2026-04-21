import sqlite3
import os

DB_FILES = ["app.db", "planner.db"]

def check_integrity(db_path):
    if not os.path.exists(db_path):
        print(f"[SKIP] {db_path} bulunamadı.")
        return True # Dosya yoksa bozuk değil sayalım, schema kontrolü de yapmayız
    
    print(f"[CHECK] {db_path} bütünlük kontrolü yapılıyor...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == "ok":
            print(f"[OK] {db_path} sağlam.")
            return True
        else:
            print(f"[ERROR] {db_path} BOZUK! Hata: {result}")
            return False
    except Exception as e:
        print(f"[ERROR] {db_path} kontrol edilirken hata: {e}")
        return False

def check_maillog_schema(db_path):
    if not os.path.exists(db_path):
        return

    print(f"[SCHEMA] {db_path} içinde MailLog tablosu kontrol ediliyor...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Tablo var mı?
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mail_log';")
        if not cursor.fetchone():
            print(f"[INFO] {db_path} içinde 'mail_log' tablosu yok.")
            conn.close()
            return

        # Sütunları kontrol et
        cursor.execute("PRAGMA table_info(mail_log);")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "team_id" in columns:
            print(f"[OK] 'team_id' sütunu mevcut.")
        else:
            print(f"[MISSING] 'team_id' sütunu EKSİK! Ekleniyor...")
            try:
                cursor.execute("ALTER TABLE mail_log ADD COLUMN team_id INTEGER;")
                conn.commit()
                print(f"[FIXED] 'team_id' sütunu başarıyla eklendi.")
                
                # Index ekle
                try:
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_mail_log_team_id ON mail_log (team_id);")
                    conn.commit()
                    print(f"[FIXED] İndeks oluşturuldu.")
                except Exception as ex:
                    print(f"[WARNING] İndeks oluşturulurken hata: {ex}")
                    
            except Exception as e:
                print(f"[ERROR] Sütun eklenirken hata: {e}")
        
        conn.close()
    except Exception as e:
        print(f"[ERROR] Şema kontrol hatası: {e}")

if __name__ == "__main__":
    print("--- BAŞLANGIÇ ---")
    for db_file in DB_FILES:
        # Integrity check başarılı ise schema check yap
        if check_integrity(db_file):
            check_maillog_schema(db_file)
    print("--- BİTİŞ ---")
