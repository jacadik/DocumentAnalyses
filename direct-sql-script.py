import sqlite3
import os

# Determine the base directory (where app.py is located)
base_dir = os.path.abspath(os.getcwd())

# Path to your database file - we'll look in a few common locations
possible_paths = [
    os.path.join(base_dir, 'instance', 'document_analyzer.db'),
    os.path.join(base_dir, 'document_analyzer.db'),
    os.path.join(base_dir, 'app.db')
]

found_db = False
db_path = None

# Check each possible path
for path in possible_paths:
    if os.path.exists(path):
        db_path = path
        found_db = True
        break

if not found_db:
    print("Database not found in common locations. Please enter the full path to your database file:")
    db_path = input().strip()
    if not os.path.exists(db_path):
        print(f"Error: File not found at {db_path}")
        exit(1)

print(f"Using database at: {db_path}")

# Connect to the database
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the document_paragraph table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_paragraph'")
    if not cursor.fetchone():
        print("Error: document_paragraph table not found in the database.")
        conn.close()
        exit(1)
    
    # Check the structure of the document_paragraph table
    cursor.execute("PRAGMA table_info(document_paragraph)")
    columns = [column[1] for column in cursor.fetchall()]
    print(f"Current columns in document_paragraph: {columns}")
    
    # Check if position column exists
    if 'position' in columns:
        print("Position column already exists. No changes needed.")
    else:
        # Add the position column
        cursor.execute("ALTER TABLE document_paragraph ADD COLUMN position INTEGER")
        conn.commit()
        print("Successfully added 'position' column to document_paragraph table.")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(document_paragraph)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Updated columns in document_paragraph: {columns}")
    
    conn.close()
    print("Database update completed successfully.")
    
except sqlite3.Error as e:
    print(f"SQLite error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
