"""
Görev hatırlatma kolonları ekleme migrasyonu.
Kullanım: `py migration_add_task_reminder_columns.py`

Eklenen kolonlar:
- reminder_days_before: Kaç gün önce hatırlatma yapılacak
- reminder_count: Toplam hatırlatma sayısı
- last_reminder_at: Son hatırlatma ne zaman yapıldı
- reminder_sent_count: Şimdiye kadar kaç kez hatırlatma gönderildi
"""

import sqlite3
import os

DB_PATH = "instance/planner.db"
COLUMNS = [
    ("reminder_days_before", "INTEGER NOT NULL DEFAULT 0"),
    ("reminder_count", "INTEGER NOT NULL DEFAULT 0"),
    ("last_reminder_at", "DATETIME"),
    ("reminder_sent_count", "INTEGER NOT NULL DEFAULT 0")
]


def upgrade():
    # Alternatif db paths
    db_paths = ["instance/planner.db", "planner.db", "instance/app.db", "app.db"]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            print(f"Veritabanı bulundu: {path}")
            break
    
    if not db_path:
        print("HATA: Veritabanı dosyası bulunamadı!")
        return
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Tablo var mı kontrol et
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task'")
    if not cur.fetchone():
        print("HATA: 'task' tablosu bulunamadı!")
        conn.close()
        return
    
    print(f"'{db_path}' veritabanında işlem yapılıyor...\n")
    
    for col_name, col_def in COLUMNS:
        # Mevcut kolonları kontrol et
        cur.execute("PRAGMA table_info(task)")
        columns = [row[1] for row in cur.fetchall()]
        
        if col_name in columns:
            print(f"✓ {col_name} zaten mevcut, atlanıyor.")
        else:
            try:
                cur.execute(f"ALTER TABLE task ADD COLUMN {col_name} {col_def}")
                print(f"+ {col_name} kolonu eklendi ({col_def})")
            except Exception as e:
                print(f"✗ {col_name} eklenirken HATA: {e}")
                conn.rollback()
    
    conn.commit()
    conn.close()
    print("\nMigrasyon tamamlandı.")


if __name__ == "__main__":
    upgrade()
