# Save this as fix_database.py and run it with python fix_database.py

import sqlite3
import os

# Get the correct path to your database (adjust if needed)
db_path = 'instance/document_analyzer.db'

# Make sure the database exists
if not os.path.exists(db_path):
    print(f"Database file not found at: {db_path}")
    exit(1)

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if preview_data column exists
cursor.execute("PRAGMA table_info(document)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

if 'preview_data' not in column_names:
    print("Adding preview_data column to document table...")
    try:
        # Add the column
        cursor.execute("ALTER TABLE document ADD COLUMN preview_data TEXT")
        conn.commit()
        print("Column added successfully!")
    except sqlite3.OperationalError as e:
        print(f"Error adding column: {e}")
        conn.rollback()
else:
    print("preview_data column already exists.")

# Close connection
conn.close()
print("Database update complete.")
