"""Create tables using db.create_all() then run migrations"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

with app.app_context():
    print("Creating all tables using db.create_all()...")
    try:
        db.create_all()
        print("OK: Tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\nNow you can run: flask db stamp head")
    print("This will mark migrations as applied (since tables are already created)")
    print("Or run: flask db upgrade (to apply any pending migrations)")

