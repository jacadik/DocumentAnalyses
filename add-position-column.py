import sqlite3
import os

# Determine the base directory (where app.py is located)
base_dir = os.path.abspath(os.getcwd())

# Path to your database file
db_path = os.path.join(base_dir, 'instance', 'document_analyzer.db')

# Print info for debugging
print(f"Looking for database at: {db_path}")
print(f"Database exists: {os.path.exists(db_path)}")

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if the column already exists
    cursor.execute("PRAGMA table_info(document_paragraph)")
    columns = cursor.fetchall()
    
    # Get column names
    column_names = [column[1] for column in columns]
    
    if 'position' not in column_names:
        # Add the position column to the document_paragraph table
        cursor.execute("ALTER TABLE document_paragraph ADD COLUMN position INTEGER;")
        print("Successfully added 'position' column to document_paragraph table")
    else:
        print("Column 'position' already exists in document_paragraph table")
    
    # Commit changes
    conn.commit()
    
except Exception as e:
    print(f"Error: {str(e)}")
    
finally:
    # Close the connection
    conn.close()
