# -*- coding: utf-8 -*-
"""Veritabanı bütünlük ve uyumluluk kontrolü."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

def main():
    from app import app
    from utils import _sqlite_db_path
    from extensions import db
    from models import User

    with app.app_context():
        path = _sqlite_db_path()
        print("DB yolu:", path)
        if not path:
            print("Hata: DB yolu alinamadi.")
            return 1
        if not os.path.exists(path):
            print("Hata: Dosya yok.")
            return 1

        # SQLite integrity
        import sqlite3
        conn = sqlite3.connect(path)
        r = conn.execute("PRAGMA integrity_check").fetchone()
        print("integrity_check:", r[0])
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        print("Tablo sayisi:", len(tables))
        conn.close()

        # Uygulama ile sorgu
        try:
            n = User.query.count()
            print("User kayit sayisi:", n)
            print("OK: Veritabani uygulama ile uyumlu.")
        except Exception as e:
            print("Hata (User.query):", e)
            return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
