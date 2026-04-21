
import sqlite3
import os

def migrate():
    print("Migration basliyor: Project ve ProjectComment guncellemeleri...")
    
    db_path = os.path.join('instance', 'planner.db')
    if not os.path.exists(db_path):
        if os.path.exists('planner.db'):
            db_path = 'planner.db'
        else:
            print("Veritabani bulunamadi!")
            return

    print(f"Veritabani: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Project tablosuna notification_enabled ekle
        cursor.execute("PRAGMA table_info(project)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'notification_enabled' not in columns:
            print("Project: notification_enabled ekleniyor...")
            cursor.execute("ALTER TABLE project ADD COLUMN notification_enabled BOOLEAN NOT NULL DEFAULT 1")
        
        # 2. Project_code unique yap (Index ekleyerek)
        # Önce duplicate var mı bakalim, varsa unique yapamayiz
        cursor.execute("SELECT project_code, COUNT(*) FROM project GROUP BY project_code HAVING COUNT(*) > 1")
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"UYARI: Duplicate proje kodlari var, unique index eklenemiyor: {duplicates}")
        else:
            print("Project: project_code icin unique index ekleniyor...")
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_project_code_unique ON project(project_code)")
            except Exception as e:
                print(f"Index ekleme hatasi (gecilebilir): {e}")

        # 3. ProjectComment tablosuna dosya alanlari ekle
        cursor.execute("PRAGMA table_info(project_comment)")
        p_columns = [column[1] for column in cursor.fetchall()]
        
        if 'file_path' not in p_columns:
            print("ProjectComment: file_path ekleniyor...")
            cursor.execute("ALTER TABLE project_comment ADD COLUMN file_path VARCHAR(400)")
            
        if 'file_type' not in p_columns:
            print("ProjectComment: file_type ekleniyor...")
            cursor.execute("ALTER TABLE project_comment ADD COLUMN file_type VARCHAR(30)")
            
        if 'file_name' not in p_columns:
            print("ProjectComment: file_name ekleniyor...")
            cursor.execute("ALTER TABLE project_comment ADD COLUMN file_name VARCHAR(255)")

        conn.commit()
        print("Migration basariyla tamamlandi.")
            
    except Exception as e:
        print(f"Hata oluştu: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
