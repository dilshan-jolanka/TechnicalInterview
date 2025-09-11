#!/usr/bin/env python3
"""
Test script for category management functionality
"""

import sqlite3
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_category_functions():
    """Test the category management functions"""
    
    # Import functions from app
    from app import get_active_categories, get_all_categories, add_category, delete_category, reactivate_category
    
    print("Testing Category Management Functions")
    print("=" * 50)
    
    # Test 1: Get active categories
    print("\n1. Testing get_active_categories():")
    active_categories = get_active_categories()
    print(f"Active categories: {active_categories}")
    
    # Test 2: Get all categories
    print("\n2. Testing get_all_categories():")
    all_categories = get_all_categories()
    for cat in all_categories:
        status = "Active" if cat['is_active'] else "Inactive"
        print(f"  - {cat['name']}: {cat['description']} ({status}) - {cat['question_count']} questions")
    
    # Test 3: Add a new category
    print("\n3. Testing add_category():")
    success, message = add_category("Python", "Python Programming Language")
    print(f"  Add Python category: {message}")
    
    # Test 4: Try to add duplicate category
    print("\n4. Testing duplicate category:")
    success, message = add_category("Python", "Duplicate test")
    print(f"  Add duplicate Python: {message}")
    
    # Test 5: Add another category
    print("\n5. Adding another category:")
    success, message = add_category("React", "React JavaScript Library")
    print(f"  Add React category: {message}")
    
    # Test 6: Show updated categories
    print("\n6. Updated active categories:")
    active_categories = get_active_categories()
    print(f"Active categories: {active_categories}")
    
    # Test 7: Deactivate a category
    print("\n7. Testing category deactivation:")
    # Get the Python category ID
    all_categories = get_all_categories()
    python_cat = next((cat for cat in all_categories if cat['name'] == 'Python'), None)
    if python_cat:
        success, message = delete_category(python_cat['id'])
        print(f"  Deactivate Python: {message}")
    
    # Test 8: Show categories after deactivation
    print("\n8. Categories after deactivation:")
    active_categories = get_active_categories()
    print(f"Active categories: {active_categories}")
    
    # Test 9: Reactivate category
    print("\n9. Testing category reactivation:")
    if python_cat:
        success, message = reactivate_category(python_cat['id'])
        print(f"  Reactivate Python: {message}")
    
    # Test 10: Final state
    print("\n10. Final active categories:")
    active_categories = get_active_categories()
    print(f"Active categories: {active_categories}")
    
    print("\n" + "=" * 50)
    print("Category management tests completed!")

def check_database_schema():
    """Check the database schema"""
    print("\nDatabase Schema Check")
    print("=" * 30)
    
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # Check categories table
    try:
        cursor.execute('PRAGMA table_info(categories)')
        columns = cursor.fetchall()
        print("\nCategories table schema:")
        for col in columns:
            print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else ''}")
    except sqlite3.Error as e:
        print(f"Error checking categories table: {e}")
    
    # Check current data
    try:
        cursor.execute("SELECT name, description, is_active FROM categories ORDER BY name")
        categories = cursor.fetchall()
        print(f"\nCategories in database ({len(categories)} total):")
        for cat in categories:
            status = "Active" if cat[2] else "Inactive"
            print(f"  - {cat[0]}: {cat[1]} ({status})")
    except sqlite3.Error as e:
        print(f"Error reading categories: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_database_schema()
    test_category_functions()
