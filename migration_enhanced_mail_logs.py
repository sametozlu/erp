
# Mail Sistemi Geliştirme V2 - Migration Script
# Kullanım: Bu scripti manuel olarak çalıştırarak veya sistem başlatıldığında çağırarak veritabanı tablosunu güncelleyin.
# NOT: Flask-Migrate veya Alembic kullanılıyors bunlara gerek yoktur.

import sqlite3
from datetime import datetime

DB_PATH = "instance/planner.db"

def upgrade():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Migrasyon baslatiliyor: MailLog genisletme...")
    
    # Mevcut sütunları kontrol et
    cursor.execute("PRAGMA table_info(mail_log)")
    columns = [row[1] for row in cursor.fetchall()]
    
    new_columns = [
        ("mail_type", "VARCHAR(50)"),
        ("error_code", "VARCHAR(50)"),
        ("cc_addr", "VARCHAR(500)"),
        ("bcc_addr", "VARCHAR(500)"),
        ("body_preview", "TEXT"),
        ("attachments_count", "INTEGER DEFAULT 0"),
        ("body_size_bytes", "INTEGER DEFAULT 0"),
        ("sent_at", "DATETIME"),
        ("user_id", "INTEGER"),
        ("project_id", "INTEGER"),
        ("job_id", "INTEGER"),
        ("task_id", "INTEGER"),
        ("team_id", "INTEGER")
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            print(f"Ekleniyor: {col_name} ({col_type})")
            try:
                cursor.execute(f"ALTER TABLE mail_log ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"HATA: {col_name} eklenemedi: {e}")
        else:
            print(f"Mevcut: {col_name}")
            
    # Mevcut verileri güncelle (mail_type = kind)
    if "mail_type" not in columns:
        print("Eski veriler guncelleniyor (mail_type)...")
        cursor.execute("UPDATE mail_log SET mail_type = kind WHERE mail_type IS NULL")
        
    conn.commit()
    conn.close()
    print("Migrasyon tamamlandi.")

if __name__ == "__main__":
    upgrade()
