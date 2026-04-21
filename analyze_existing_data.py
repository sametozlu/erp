
import os
import sqlite3


# Try to find the database file
db_paths = [
    "planner.db",
    "instance/planner.db"
]

db_path = None
for p in db_paths:
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    print("Database file found in:", db_path)
    # If not found, try to create one or exit? 
    # But user says "Analyze EXISTING data".
    print("ERROR: Database file not found!")
    exit(1)

print(f"Connecting to {db_path}...")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    analysis_report = []

    print(f"Found tables: {tables}")
    
    for table in tables:
        if table.startswith("sqlite_"): continue
        if table in ["alembic_version"]: continue

        # Get columns
        cursor.execute(f"PRAGMA table_info({table})")
        columns_info = cursor.fetchall()
        # (cid, name, type, notnull, dflt_value, pk)
        
        # Check row count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        
        has_data = row_count > 0
        
        for col in columns_info:
            col_name = col[1]
            
            # Check usability - count non-null values
            if has_data:
                cursor.execute(f"SELECT COUNT({col_name}) FROM {table} WHERE {col_name} IS NOT NULL AND {col_name} != ''")
                non_null_count = cursor.fetchone()[0]
                usable = "YES" if non_null_count > 0 else "NO"
            else:
                usable = "NO"
                
            analysis_report.append({
                "Table": table,
                "Column": col_name,
                "Has Data": "YES" if has_data else "NO",
                "Usable": usable,
                "Notes": f"Rows: {row_count}"
            })


    # Print Report
    print("\n--- DATA ANALYSIS REPORT ---")
    header = "{:<25} {:<25} {:<10} {:<10} {:<15}".format("Table", "Column", "Has Data", "Usable", "Notes")
    print(header)
    print("-" * len(header))
    
    for item in analysis_report:
        print("{:<25} {:<25} {:<10} {:<10} {:<15}".format(
            item["Table"][:24], 
            item["Column"][:24], 
            item["Has Data"], 
            item["Usable"], 
            item["Notes"]
        ))
    
    # Specific check for Analytics Tables
    analytics_tables = ['statistics_event', 'monthly_stat']
    for t in analytics_tables:
        if t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            c = cursor.fetchone()[0]
            print(f"\nProbing {t}: {c} rows.")
            if c > 0:
                cursor.execute(f"SELECT * FROM {t} LIMIT 1")
                print("Sample:", cursor.fetchone())
        else:
            print(f"\n{t} does not exist.")

    # Check operational data for deriving stats
    # Check Job table
    if 'job' in tables:
        print("\nChecking 'job' table for potential analytics:")
        cursor.execute("SELECT COUNT(*) FROM job")
        print(f"Total Jobs: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT status, count(*) FROM job GROUP BY status")
        print("Job Status Distribution:", cursor.fetchall())
        
        cursor.execute("SELECT kanban_status, count(*) FROM job GROUP BY kanban_status")
        print("Kanban Status Distribution:", cursor.fetchall())

except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if conn:
        conn.close()
