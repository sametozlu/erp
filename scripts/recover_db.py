#!/usr/bin/env python3
"""
Bozuk SQLite veritabanını yedekleyip, son alınan yedekten geri yükler.
Kullanım: Proje kökünden  python scripts/recover_db.py
"""
import os
import sys
import shutil
import glob
from datetime import datetime

# Proje kökünü path'e ekle
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

def main():
    from app import app
    from utils import _sqlite_db_path

    with app.app_context():
        db_path = _sqlite_db_path()
        if not db_path:
            print("Hata: SQLite veritabanı yolu alınamadı.")
            return 1
        if not os.path.exists(db_path):
            print(f"Hata: Veritabanı dosyası yok: {db_path}")
            return 1

        instance_path = app.instance_path
        backups_dir = os.path.join(instance_path, "backups")
        os.makedirs(backups_dir, exist_ok=True)

        # 1) Bozuk dosyayı yedekle
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        corrupt_backup = os.path.join(backups_dir, f"corrupt_{stamp}.db")
        try:
            shutil.copy2(db_path, corrupt_backup)
            print(f"[OK] Bozuk veritabanı yedeklendi: {corrupt_backup}")
        except Exception as e:
            print(f"[HATA] Yedek alınamadı: {e}")
            return 1

        # 2) Son iyi yedeği bul (backup_*.db veya pre_restore_backup_*.db, corrupted_ hariç)
        candidates = []
        for pattern in ["backup_*.db", "pre_restore_backup_*.db"]:
            for p in glob.glob(os.path.join(backups_dir, pattern)):
                if "corrupted_" in os.path.basename(p).lower():
                    continue
                try:
                    mtime = os.path.getmtime(p)
                    candidates.append((mtime, p))
                except Exception:
                    pass
        if not candidates:
            print("[HATA] instance/backups/ içinde geri yüklenecek yedek bulunamadı.")
            print("       Önce uygulama çalışırken bir yedek alın (örn. Admin > DB Yedek).")
            return 1

        # En güncel yedek
        candidates.sort(key=lambda x: -x[0])
        latest_backup = candidates[0][1]
        print(f"[OK] Geri yüklenecek yedek: {os.path.basename(latest_backup)}")

        # 3) Yedeği ana veritabanı konumuna kopyala
        try:
            shutil.copy2(latest_backup, db_path)
            print(f"[OK] Veritabanı geri yüklendi: {db_path}")
        except Exception as e:
            print(f"[HATA] Geri yükleme başarısız: {e}")
            return 1

        # 4) Doğrulama: yeni db açılabiliyor mu?
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            print("[OK] integrity_check geçti. Uygulama tekrar çalıştırılabilir.")
        except Exception as e:
            print(f"[UYARI] integrity_check atlandı veya hata: {e}")

        return 0

if __name__ == "__main__":
    sys.exit(main())
