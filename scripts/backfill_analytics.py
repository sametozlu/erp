import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from extensions import db
from models import Job
from services.analytics import record_job_completion, update_monthly_stats
from datetime import datetime

# app = create_app() # app is imported directly

def backfill_analytics():
    """
    Geçmişte tamamlanmış tüm işleri analiz sistemine aktarır.
    """
    with app.app_context():
        print("Starting backfill process...")
        
        # 1. Tamamlanmış (status='completed') işleri bul
        completed_jobs = Job.query.filter_by(status='completed').all()
        total = len(completed_jobs)
        print(f"Found {total} completed jobs.")
        
        processed = 0
        error_count = 0
        
        # Benzersiz Yıl/Ay ikililerini biriktir
        months_to_update = set()
        
        for job in completed_jobs:
            try:
                record_job_completion(job.id)
                months_to_update.add((job.work_date.year, job.work_date.month))
                processed += 1
                if processed % 100 == 0:
                    print(f"Processed {processed}/{total}")
            except Exception as e:
                print(f"Error processing Job {job.id}: {e}")
                error_count += 1
        
        print(f"Job processing done. updating monthly stats for {len(months_to_update)} periods...")
        
        # 2. Özet tabloları güncelle
        for year, month in months_to_update:
            try:
                print(f"Updating stats for {year}-{month}...")
                update_monthly_stats(year, month)
            except Exception as e:
                print(f"Error updating stats for {year}-{month}: {e}")
        
        print("Backfill completed.")
        print(f"Total: {total}, Success: {processed}, Error: {error_count}")

if __name__ == "__main__":
    backfill_analytics()
