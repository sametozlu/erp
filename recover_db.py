
import os
import shutil
import glob
import datetime
import sys

# Paths
INSTANCE_DIR = os.path.join(os.getcwd(), "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "planner.db")
BACKUP_DIR = os.path.join(INSTANCE_DIR, "backups")

def recover_database():
    if not os.path.exists(DB_PATH):
        print("Mevcut veritabanı bulunamadı.")
        return

    # Find latest backup
    backups = glob.glob(os.path.join(BACKUP_DIR, "*.db"))
    if not backups:
        print("Hiçbir yedek dosyası bulunamadı!")
        return

    latest_backup = max(backups, key=os.path.getctime)
    print(f"En son yedek: {latest_backup}")

    # Move corrupt DB
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    corrupt_path = os.path.join(INSTANCE_DIR, f"planner_corrupt_{timestamp}.db")
    
    try:
        shutil.move(DB_PATH, corrupt_path)
        print(f"Bozuk veritabanı şuraya yedeklendi: {corrupt_path}")
    except Exception as e:
        print(f"Bozuk dosya taşınırken hata oluştu: {e}")
        return

    # Restore backup
    try:
        shutil.copy2(latest_backup, DB_PATH)
        print("Yedek başarıyla geri yüklendi.")
        print(f"Yüklenen yedek: {os.path.basename(latest_backup)}")
    except Exception as e:
        print(f"Yedek yüklenirken hata oluştu: {e}")
        # Try to revert moving corrupt file
        shutil.move(corrupt_path, DB_PATH)
        print("İşlem geri alındı.")

if __name__ == "__main__":
    recover_database()
