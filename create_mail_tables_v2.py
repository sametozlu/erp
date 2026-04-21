from app import app
from extensions import db
from models import MailQueue

with app.app_context():
    print("Checking MailQueue status...")
    
    pending = MailQueue.query.filter_by(status='pending').count()
    processing = MailQueue.query.filter_by(status='processing').count()
    failed = MailQueue.query.filter_by(status='failed').count()
    sent = MailQueue.query.filter_by(status='sent').count()
    
    print(f"Pending: {pending}")
    print(f"Processing: {processing}")
    print(f"Failed: {failed}")
    print(f"Sent: {sent}")
    
    if failed > 0:
        last_failed = MailQueue.query.filter_by(status='failed').order_by(MailQueue.created_at.desc()).first()
        print(f"Last Error (ID: {last_failed.id}): {last_failed.error_message}")
