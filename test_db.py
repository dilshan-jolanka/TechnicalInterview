import sqlite3
from datetime import datetime

# Test database connectivity and operations
conn = sqlite3.connect('data/mcq_interview.db')
cursor = conn.cursor()

try:
    # Test inserting a candidate
    test_name = f"Test_User_{datetime.now().strftime('%H%M%S')}"
    cursor.execute("INSERT INTO candidates (name, email, date_taken) VALUES (?, ?, ?)", 
                   (test_name, "test@test.com", datetime.now().isoformat()))
    test_candidate_id = cursor.lastrowid
    print(f"✓ Successfully inserted test candidate with ID: {test_candidate_id}")
    
    # Test inserting results
    cursor.execute("INSERT INTO results (candidate_id, category, score, total_questions) VALUES (?, ?, ?, ?)",
                   (test_candidate_id, "Test Category", 1, 5))
    print(f"✓ Successfully inserted test result for candidate {test_candidate_id}")
    
    # Test inserting answers
    cursor.execute("INSERT INTO answers (candidate_id, question_id, selected_option, is_correct) VALUES (?, ?, ?, ?)",
                   (test_candidate_id, 1, "A", 1))
    print(f"✓ Successfully inserted test answer for candidate {test_candidate_id}")
    
    conn.commit()
    
    # Verify the data was inserted
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (test_candidate_id,))
    candidate = cursor.fetchone()
    print(f"✓ Verified candidate: {candidate}")
    
    cursor.execute("SELECT * FROM results WHERE candidate_id = ?", (test_candidate_id,))
    results = cursor.fetchall()
    print(f"✓ Verified results: {results}")
    
    cursor.execute("SELECT * FROM answers WHERE candidate_id = ?", (test_candidate_id,))
    answers = cursor.fetchall()
    print(f"✓ Verified answers: {answers}")
    
    print(f"\n✅ Database operations working correctly!")
    
    # Clean up test data
    cursor.execute("DELETE FROM candidates WHERE id = ?", (test_candidate_id,))
    cursor.execute("DELETE FROM results WHERE candidate_id = ?", (test_candidate_id,))
    cursor.execute("DELETE FROM answers WHERE candidate_id = ?", (test_candidate_id,))
    conn.commit()
    print(f"✓ Cleaned up test data")
    
except Exception as e:
    print(f"❌ Database error: {str(e)}")
    import traceback
    traceback.print_exc()
    conn.rollback()

finally:
    conn.close()