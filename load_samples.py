import sqlite3
import pandas as pd
import os
import hashlib

def load_sample_questions():
    print("Checking for sample questions...")
    
    # Connect to the database
    if not os.path.exists('data'):
        os.makedirs('data')
        
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # Check if tables exist, if not create them
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            date_taken TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            question_text TEXT NOT NULL,
            code_snippet TEXT,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_option TEXT,
            is_correct BOOLEAN,
            FOREIGN KEY (candidate_id) REFERENCES candidates (id),
            FOREIGN KEY (question_id) REFERENCES questions (id)
        )
    ''')
    
    # Create default admin account if it doesn't exist
    cursor.execute("SELECT * FROM admins WHERE username = 'admin'")
    if not cursor.fetchone():
        # Hash password 'admin123'
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                      ('admin', password_hash))
        print("Default admin account created.")
    
    # Check if questions table is empty
    cursor.execute("SELECT COUNT(*) FROM questions")
    question_count = cursor.fetchone()[0]
    
    if question_count == 0:
        # Load sample questions if the CSV file exists
        if os.path.exists('sample_questions.csv'):
            try:
                df = pd.read_csv('sample_questions.csv')
                
                # Insert sample questions
                for _, row in df.iterrows():
                    # Check if the CSV has the code_snippet column
                    if 'code_snippet' in row:
                        code_snippet = row['code_snippet']
                    else:
                        code_snippet = ""  # Default empty code snippet
                    
                    cursor.execute(
                        "INSERT INTO questions (category, question_text, code_snippet, option_a, option_b, option_c, option_d, correct_option) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (row['category'], row['question_text'], code_snippet, row['option_a'], row['option_b'], row['option_c'], row['option_d'], row['correct_option'])
                    )
                
                print(f"Successfully loaded {len(df)} sample questions.")
            except Exception as e:
                print(f"Error loading sample questions: {e}")
        else:
            print("Sample questions file not found. No questions were loaded.")
    else:
        print(f"Database already has {question_count} questions. No sample questions loaded.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    load_sample_questions()
