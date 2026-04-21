import sqlite3
import os

DB_PATH = "instance/planner.db"

def list_tables():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("Tables found:", [t[0] for t in tables])
    conn.close()

if __name__ == "__main__":
    list_tables()
