#!/usr/bin/env python3
"""
Mevcut tüm Job kayıtlarında assigned_user_id'yi PlanCell ile eşitler.
Böylece daha önce atanmış ama "Benim İşlerim"de görünmeyen işler düzelir.
Kullanım: Proje kökünden  python scripts/sync_job_assignments.py
"""
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

def main():
    from app import app
    from utils import upsert_jobs_for_range

    # Son 60 gün + önümüzdeki 90 gün
    start = date.today() - timedelta(days=60)
    end = date.today() + timedelta(days=90)

    with app.app_context():
        upsert_jobs_for_range(start, end)
        print(f"Job atamalari senkronize edildi: {start} - {end}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
