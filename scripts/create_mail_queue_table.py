import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from extensions import db
from models import MailQueue

def create_table():
    with app.app_context():
        print("Creating MailQueue table...")
        try:
            # Sadece MailQueue tablosunu oluşturmaya çalışalım veya hepsini
            db.create_all()
            print("db.create_all() executed.")
            
            # Check if table exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            if 'mail_queue' in tables:
                print("SUCCESS: 'mail_queue' table exists.")
                # Count items
                count = MailQueue.query.count()
                print(f"Current items in queue: {count}")
                
                pending = MailQueue.query.filter_by(status='pending').count()
                print(f"Pending items: {pending}")
                
                failed = MailQueue.query.filter_by(status='failed').count()
                print(f"Failed items: {failed}")
                
            else:
                print("ERROR: 'mail_queue' table NOT FOUND after create_all.")
                
        except Exception as e:
            print(f"Error creating table: {e}")

if __name__ == "__main__":
    create_table()
