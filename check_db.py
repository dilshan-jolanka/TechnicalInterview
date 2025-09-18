import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('data/mcq_interview.db')
cursor = conn.cursor()

# Check candidates table
print("=== RECENT CANDIDATES ===")
cursor.execute('SELECT * FROM candidates ORDER BY id DESC LIMIT 5')
candidates = cursor.fetchall()
for row in candidates:
    print(f"ID: {row[0]}, Name: {row[1]}, Email: {row[2]}, Date: {row[3]}")

print("\n=== RECENT RESULTS ===")
cursor.execute('SELECT * FROM results ORDER BY candidate_id DESC LIMIT 10')
results = cursor.fetchall()
for row in results:
    print(f"Candidate ID: {row[0]}, Category: {row[1]}, Score: {row[2]}, Total: {row[3]}, Date: {row[4]}")

print("\n=== RECENT ANSWERS ===")
cursor.execute('SELECT candidate_id, question_id, selected_option, is_correct FROM answers ORDER BY candidate_id DESC LIMIT 10')
answers = cursor.fetchall()
for row in answers:
    print(f"Candidate ID: {row[0]}, Question: {row[1]}, Answer: {row[2]}, Correct: {row[3]}")

# Check if there are any incomplete attempts (candidates with no results)
print("\n=== CANDIDATES WITHOUT RESULTS ===")
cursor.execute('''
SELECT c.id, c.name, c.email 
FROM candidates c 
LEFT JOIN results r ON c.id = r.candidate_id 
WHERE r.candidate_id IS NULL
ORDER BY c.id DESC
''')
incomplete = cursor.fetchall()
for row in incomplete:
    print(f"ID: {row[0]}, Name: {row[1]}, Email: {row[2]} - NO RESULTS")

conn.close()