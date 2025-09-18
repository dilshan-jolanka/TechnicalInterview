import sys
import os
sys.path.append(os.path.dirname(__file__))

# Import the required functions
from app import save_results, get_random_questions

# Test data
test_candidate_id = 999  # Use a test ID that won't conflict
test_questions = [
    {
        'id': 1,
        'category': 'Test Category',
        'question': 'Test Question 1',
        'correct': 'A'
    },
    {
        'id': 2,
        'category': 'Test Category',
        'question': 'Test Question 2',
        'correct': 'B'
    },
    {
        'id': 3,
        'category': 'Another Category',
        'question': 'Test Question 3',
        'correct': 'C'
    }
]

# Test with some answers
test_answers = {
    1: 'A',  # Correct
    2: 'C',  # Incorrect
    # Question 3 not answered (incomplete)
}

print("Testing save_results function...")
print(f"Candidate ID: {test_candidate_id}")
print(f"Questions: {len(test_questions)}")
print(f"Answers: {test_answers}")

try:
    # Call save_results
    save_results(test_candidate_id, test_answers, test_questions)
    print("✅ save_results completed successfully!")
    
    # Check what was saved
    import sqlite3
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # Check results table
    cursor.execute("SELECT * FROM results WHERE candidate_id = ?", (test_candidate_id,))
    results = cursor.fetchall()
    print(f"Results saved: {results}")
    
    # Check answers table
    cursor.execute("SELECT * FROM answers WHERE candidate_id = ?", (test_candidate_id,))
    answers = cursor.fetchall()
    print(f"Answers saved: {answers}")
    
    # Cleanup
    cursor.execute("DELETE FROM results WHERE candidate_id = ?", (test_candidate_id,))
    cursor.execute("DELETE FROM answers WHERE candidate_id = ?", (test_candidate_id,))
    conn.commit()
    conn.close()
    
    print("✅ Test completed successfully!")
    
except Exception as e:
    print(f"❌ Error testing save_results: {str(e)}")
    import traceback
    traceback.print_exc()