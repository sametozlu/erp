import sys
import os
from datetime import datetime

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from services.mail_service import MailService
from models import MailQueue
from extensions import db

def run_manual_process():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Manuel Mail Process (ZORLA)...")
    
    with app.app_context():
        # 1. Processing olanları zorla pending yap
        stuck = MailQueue.query.filter_by(status='processing').all()
        recovered_count = 0
        if stuck:
            print(f"Processing durumunda {len(stuck)} mail bulundu. Zorla pending'e çekiliyor...")
            for m in stuck:
                m.status = 'pending'
                m.retry_count = 0 # Retry count'u da sıfırlayalım ki tekrar denesin
                m.error_message = None
            db.session.commit()
            recovered_count = len(stuck)
            print(f"Kurtarilan: {recovered_count}")

        # 2. Failed olanları göster
        failed_start = MailQueue.query.filter_by(status='failed').all()
        if failed_start:
            print(f"Baslangicta {len(failed_start)} hatali mail var.")
            for f in failed_start:
                print(f" - ID {f.id} Error: {f.error_message}")

        # 3. İşle
        print(">> MailService.process_queue() baslatiliyor...")
        try:
            # Tek seferde 5 tane işler.
            MailService.process_queue(app)
            print(">> MailService.process_queue() tamamlandi.")
        except Exception as e:
            print(f"ERROR in process_queue: {e}")

        # 4. Sonuç
        db.session.expire_all()
        
        pending = MailQueue.query.filter_by(status='pending').count()
        processing = MailQueue.query.filter_by(status='processing').count()
        failed = MailQueue.query.filter_by(status='failed').count()
        sent = MailQueue.query.filter_by(status='sent').count()
        
        print(f"SON DURUM: Pending={pending}, Processing={processing}, Failed={failed}, Sent={sent}")
        
        # Eğer yine processing'de kaldıysa, gönderim sırasında takılıyor demektir.
        if processing > 0:
            print("DIKKAT: Mailler yine processing durumunda takildi. SMTP timeout olabilir.")

if __name__ == "__main__":
    run_manual_process()
