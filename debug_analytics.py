
import sys
import os
import logging
from datetime import date

# Add current dir to path
sys.path.append(os.getcwd())

from flask import Flask
from extensions import db
from models import * # Import all models to ensure registry
from services.analytics_service import AnalyticsRobot

app = Flask(__name__)
# Use absolute path to ensure DB is found
db_path = os.path.join(os.getcwd(), "instance", "planner.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

def run_tests():
    with app.app_context():
        print(f"DB: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        # Test 1: Query - Project Job Count
        print("\n--- TEST 1: Robot Query (Project) ---")
        try:
            payload = {
                "dimensions": ["project"],
                "metrics": ["job_count"],
                "date_range": {"start": "2023-01-01", "end": "2026-12-31"},
                "bucket": "month"
            }
            res = AnalyticsRobot.query(payload)
            if res.get("error"):
                print("Error:", res["error"])
            else:
                print(f"Success. Rows: {len(res.get('rows', []))}")
                if res.get('rows'):
                    print("Sample:", res['rows'][0])
        except Exception:
            import traceback
            traceback.print_exc()

        # Test 2: Tops
        print("\n--- TEST 2: Tops ---")
        try:
            payload = {
                "date_range": {"start": date(2023,1,1), "end": date(2026,12,31)},
                "limit": 5
            }
            res = AnalyticsRobot.get_tops(payload)
            print("Keys:", res.keys())
            if res.get("cards"):
                print("Person Max Hours:", res["cards"].get("person_max_hours"))
        except Exception:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run_tests()
