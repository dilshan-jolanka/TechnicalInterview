import sqlite3

# Connect to the database
conn = sqlite3.connect('data/mcq_interview.db')
cursor = conn.cursor()

try:
    # Add the code_snippet column if it doesn't exist
    cursor.execute('ALTER TABLE questions ADD COLUMN code_snippet TEXT DEFAULT ""')
    print("Successfully added code_snippet column to questions table")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("code_snippet column already exists")
    else:
        print(f"Error: {e}")

# Create categories table if it doesn't exist
try:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("Successfully created categories table")
    
    # Initialize default categories if table is empty
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ('C#', 'C# Programming Language'),
            ('ASP.NET', 'ASP.NET Framework'),
            ('MS SQL', 'Microsoft SQL Server'),
            ('JavaScript', 'JavaScript Programming'),
            ('HTML/CSS', 'HTML and CSS Web Technologies')
        ]
        cursor.executemany(
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            default_categories
        )
        print("Successfully initialized default categories")
    else:
        print("Categories already exist, skipping initialization")
        
except sqlite3.Error as e:
    print(f"Error creating categories table: {e}")

# Verify the schemas
cursor.execute('PRAGMA table_info(questions)')
columns = cursor.fetchall()
print("\nCurrent questions table schema:")
for i, col in enumerate(columns):
    print(f"{i}: {col[1]} {col[2]}")

cursor.execute('PRAGMA table_info(categories)')
columns = cursor.fetchall()
print("\nCurrent categories table schema:")
for i, col in enumerate(columns):
    print(f"{i}: {col[1]} {col[2]}")

# Show current categories
cursor.execute("SELECT id, name, description, is_active FROM categories")
categories = cursor.fetchall()
print("\nCurrent categories:")
for cat in categories:
    status = "Active" if cat[3] else "Inactive"
    print(f"ID: {cat[0]}, Name: {cat[1]}, Description: {cat[2]}, Status: {status}")

conn.commit()
conn.close()
