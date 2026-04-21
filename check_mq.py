from app import app
from extensions import db
from models import MailQueue
from datetime import datetime

with app.app_context():
    print(f"Status Check [{datetime.now().strftime('%H:%M:%S')}]")
    
    pending = MailQueue.query.filter_by(status='pending').count()
    processing = MailQueue.query.filter_by(status='processing').count()
    failed = MailQueue.query.filter_by(status='failed').count()
    sent = MailQueue.query.filter_by(status='sent').count()
    
    print(f"Pending: {pending}")
    print(f"Processing: {processing}")
    print(f"Failed: {failed}")
    print(f"Sent: {sent}")
    
    if failed > 0:
        # Son hatayı al
        last = MailQueue.query.filter_by(status='failed').order_by(MailQueue.id.desc()).first()
        if last:
            print(f"LAST ERROR (ID {last.id}): {last.error_message}")
            if last.retry_count:
                print(f"Retries: {last.retry_count}")
