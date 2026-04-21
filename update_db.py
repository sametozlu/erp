import sqlite3
import os

DB_PATH = "instance/planner.db"

def add_column_if_not_exists(cursor, table, column, definition):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"Added column {column} to {table}")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print(f"Column {column} already exists in {table}")
        else:
            print(f"Error adding {column}: {e}")

def update_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Project tablosuna yeni kolonlari ekle
    add_column_if_not_exists(cursor, "project", "initiation_file_path", "TEXT")
    add_column_if_not_exists(cursor, "project", "initiation_file_type", "TEXT")
    add_column_if_not_exists(cursor, "project", "initiation_file_name", "TEXT")
    # SQLite boolean'i INTEGER (0/1) olarak tutar
    add_column_if_not_exists(cursor, "project", "no_initiation_file", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_not_exists(cursor, "project", "no_file_reason", "TEXT")

    conn.commit()
    conn.close()
    print("Database update completed.")

if __name__ == "__main__":
    update_db()
