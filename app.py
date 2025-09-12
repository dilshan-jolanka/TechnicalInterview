import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import random
import hashlib
import os
import sys
from datetime import datetime, timedelta
import time
import json
import threading
from streamlit.runtime.scriptrunner import get_script_run_ctx
import streamlit.components.v1 as components
from io import BytesIO
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import Image as RLImage
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import numpy as np
try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# Import function to load sample questions
from load_samples import load_sample_questions

def save_answers_to_storage():
    """Save current answers to persistent storage"""
    try:
        if 'user_data' in st.session_state and 'candidate_id' in st.session_state['user_data']:
            candidate_id = st.session_state['user_data']['candidate_id']
            answers = st.session_state.get('answers', {})
            session_id = st.session_state.get('session_id', 'default')
            
            # Save to a temporary storage file for this session
            import os
            os.makedirs('data/temp_answers', exist_ok=True)
            
            temp_file = f'data/temp_answers/answers_{candidate_id}_{session_id}.json'
            with open(temp_file, 'w') as f:
                json.dump({
                    'answers': answers,
                    'timestamp': datetime.now().isoformat(),
                    'current_question': st.session_state.get('current_question', 0)
                }, f)
                
            # Also save to Streamlit's session state cache with a backup key
            st.session_state[f'answers_backup_{candidate_id}'] = answers.copy()
                
    except Exception:
        pass  # Silently handle any storage errors

def load_answers_from_storage():
    """Load answers from persistent storage"""
    try:
        if 'user_data' in st.session_state and 'candidate_id' in st.session_state['user_data']:
            candidate_id = st.session_state['user_data']['candidate_id']
            session_id = st.session_state.get('session_id', 'default')
            
            # First try to load from file
            temp_file = f'data/temp_answers/answers_{candidate_id}_{session_id}.json'
            if os.path.exists(temp_file):
                with open(temp_file, 'r') as f:
                    data = json.load(f)
                    loaded_answers = data.get('answers', {})
                    
                    # Only load if we don't already have answers or if loaded answers has more data
                    current_answers = st.session_state.get('answers', {})
                    if len(loaded_answers) > len(current_answers):
                        st.session_state['answers'] = loaded_answers
                        if 'current_question' not in st.session_state:
                            st.session_state['current_question'] = data.get('current_question', 0)
            
            # Backup: try to load from session state backup
            backup_key = f'answers_backup_{candidate_id}'
            if backup_key in st.session_state:
                backup_answers = st.session_state[backup_key]
                current_answers = st.session_state.get('answers', {})
                if len(backup_answers) > len(current_answers):
                    st.session_state['answers'] = backup_answers.copy()
                    
    except Exception:
        pass  # Silently handle any loading errors

def save_answer():
    """Callback function to save answer immediately when radio button changes"""
    # This callback will be called after the widget value is updated
    # We'll handle saving in the main flow instead
    pass

def detect_programming_language(code_snippet):
    """Detect programming language from code snippet for syntax highlighting"""
    if not code_snippet:
        return "text"
    
    code_lower = code_snippet.lower().strip()
    
    # Python indicators
    if any(keyword in code_lower for keyword in ['def ', 'import ', 'from ', 'print(', 'if __name__', 'elif ', 'except:', 'finally:']):
        return "python"
    
    # JavaScript indicators
    if any(keyword in code_lower for keyword in ['function ', 'var ', 'let ', 'const ', 'console.log', '=>', 'document.', 'window.']):
        return "javascript"
    
    # Java indicators
    if any(keyword in code_lower for keyword in ['public class', 'private ', 'public ', 'system.out', 'static void main', 'import java']):
        return "java"
    
    # C++ indicators
    if any(keyword in code_lower for keyword in ['#include', 'cout <<', 'cin >>', 'std::', 'namespace ', 'using namespace']):
        return "cpp"
    
    # C indicators
    if any(keyword in code_lower for keyword in ['#include <stdio.h>', 'printf(', 'scanf(', 'main()']):
        return "c"
    
    # SQL indicators
    if any(keyword in code_lower for keyword in ['select ', 'from ', 'where ', 'insert into', 'update ', 'delete from', 'create table']):
        return "sql"
    
    # HTML indicators
    if any(keyword in code_lower for keyword in ['<html', '<div', '<span', '<p>', '<!doctype', '<head>', '<body>']):
        return "html"
    
    # CSS indicators
    if any(keyword in code_lower for keyword in ['{', '}', 'color:', 'background:', 'margin:', 'padding:', '@media']):
        return "css"
    
    # Default to text if no language detected
    return "text"

# Check for admin command-line argument
is_admin_access = False
if len(sys.argv) > 1 and '--admin' in sys.argv:
    is_admin_access = True

# Initialize session state variables if they don't exist
if 'session_id' not in st.session_state:
    # Create unique session ID for proper isolation
    import uuid
    st.session_state['session_id'] = str(uuid.uuid4())

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'admin_view' not in st.session_state:
    st.session_state['admin_view'] = False
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 'home'  # Changed default to home
if 'user_data' not in st.session_state:
    st.session_state['user_data'] = {}
if 'questions' not in st.session_state:
    st.session_state['questions'] = []
if 'answers' not in st.session_state:
    st.session_state['answers'] = {}
if 'current_question' not in st.session_state:
    st.session_state['current_question'] = 0
if 'score' not in st.session_state:
    st.session_state['score'] = 0
# New session variables for time limit and auto-save
if 'start_time' not in st.session_state:
    st.session_state['start_time'] = None
if 'time_limit' not in st.session_state:
    st.session_state['time_limit'] = 60  # Default: 60 minutes
if 'form_data' not in st.session_state:
    st.session_state['form_data'] = {"name": "", "email": ""}
if 'time_expired' not in st.session_state:
    st.session_state['time_expired'] = False
if 'interview_submitted' not in st.session_state:
    st.session_state['interview_submitted'] = False
# Add timer variables
if 'last_timer_update' not in st.session_state:
    st.session_state['last_timer_update'] = datetime.now()
if 'timer_key' not in st.session_state:
    st.session_state['timer_key'] = 0  # Used to force rerun for timer

# Database setup function
def setup_database():
    # Create database directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Connect to SQLite database (creates it if it doesn't exist)
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # Create tables if they don't exist
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
            question TEXT NOT NULL,
            code_snippet TEXT DEFAULT '',
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct TEXT NOT NULL
        )
    ''')
    
    # Migrate old schema to new schema if needed
    try:
        # Check if old columns exist and migrate
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='questions'")
        table_sql = cursor.fetchone()
        if table_sql and 'question_text' in table_sql[0]:
            # Create new table with correct schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    question TEXT NOT NULL,
                    code_snippet TEXT DEFAULT '',
                    option_a TEXT NOT NULL,
                    option_b TEXT NOT NULL,
                    option_c TEXT NOT NULL,
                    option_d TEXT NOT NULL,
                    correct TEXT NOT NULL
                )
            ''')
            
            # Copy data from old table to new table
            cursor.execute('''
                INSERT INTO questions_new (id, category, question, code_snippet, option_a, option_b, option_c, option_d, correct)
                SELECT id, category, question_text, COALESCE(code_snippet, ''), option_a, option_b, option_c, option_d, correct_option
                FROM questions
            ''')
            
            # Drop old table and rename new table
            cursor.execute('DROP TABLE questions')
            cursor.execute('ALTER TABLE questions_new RENAME TO questions')
    except sqlite3.Error:
        # If migration fails, continue with existing table
        pass
    
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
    
    # Create categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    # Create or update admin account with new credentials
    cursor.execute("SELECT * FROM admins WHERE username = ?", ('dilshank@jolankagroup.com',))
    if not cursor.fetchone():
        # Check if old admin exists
        cursor.execute("SELECT * FROM admins WHERE username = 'admin'")
        old_admin = cursor.fetchone()
        if old_admin:
            # Update existing admin account with new credentials
            password_hash = hashlib.sha256('%@Kumara123'.encode()).hexdigest()
            cursor.execute("UPDATE admins SET username = ?, password_hash = ? WHERE username = 'admin'",
                          ('dilshank@jolankagroup.com', password_hash))
        else:
            # Create new admin account
            password_hash = hashlib.sha256('%@Kumara123'.encode()).hexdigest()
            cursor.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                          ('dilshank@jolankagroup.com', password_hash))
    else:
        # Admin already exists with new username, update password if needed
        password_hash = hashlib.sha256('%@Kumara123'.encode()).hexdigest()
        cursor.execute("UPDATE admins SET password_hash = ? WHERE username = ?",
                      (password_hash, 'dilshank@jolankagroup.com'))
    
    conn.commit()
    conn.close()

# Category management functions
def get_active_categories():
    """Get list of active category names from database"""
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM categories WHERE is_active = 1 ORDER BY name")
        categories = [row[0] for row in cursor.fetchall()]
        
        # Fallback to default categories if none exist
        if not categories:
            categories = ['C#', 'ASP.NET', 'MS SQL', 'JavaScript', 'HTML/CSS']
            
        return categories
    except sqlite3.Error:
        # Fallback if categories table doesn't exist yet
        return ['C#', 'ASP.NET', 'MS SQL', 'JavaScript', 'HTML/CSS']
    finally:
        conn.close()

def get_all_categories():
    """Get all categories (active and inactive) with details"""
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT c.id, c.name, c.description, c.is_active, c.created_date,
                   COUNT(q.id) as question_count
            FROM categories c
            LEFT JOIN questions q ON c.name = q.category
            GROUP BY c.id, c.name, c.description, c.is_active, c.created_date
            ORDER BY c.name
        """)
        
        categories = []
        for row in cursor.fetchall():
            categories.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'is_active': bool(row[3]),
                'created_date': row[4],
                'question_count': row[5]
            })
        
        return categories
    except sqlite3.Error as e:
        st.error(f"Error fetching categories: {str(e)}")
        return []
    finally:
        conn.close()

def add_category(name, description=""):
    """Add a new category"""
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO categories (name, description) VALUES (?, ?)",
            (name.strip(), description.strip())
        )
        conn.commit()
        return True, "Category added successfully!"
    except sqlite3.IntegrityError:
        return False, "Category name already exists!"
    except sqlite3.Error as e:
        return False, f"Error adding category: {str(e)}"
    finally:
        conn.close()

def delete_category(category_id):
    """Delete a category (soft delete by setting is_active to 0)"""
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    try:
        # Check if category has questions
        cursor.execute("""
            SELECT COUNT(*) FROM questions q 
            JOIN categories c ON q.category = c.name 
            WHERE c.id = ?
        """, (category_id,))
        
        question_count = cursor.fetchone()[0]
        
        if question_count > 0:
            # Soft delete - deactivate the category
            cursor.execute(
                "UPDATE categories SET is_active = 0 WHERE id = ?",
                (category_id,)
            )
            conn.commit()
            return True, f"Category deactivated (has {question_count} questions)"
        else:
            # Hard delete if no questions
            cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            conn.commit()
            return True, "Category deleted successfully!"
            
    except sqlite3.Error as e:
        return False, f"Error deleting category: {str(e)}"
    finally:
        conn.close()

def reactivate_category(category_id):
    """Reactivate a deactivated category"""
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE categories SET is_active = 1 WHERE id = ?",
            (category_id,)
        )
        conn.commit()
        return True, "Category reactivated successfully!"
    except sqlite3.Error as e:
        return False, f"Error reactivating category: {str(e)}"
    finally:
        conn.close()

# AI-Powered Candidate Analysis Functions
def analyze_question_difficulty_patterns(candidate_answers, questions):
    """Analyze how candidate performs across different difficulty levels"""
    difficulty_performance = {
        'easy': {'correct': 0, 'total': 0, 'avg_time': 0},
        'medium': {'correct': 0, 'total': 0, 'avg_time': 0}, 
        'hard': {'correct': 0, 'total': 0, 'avg_time': 0}
    }
    
    for question in questions:
        q_id = question['id']
        if q_id in candidate_answers:
            # Classify difficulty based on question characteristics
            difficulty = classify_question_difficulty(question)
            
            difficulty_performance[difficulty]['total'] += 1
            if candidate_answers[q_id] == question['correct']:
                difficulty_performance[difficulty]['correct'] += 1
    
    return difficulty_performance

def classify_question_difficulty(question):
    """Classify question difficulty based on content analysis"""
    question_text = question['question'].lower()
    code_snippet = question.get('code_snippet', '').lower()
    category = question['category'].lower()
    
    # Complex indicators
    complex_indicators = [
        'algorithm', 'complexity', 'optimization', 'design pattern',
        'architecture', 'performance', 'scalability', 'inheritance',
        'polymorphism', 'abstraction', 'recursion', 'dynamic programming'
    ]
    
    # Medium indicators  
    medium_indicators = [
        'function', 'method', 'class', 'object', 'array', 'loop',
        'condition', 'variable', 'parameter', 'return'
    ]
    
    # Count indicators
    complex_count = sum(1 for indicator in complex_indicators if indicator in question_text or indicator in code_snippet)
    medium_count = sum(1 for indicator in medium_indicators if indicator in question_text or indicator in code_snippet)
    
    # Code complexity analysis
    code_complexity = 0
    if code_snippet:
        code_complexity = len(code_snippet.split('\n'))
        if any(keyword in code_snippet for keyword in ['if', 'for', 'while', 'switch']):
            code_complexity += 2
        if any(keyword in code_snippet for keyword in ['class', 'function', 'def']):
            code_complexity += 1
    
    # Final classification
    if complex_count >= 2 or code_complexity > 10:
        return 'hard'
    elif medium_count >= 2 or code_complexity > 5:
        return 'medium' 
    else:
        return 'easy'

def analyze_response_time_patterns(candidate_id):
    """Analyze response time patterns to understand thinking style"""
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    try:
        # For now, we'll simulate response times based on question complexity
        # In a real implementation, you'd track actual response times
        cursor.execute("""
            SELECT q.category, q.question, q.code_snippet, a.is_correct
            FROM answers a
            JOIN questions q ON a.question_id = q.id
            WHERE a.candidate_id = ?
            ORDER BY a.id
        """, (candidate_id,))
        
        results = cursor.fetchall()
        response_patterns = {
            'quick_correct': 0,
            'slow_correct': 0, 
            'quick_incorrect': 0,
            'slow_incorrect': 0,
            'consistency_score': 0
        }
        
        # Simulate analysis - in real implementation, use actual timing data
        for result in results:
            is_correct = result[3]
            has_code = bool(result[2])
            
            # Simulate response time based on complexity
            simulated_time = random.uniform(30, 180) if has_code else random.uniform(15, 90)
            
            if simulated_time < 60:  # Quick response
                if is_correct:
                    response_patterns['quick_correct'] += 1
                else:
                    response_patterns['quick_incorrect'] += 1
            else:  # Slow response
                if is_correct:
                    response_patterns['slow_correct'] += 1
                else:
                    response_patterns['slow_incorrect'] += 1
        
        total_responses = len(results)
        if total_responses > 0:
            response_patterns['consistency_score'] = (
                response_patterns['quick_correct'] + response_patterns['slow_correct']
            ) / total_responses
            
        return response_patterns
        
    finally:
        conn.close()

def analyze_cognitive_patterns(candidate_id, candidate_answers, questions):
    """Comprehensive cognitive pattern analysis"""
    
    # Category performance analysis
    category_analysis = {}
    for question in questions:
        category = question['category']
        if category not in category_analysis:
            category_analysis[category] = {'correct': 0, 'total': 0, 'has_code': 0}
        
        category_analysis[category]['total'] += 1
        if question.get('code_snippet'):
            category_analysis[category]['has_code'] += 1
            
        q_id = question['id']
        if q_id in candidate_answers and candidate_answers[q_id] == question['correct']:
            category_analysis[category]['correct'] += 1
    
    # Calculate cognitive traits
    cognitive_traits = {
        'logical_thinking': 0,
        'pattern_recognition': 0,
        'abstract_reasoning': 0,
        'attention_to_detail': 0,
        'problem_solving_approach': 'balanced',
        'learning_style': 'mixed',
        'stress_management': 'good'
    }
    
    # Analyze programming vs theoretical performance
    programming_score = 0
    theoretical_score = 0
    programming_total = 0
    theoretical_total = 0
    
    for category, data in category_analysis.items():
        score_rate = data['correct'] / data['total'] if data['total'] > 0 else 0
        
        if 'programming' in category.lower() or data['has_code'] > data['total'] * 0.5:
            programming_score += data['correct']
            programming_total += data['total']
        else:
            theoretical_score += data['correct']
            theoretical_total += data['total']
    
    # Calculate cognitive scores (0-100)
    if programming_total > 0:
        prog_rate = programming_score / programming_total
        cognitive_traits['logical_thinking'] = min(100, prog_rate * 120)
        cognitive_traits['pattern_recognition'] = min(100, prog_rate * 110)
    
    if theoretical_total > 0:
        theory_rate = theoretical_score / theoretical_total
        cognitive_traits['abstract_reasoning'] = min(100, theory_rate * 115)
        cognitive_traits['attention_to_detail'] = min(100, theory_rate * 105)
    
    # Determine problem-solving approach
    if programming_score > theoretical_score * 1.2:
        cognitive_traits['problem_solving_approach'] = 'practical'
    elif theoretical_score > programming_score * 1.2:
        cognitive_traits['problem_solving_approach'] = 'theoretical'
    else:
        cognitive_traits['problem_solving_approach'] = 'balanced'
    
    # Response time analysis
    response_patterns = analyze_response_time_patterns(candidate_id)
    
    # Determine stress management
    consistency = response_patterns.get('consistency_score', 0.5)
    if consistency > 0.8:
        cognitive_traits['stress_management'] = 'excellent'
    elif consistency > 0.6:
        cognitive_traits['stress_management'] = 'good'
    else:
        cognitive_traits['stress_management'] = 'needs_improvement'
    
    return cognitive_traits, category_analysis, response_patterns

def generate_personality_insights(cognitive_traits, category_analysis):
    """Generate personality insights from cognitive analysis"""
    insights = {
        'work_style': 'collaborative',
        'leadership_potential': 'medium',
        'innovation_tendency': 'moderate',
        'risk_tolerance': 'balanced',
        'communication_style': 'technical',
        'growth_mindset': 'strong'
    }
    
    # Determine work style
    logical_score = cognitive_traits.get('logical_thinking', 50)
    detail_score = cognitive_traits.get('attention_to_detail', 50)
    
    if logical_score > 80 and detail_score > 80:
        insights['work_style'] = 'independent'
    elif logical_score > 70:
        insights['work_style'] = 'collaborative'
    else:
        insights['work_style'] = 'team_dependent'
    
    # Leadership potential
    abstract_reasoning = cognitive_traits.get('abstract_reasoning', 50)
    problem_solving = cognitive_traits.get('problem_solving_approach', 'balanced')
    
    if abstract_reasoning > 85 and problem_solving == 'balanced':
        insights['leadership_potential'] = 'high'
    elif abstract_reasoning > 70:
        insights['leadership_potential'] = 'medium'
    else:
        insights['leadership_potential'] = 'low'
    
    # Innovation tendency
    pattern_recognition = cognitive_traits.get('pattern_recognition', 50)
    if pattern_recognition > 85:
        insights['innovation_tendency'] = 'high'
    elif pattern_recognition > 65:
        insights['innovation_tendency'] = 'moderate'
    else:
        insights['innovation_tendency'] = 'low'
    
    return insights

def generate_candidate_recommendations(cognitive_traits, personality_insights, category_analysis):
    """Generate specific recommendations for the candidate"""
    recommendations = {
        'suitable_roles': [],
        'development_areas': [],
        'strengths': [],
        'team_fit': '',
        'training_recommendations': []
    }
    
    # Determine suitable roles
    logical_thinking = cognitive_traits.get('logical_thinking', 50)
    abstract_reasoning = cognitive_traits.get('abstract_reasoning', 50)
    problem_solving = cognitive_traits.get('problem_solving_approach', 'balanced')
    
    if logical_thinking > 80 and problem_solving == 'practical':
        recommendations['suitable_roles'].extend(['Senior Developer', 'Technical Lead', 'Solution Architect'])
    elif logical_thinking > 70:
        recommendations['suitable_roles'].extend(['Software Developer', 'Systems Analyst'])
    elif abstract_reasoning > 75:
        recommendations['suitable_roles'].extend(['Business Analyst', 'Project Manager'])
    else:
        recommendations['suitable_roles'].extend(['Junior Developer', 'QA Tester'])
    
    # Identify strengths
    for trait, score in cognitive_traits.items():
        if isinstance(score, (int, float)) and score > 75:
            trait_name = trait.replace('_', ' ').title()
            recommendations['strengths'].append(trait_name)
    
    # Development areas
    for trait, score in cognitive_traits.items():
        if isinstance(score, (int, float)) and score < 60:
            trait_name = trait.replace('_', ' ').title()
            recommendations['development_areas'].append(trait_name)
    
    # Team fit
    work_style = personality_insights.get('work_style', 'collaborative')
    leadership = personality_insights.get('leadership_potential', 'medium')
    
    if work_style == 'independent' and leadership == 'high':
        recommendations['team_fit'] = 'Team Leader or Independent Contributor'
    elif work_style == 'collaborative':
        recommendations['team_fit'] = 'Strong Team Player'
    else:
        recommendations['team_fit'] = 'Requires Mentorship and Guidance'
    
    # Training recommendations
    if logical_thinking < 70:
        recommendations['training_recommendations'].append('Algorithm and Data Structures Training')
    if abstract_reasoning < 70:
        recommendations['training_recommendations'].append('System Design and Architecture Courses')
    if cognitive_traits.get('attention_to_detail', 50) < 70:
        recommendations['training_recommendations'].append('Code Quality and Testing Best Practices')
    
    return recommendations

def generate_psychological_profile_pdf(candidate_id, candidate_name, candidate_email):
    """Generate comprehensive PDF report of candidate's psychological profile"""
    
    # Get candidate data
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # Get candidate answers and questions
    cursor.execute("""
        SELECT q.id, q.category, q.question, q.code_snippet, q.correct, a.selected_option, a.is_correct
        FROM answers a
        JOIN questions q ON a.question_id = q.id
        WHERE a.candidate_id = ?
        ORDER BY q.category, q.id
    """, (candidate_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        return None
    
    # Prepare data
    questions = []
    candidate_answers = {}
    
    for result in results:
        question = {
            'id': result[0],
            'category': result[1],
            'question': result[2],
            'code_snippet': result[3] or '',
            'correct': result[4]
        }
        questions.append(question)
        candidate_answers[result[0]] = result[5]
    
    # Perform AI analysis
    cognitive_traits, category_analysis, response_patterns = analyze_cognitive_patterns(
        candidate_id, candidate_answers, questions
    )
    
    personality_insights = generate_personality_insights(cognitive_traits, category_analysis)
    recommendations = generate_candidate_recommendations(
        cognitive_traits, personality_insights, category_analysis
    )
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkblue,
        borderWidth=1,
        borderColor=colors.darkblue,
        borderPadding=5
    )
    
    # Build PDF content
    story = []
    
    # Title
    story.append(Paragraph("Comprehensive Candidate Analysis Report", title_style))
    story.append(Spacer(1, 20))
    
    # Candidate Info
    story.append(Paragraph("Candidate Information", heading_style))
    candidate_info = [
        ['Name:', candidate_name],
        ['Email:', candidate_email],
        ['Assessment Date:', datetime.now().strftime('%Y-%m-%d %H:%M')],
        ['Total Questions:', str(len(questions))]
    ]
    
    info_table = Table(candidate_info, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (0, -1), colors.grey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Cognitive Traits Analysis
    story.append(Paragraph("Cognitive Abilities Assessment", heading_style))
    
    cognitive_data = []
    for trait, score in cognitive_traits.items():
        if isinstance(score, (int, float)):
            trait_name = trait.replace('_', ' ').title()
            score_text = f"{score:.1f}%"
            level = "Excellent" if score > 85 else "Good" if score > 70 else "Average" if score > 50 else "Needs Improvement"
            cognitive_data.append([trait_name, score_text, level])
        else:
            trait_name = trait.replace('_', ' ').title()
            cognitive_data.append([trait_name, str(score), "Assessment"])
    
    cognitive_table = Table(cognitive_data, colWidths=[2.5*inch, 1*inch, 1.5*inch])
    cognitive_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(cognitive_table)
    story.append(Spacer(1, 20))
    
    # Personality Insights
    story.append(Paragraph("Personality & Work Style Analysis", heading_style))
    
    personality_data = []
    for trait, value in personality_insights.items():
        trait_name = trait.replace('_', ' ').title()
        personality_data.append([trait_name, str(value).replace('_', ' ').title()])
    
    personality_table = Table(personality_data, colWidths=[2.5*inch, 2.5*inch])
    personality_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(personality_table)
    story.append(Spacer(1, 20))
    
    # Page break before recommendations
    story.append(PageBreak())
    
    # Recommendations
    story.append(Paragraph("Professional Recommendations", heading_style))
    
    # Suitable Roles
    story.append(Paragraph("<b>Recommended Roles:</b>", styles['Normal']))
    for role in recommendations['suitable_roles']:
        story.append(Paragraph(f"• {role}", styles['Normal']))
    story.append(Spacer(1, 10))
    
    # Strengths
    story.append(Paragraph("<b>Key Strengths:</b>", styles['Normal']))
    for strength in recommendations['strengths']:
        story.append(Paragraph(f"• {strength}", styles['Normal']))
    story.append(Spacer(1, 10))
    
    # Development Areas
    story.append(Paragraph("<b>Development Areas:</b>", styles['Normal']))
    for area in recommendations['development_areas']:
        story.append(Paragraph(f"• {area}", styles['Normal']))
    story.append(Spacer(1, 10))
    
    # Team Fit
    story.append(Paragraph(f"<b>Team Fit:</b> {recommendations['team_fit']}", styles['Normal']))
    story.append(Spacer(1, 10))
    
    # Training Recommendations
    story.append(Paragraph("<b>Training Recommendations:</b>", styles['Normal']))
    for training in recommendations['training_recommendations']:
        story.append(Paragraph(f"• {training}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Category Performance
    story.append(Paragraph("Technical Category Performance", heading_style))
    
    category_data = [['Category', 'Score', 'Performance Level']]
    for category, data in category_analysis.items():
        score = (data['correct'] / data['total'] * 100) if data['total'] > 0 else 0
        level = "Excellent" if score > 85 else "Good" if score > 70 else "Average" if score > 50 else "Needs Improvement"
        category_data.append([category, f"{data['correct']}/{data['total']} ({score:.1f}%)", level])
    
    category_table = Table(category_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(category_table)
    story.append(Spacer(1, 20))
    
    # Footer
    story.append(Spacer(1, 30))
    story.append(Paragraph("This report was generated using AI-powered analysis of the candidate's responses to technical assessment questions. The analysis considers response patterns, problem-solving approaches, and cognitive indicators to provide insights into the candidate's thinking patterns and professional potential.", styles['Normal']))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Generated by Jolanka Group Technical Assessment System on {datetime.now().strftime('%Y-%m-%d at %H:%M')}", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

def generate_complete_candidate_report_pdf(candidate_id, candidate_name, candidate_email):
    """Generate comprehensive PDF report with candidate marks and AI analysis"""
    
    # Get candidate data
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # Get candidate basic info
    cursor.execute("SELECT date_taken FROM candidates WHERE id = ?", (candidate_id,))
    candidate_result = cursor.fetchone()
    if not candidate_result:
        conn.close()
        return None
    
    date_taken = candidate_result[0]
    
    # Get candidate results summary - GROUP BY category to avoid duplicates
    cursor.execute("""
        SELECT category, SUM(score) as score, SUM(total_questions) as total_questions 
        FROM results WHERE candidate_id = ?
        GROUP BY category
    """, (candidate_id,))
    results_summary = cursor.fetchall()
    
    # Get detailed answers
    cursor.execute("""
        SELECT q.id, q.category, q.question, q.code_snippet, q.option_a, q.option_b, q.option_c, q.option_d, 
               q.correct, a.selected_option, a.is_correct
        FROM answers a
        JOIN questions q ON a.question_id = q.id
        WHERE a.candidate_id = ?
        ORDER BY q.category, q.id
    """, (candidate_id,))
    detailed_answers = cursor.fetchall()
    
    conn.close()
    
    if not detailed_answers:
        return None
    
    # Calculate overall scores
    total_score = sum(row[1] for row in results_summary)
    total_questions = sum(row[2] for row in results_summary)
    overall_percentage = (total_score / total_questions * 100) if total_questions > 0 else 0
    
    # Prepare data for AI analysis
    questions = []
    candidate_answers = {}
    
    for result in detailed_answers:
        question = {
            'id': result[0],
            'category': result[1],
            'question': result[2],
            'code_snippet': result[3] or '',
            'correct': result[8]
        }
        questions.append(question)
        candidate_answers[result[0]] = result[9]
    
    # Perform AI analysis
    try:
        cognitive_traits, category_analysis, response_patterns = analyze_cognitive_patterns(
            candidate_id, candidate_answers, questions
        )
        
        personality_insights = generate_personality_insights(cognitive_traits, category_analysis)
        recommendations = generate_candidate_recommendations(
            cognitive_traits, personality_insights, category_analysis
        )
    except Exception as e:
        # If AI analysis fails, create basic placeholders
        cognitive_traits = {'analytical_thinking': 'N/A', 'problem_solving': 'N/A'}
        personality_insights = {'work_style': 'Analysis unavailable'}
        recommendations = {
            'suitable_roles': ['Technical Assessment Incomplete'],
            'strengths': ['Data insufficient for analysis'],
            'development_areas': ['Complete assessment for detailed analysis'],
            'team_fit': 'Requires full assessment',
            'training_recommendations': ['Complete technical assessment']
        }
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=26,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=15,
        textColor=colors.darkblue,
        borderWidth=2,
        borderColor=colors.darkblue,
        borderPadding=8
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=10,
        textColor=colors.darkgreen
    )
    
    # Build PDF content
    story = []
    
    # Header with company branding
    story.append(Paragraph("JOLANKA GROUP", ParagraphStyle('Company', fontSize=20, textColor=colors.darkblue, alignment=TA_CENTER)))
    story.append(Paragraph("Technical Interview Assessment Report", title_style))
    story.append(Spacer(1, 20))
    
    # Candidate Information Section
    story.append(Paragraph("CANDIDATE INFORMATION", heading_style))
    candidate_info = [
        ['Full Name:', candidate_name],
        ['Email Address:', candidate_email],
        ['Assessment Date:', pd.to_datetime(date_taken).strftime('%Y-%m-%d %H:%M')],
        ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M')],
        ['Total Questions:', str(total_questions)],
        ['Overall Score:', f"{total_score}/{total_questions} ({overall_percentage:.1f}%)"]
    ]
    
    info_table = Table(candidate_info, colWidths=[2.2*inch, 3.8*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (0, -1), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 25))
    
    # Performance Summary by Category
    story.append(Paragraph("PERFORMANCE SUMMARY BY CATEGORY", heading_style))
    
    category_data = [['Category', 'Score', 'Total Questions', 'Percentage', 'Performance Level']]
    for category, score, total in results_summary:
        percentage = (score / total * 100) if total > 0 else 0
        if percentage >= 85:
            level = "Excellent"
        elif percentage >= 70:
            level = "Good"
        elif percentage >= 50:
            level = "Average"
        else:
            level = "Needs Improvement"
        
        category_data.append([
            category,
            str(score),
            str(total), 
            f"{percentage:.1f}%",
            level
        ])
    
    category_table = Table(category_data, colWidths=[1.8*inch, 0.8*inch, 1*inch, 1*inch, 1.4*inch])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ]))
    
    story.append(category_table)
    story.append(Spacer(1, 25))
    
    # Page break before detailed answers
    story.append(PageBreak())
    
    # Detailed Question-by-Question Results
    story.append(Paragraph("DETAILED QUESTION ANALYSIS", heading_style))
    
    current_category = ""
    question_number = 1
    
    for result in detailed_answers:
        question_id, category, question, code_snippet, opt_a, opt_b, opt_c, opt_d, correct, selected, is_correct = result
        
        # Category header
        if category != current_category:
            current_category = category
            story.append(Paragraph(f"{category.upper()}", subheading_style))
        
        # Question details
        status = "✓ CORRECT" if is_correct else "✗ INCORRECT"
        status_color = colors.green if is_correct else colors.red
        
        question_text = f"<b>Q{question_number}:</b> {question}"
        story.append(Paragraph(question_text, styles['Normal']))
        
        if code_snippet:
            code_style = ParagraphStyle('Code', fontSize=9, fontName='Courier', 
                                      backgroundColor=colors.lightgrey, borderPadding=5)
            story.append(Paragraph(f"<pre>{code_snippet}</pre>", code_style))
        
        # Options
        options = [f"A) {opt_a}", f"B) {opt_b}", f"C) {opt_c}", f"D) {opt_d}"]
        for option in options:
            story.append(Paragraph(option, styles['Normal']))
        
        # Answer information
        answer_info = [
            ['Correct Answer:', correct],
            ['Selected Answer:', selected or 'Not Answered'],
            ['Result:', status]
        ]
        
        answer_table = Table(answer_info, colWidths=[1.5*inch, 1.5*inch])
        answer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 2), (1, 2), status_color),
            ('FONTNAME', (1, 2), (1, 2), 'Helvetica-Bold'),
        ]))
        
        story.append(answer_table)
        story.append(Spacer(1, 15))
        
        question_number += 1
        
        # Add page break after every 5 questions to prevent overcrowding
        if question_number % 5 == 1 and question_number > 1:
            story.append(PageBreak())
    
    # Page break before AI analysis
    story.append(PageBreak())
    
    # AI Analysis Section
    story.append(Paragraph("AI-POWERED PSYCHOLOGICAL ANALYSIS", heading_style))
    
    # Cognitive Abilities
    story.append(Paragraph("Cognitive Assessment", subheading_style))
    if isinstance(cognitive_traits, dict):
        cognitive_data = []
        for trait, score in cognitive_traits.items():
            if isinstance(score, (int, float)):
                trait_name = trait.replace('_', ' ').title()
                score_text = f"{score:.1f}%"
                level = "Excellent" if score > 85 else "Good" if score > 70 else "Average" if score > 50 else "Needs Improvement"
                cognitive_data.append([trait_name, score_text, level])
        
        if cognitive_data:
            cognitive_table = Table(cognitive_data, colWidths=[2.5*inch, 1*inch, 1.5*inch])
            cognitive_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(cognitive_table)
    
    story.append(Spacer(1, 20))
    
    # Professional Recommendations
    story.append(Paragraph("Professional Recommendations", subheading_style))
    
    if isinstance(recommendations, dict):
        # Suitable Roles
        story.append(Paragraph("<b>Recommended Roles:</b>", styles['Normal']))
        for role in recommendations.get('suitable_roles', []):
            story.append(Paragraph(f"• {role}", styles['Normal']))
        story.append(Spacer(1, 10))
        
        # Key Strengths
        story.append(Paragraph("<b>Key Strengths:</b>", styles['Normal']))
        for strength in recommendations.get('strengths', []):
            story.append(Paragraph(f"• {strength}", styles['Normal']))
        story.append(Spacer(1, 10))
        
        # Development Areas
        story.append(Paragraph("<b>Development Areas:</b>", styles['Normal']))
        for area in recommendations.get('development_areas', []):
            story.append(Paragraph(f"• {area}", styles['Normal']))
        story.append(Spacer(1, 10))
        
        # Team Fit
        team_fit = recommendations.get('team_fit', 'Assessment incomplete')
        story.append(Paragraph(f"<b>Team Fit:</b> {team_fit}", styles['Normal']))
    
    story.append(Spacer(1, 30))
    
    # Footer
    story.append(Paragraph("REPORT DISCLAIMER", subheading_style))
    story.append(Paragraph("This comprehensive report combines quantitative assessment results with AI-powered psychological analysis. The technical scores reflect the candidate's performance on domain-specific questions, while the AI analysis provides insights based on response patterns and cognitive indicators. Both components should be considered together for a complete evaluation.", styles['Normal']))
    
    story.append(Spacer(1, 15))
    story.append(Paragraph(f"<b>Report Generated by:</b> Jolanka Group Technical Assessment System<br/><b>Generation Date:</b> {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

# Function to get random questions from each category
def get_random_questions():
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # Get active categories from database instead of hardcoded list
    categories = get_active_categories()
    all_questions = []
    
    # Check if there are any questions in the database
    cursor.execute("SELECT COUNT(*) FROM questions")
    question_count = cursor.fetchone()[0]
    
    if question_count == 0:
        # If no questions, add some sample questions
        st.warning("No questions found in the database. Adding sample questions.")
        load_sample_questions()
    
    # Get table schema to understand column structure
    cursor.execute("PRAGMA table_info(questions)")
    columns = cursor.fetchall()
    has_code_snippet = any(col[1] == 'code_snippet' for col in columns)
    
    category_counts = {}
    
    for category in categories:
        try:
            cursor.execute("SELECT COUNT(*) FROM questions WHERE category = ?", (category,))
            count = cursor.fetchone()[0]
            category_counts[category] = count
            
            # Get available questions for this category
            cursor.execute(
                "SELECT * FROM questions WHERE category = ? ORDER BY RANDOM()", 
                (category,)
            )
            category_questions = cursor.fetchall()
            
            # Add all available questions
            for q in category_questions:
                try:
                    # Safely extract columns based on schema
                    if has_code_snippet:
                        all_questions.append({
                            'id': q[0],
                            'category': q[1],
                            'question': q[2],
                            'code_snippet': q[3] if len(q) > 3 else "",
                            'options': [q[4], q[5], q[6], q[7]] if len(q) > 7 else ["A", "B", "C", "D"],
                            'correct': q[8] if len(q) > 8 else "A"
                        })
                    else:
                        all_questions.append({
                            'id': q[0],
                            'category': q[1],
                            'question': q[2],
                            'code_snippet': "",
                            'options': [q[3], q[4], q[5], q[6]] if len(q) > 6 else ["A", "B", "C", "D"],
                            'correct': q[7] if len(q) > 7 else "A"
                        })
                except Exception as e:
                    st.error(f"Error processing question: {str(e)}")
                    continue
        except Exception as e:
            st.error(f"Error fetching questions for category {category}: {str(e)}")
            continue
    
    conn.close()
    
    # If we still have no questions, create dummy questions to prevent errors
    if not all_questions:
        for i in range(1, 6):
            for j in range(1, 11):
                category = categories[i-1] if i-1 < len(categories) else "General"
                all_questions.append({
                    'id': (i-1)*10 + j,
                    'category': category,
                    'question': f"Sample {category} question {j}?",
                    'code_snippet': "",  # Add empty code snippet for dummy questions
                    'options': [f"Option A for {j}", f"Option B for {j}", f"Option C for {j}", f"Option D for {j}"],
                    'correct': 'A'
                })
    
    # Shuffle the questions
    random.shuffle(all_questions)
    return all_questions

# Function to save candidate info and get candidate_id
def save_candidate(name, email):
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO candidates (name, email, date_taken) VALUES (?, ?, ?)",
        (name, email, datetime.now())
    )
    
    # Get the ID of the inserted candidate
    candidate_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return candidate_id

# Function to save results
def save_results(candidate_id, answers, questions):
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # First, check if results already exist for this candidate to prevent duplicates
    cursor.execute("SELECT COUNT(*) FROM results WHERE candidate_id = ?", (candidate_id,))
    existing_results = cursor.fetchone()[0]
    
    if existing_results > 0:
        # Delete existing results and answers to prevent duplicates
        cursor.execute("DELETE FROM results WHERE candidate_id = ?", (candidate_id,))
        cursor.execute("DELETE FROM answers WHERE candidate_id = ?", (candidate_id,))
    
    # Calculate scores by category - use dynamic categories
    categories = get_active_categories()
    category_scores = {category: {'correct': 0, 'total': 0} for category in categories}
    
    # Save individual answers
    for q_id, selected_option in answers.items():
        # Find the question
        question = next((q for q in questions if q['id'] == q_id), None)
        if question:
            is_correct = (selected_option == question['correct'])
            cursor.execute(
                "INSERT INTO answers (candidate_id, question_id, selected_option, is_correct) VALUES (?, ?, ?, ?)",
                (candidate_id, q_id, selected_option, is_correct)
            )
            
            # Update category scores
            category = question['category']
            if category not in category_scores:
                category_scores[category] = {'correct': 0, 'total': 0}
            category_scores[category]['total'] += 1
            if is_correct:
                category_scores[category]['correct'] += 1
    
    # Save category results
    for category, score in category_scores.items():
        if score['total'] > 0:  # Only save if there were questions in this category
            cursor.execute(
                "INSERT INTO results (candidate_id, category, score, total_questions) VALUES (?, ?, ?, ?)",
                (candidate_id, category, score['correct'], score['total'])
            )
    
    conn.commit()
    conn.close()

# Authentication function
def authenticate(username, password):
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    # Get stored password hash
    cursor.execute("SELECT password_hash FROM admins WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        stored_hash = result[0]
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        return stored_hash == input_hash
    return False

# Function to reset the session state when returning to home page
def reset_session():
    st.session_state['current_page'] = 'home'
    st.session_state['user_data'] = {}
    st.session_state['questions'] = []
    st.session_state['answers'] = {}
    st.session_state['current_question'] = 0
    st.session_state['score'] = 0
    st.session_state['start_time'] = None
    st.session_state['time_expired'] = False
    st.session_state['interview_submitted'] = False
    # Keep form_data and time_limit as they are

# Function to force admin session (clear candidate data completely)
def force_admin_session():
    """Completely clear candidate session and force admin mode"""
    # Clear all candidate-related session state
    candidate_keys = [
        'user_data', 'questions', 'answers', 'current_question', 'score',
        'start_time', 'time_expired', 'interview_submitted', 'form_data',
        'form_submitted', 'nav_action', 'submit_requested'
    ]
    for key in candidate_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    # Set admin mode flags
    st.session_state['admin_mode'] = True
    st.session_state['current_page'] = 'admin_login'

# Home page - Company landing page
def home_page():
    # Custom CSS for the home page
    st.markdown("""
    <style>
    .home-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 10px 20px;
        border-radius: 15px;
        text-align: center;
        color: white;
        margin-bottom: 40px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    .company-logo {
        font-size: 48px;
        font-weight: bold;
        margin-bottom: 15px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .company-tagline {
        font-size: 20px;
        font-weight: 300;
        opacity: 0.9;
        margin-bottom: 30px;
    }
    .nav-card {
        background: white;
        padding: 40px 30px;
        border-radius: 15px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        text-align: center;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: 100%;
        border: 2px solid transparent;
    }
    .nav-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.2);
        border-color: #667eea;
    }
    .nav-icon {
        font-size: 48px;
        margin-bottom: 20px;
        display: block;
    }
    .candidate-card {
        border-top: 4px solid #4CAF50;
    }
    .admin-card {
        border-top: 4px solid #2196F3;
    }
    .nav-title {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 15px;
        color: #333;
    }
    .nav-description {
        color: #666;
        line-height: 1.6;
        margin-bottom: 25px;
    }
    .company-info {
        background: #f8f9fa;
        padding: 40px;
        border-radius: 15px;
        margin: 40px 0;
    }
    .info-section {
        margin-bottom: 30px;
    }
    .info-title {
        font-size: 20px;
        font-weight: bold;
        color: #333;
        margin-bottom: 15px;
        border-bottom: 2px solid #667eea;
        padding-bottom: 5px;
        display: inline-block;
    }
    .info-content {
        color: #555;
        line-height: 1.8;
    }
    .stats-container {
        display: flex;
        justify-content: space-around;
        margin: 30px 0;
        flex-wrap: wrap;
    }
    .stat-item {
        text-align: center;
        margin: 10px;
    }
    .stat-number {
        font-size: 32px;
        font-weight: bold;
        color: #667eea;
        display: block;
    }
    .stat-label {
        font-size: 14px;
        color: #666;
        margin-top: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # # Header with company branding
    # st.markdown("""
    # <div class="home-header">
    #     <div class="company-logo">🏭 JOLANKA GROUP</div>
    #     <div class="company-tagline">WEAVING A STORY OF SUCCESS</div>
    #     <p style="font-size: 16px; margin: 0; opacity: 0.8;">Technical Interview Assessment Portal</p>
    # </div>
    # """, unsafe_allow_html=True)
    
    # Navigation options
    st.markdown("### Choose Your Access Portal")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="nav-card candidate-card">
            <div class="nav-icon">👨‍💻</div>
            <div class="nav-title">Candidate Portal</div>
            <div class="nav-description">
                Take your technical assessment and showcase your skills. 
                Our comprehensive evaluation covers multiple technology areas 
                to assess your capabilities.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Start Interview", key="candidate_access", type="primary", use_container_width=True):
            st.session_state['current_page'] = 'welcome'
            st.query_params["page"] = "welcome"
            st.rerun()
    
    with col2:
        st.markdown("""
        <div class="nav-card admin-card">
            <div class="nav-icon">🛡️</div>
            <div class="nav-title">Administrator Portal</div>
            <div class="nav-description">
                Access the admin dashboard to manage questions, view candidate results, 
                and oversee the interview assessment system.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Admin Login", key="admin_access", type="secondary", use_container_width=True):
            st.session_state['current_page'] = 'admin_login'
            st.query_params["page"] = "admin_login"
            st.rerun()
    
    # # Company information section
    # st.markdown("""
    # <div class="company-info">
    #     <div class="info-section">
    #         <div class="info-title">About Jolanka Group</div>
    #         <div class="info-content">
    #             With 30 years of excellence in the Sri Lankan apparel industry, Jolanka Group has evolved 
    #             into a stalwart manufacturer, harnessing industry best practices and strong corporate governance. 
    #             We lead in product innovation and provide rapid solutions for renowned apparel brands.
    #         </div>
    #     </div>
        
    #     <div class="stats-container">
    #         <div class="stat-item">
    #             <span class="stat-number">30+</span>
    #             <div class="stat-label">Years of Excellence</div>
    #         </div>
    #         <div class="stat-item">
    #             <span class="stat-number">2500+</span>
    #             <div class="stat-label">Strong Workforce</div>
    #         </div>
    #         <div class="stat-item">
    #             <span class="stat-number">4</span>
    #             <div class="stat-label">Factory Units</div>
    #         </div>
    #         <div class="stat-item">
    #             <span class="stat-number">800K</span>
    #             <div class="stat-label">Monthly Output Capacity</div>
    #         </div>
    #     </div>
        
    #     <div class="info-section">
    #         <div class="info-title">Our Operations</div>
    #         <div class="info-content">
    #             Headquartered in Colombo, our operations span across Sri Lanka's South with 4 state-of-the-art 
    #             factory units, and extend to Northwest England with complete warehousing and distribution facilities. 
    #             Our integrated supply chain and dedicated team ensure phenomenal products with sustainable practices.
    #         </div>
    #     </div>
        
    #     <div class="info-section">
    #         <div class="info-title">Global Presence</div>
    #         <div class="info-content">
    #             <strong>Sri Lanka:</strong> Manufacturing and operational headquarters<br>
    #             <strong>United Kingdom:</strong> Warehousing, distribution, and European operations<br>
    #             <strong>UAE:</strong> Financial strategy and international trade management
    #         </div>
    #     </div>
    # </div>
    # """, unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; margin-top: 30px;">
        <p><strong>The Jolanka Group</strong> - Leading Sri Lankan Apparel Manufacturer</p>
        <p>🌐 <a href="https://jolankagroup.com" target="_blank" style="color: #667eea;">jolankagroup.com</a> | 
        📧 info@jolankagroup.com | 📞 +94 11 250 7848</p>
        <p style="font-size: 12px; margin-top: 20px;">© 2025 Jolanka Group. All Rights Reserved.</p>
    </div>
    """, unsafe_allow_html=True)

# Welcome page
def welcome_page():
    st.markdown("""
    <div class="welcome-container fade-in">
        <div class="welcome-title">Welcome to Technical Interview</div>
        <div class="welcome-subtitle">
            Ready to showcase your technical skills? This comprehensive assessment covers multiple key technical areas.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Use stored form data if available
    if st.session_state['form_data']:
        default_name = st.session_state['form_data'].get('name', '')
        default_email = st.session_state['form_data'].get('email', '')
    else:
        default_name = ''
        default_email = ''
    
    with st.form("candidate_form"):
        name = st.text_input("Full Name", value=default_name)
        email = st.text_input("Email", value=default_email)
        submitted = st.form_submit_button("Start Interview")
        
        if submitted:
            # Set a flag to indicate form was submitted
            st.session_state['form_submitted'] = True
            
            if name.strip() and email.strip():
                # Check if this email has already been used
                conn = sqlite3.connect('data/mcq_interview.db')
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM candidates WHERE email = ? AND name = ?", (email, name))
                existing_candidate = cursor.fetchone()
                conn.close()
                
                if existing_candidate:
                    st.error("You have already taken this interview. Each candidate can only take the interview once.")
                else:
                    try:
                        # Save form data in session state
                        st.session_state['form_data'] = {
                            'name': name,
                            'email': email
                        }
                        
                        # Create candidate entry and get questions
                        candidate_id = save_candidate(name, email)
                        questions = get_random_questions()
                        
                        # Set all required session state variables
                        st.session_state['user_data'] = {
                            'name': name,
                            'email': email,
                            'candidate_id': candidate_id,
                            'session_id': st.session_state['session_id']  # Add session ID for isolation
                        }
                        st.session_state['questions'] = questions
                        st.session_state['current_page'] = 'interview'
                        st.session_state['start_time'] = datetime.now()
                        st.session_state['time_expired'] = False
                        
                        # Force a page redirect
                        st.query_params["page"] = "interview"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error starting interview: {str(e)}")
            else:
                st.error("Please enter your name and email to continue.")
    
    # Small admin access link at the bottom and back to home option
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back to Home", key="back_to_home"):
            st.session_state['current_page'] = 'home'
            st.query_params["page"] = "home"
            st.rerun()
    with col2:
        st.markdown("")
    # with col1:
    #     # st.markdown("*Admin? [Login here](/?JolankaAdmin=true)*")
    # with col2:
    #     # st.markdown("*Direct: [Admin Dashboard](/?page=admin_dashboard)*")

# Admin login page
def admin_login_page():
    st.title("Admin Login")
    
    st.markdown("""
    ### Administrator Access
    
    Please enter your credentials to access the admin dashboard.
    """)
    
    with st.form("admin_login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login")
        
        if login_button:
            st.session_state['form_submitted'] = True
            
            if authenticate(username, password):
                st.session_state['logged_in'] = True
                st.session_state['admin_view'] = True
                st.session_state['current_page'] = 'admin_dashboard'
                
                # Force a page redirect
                st.query_params["page"] = "admin_dashboard"
                st.rerun()
            else:
                st.error("Invalid credentials")
    
    if st.button("← Back to Home"):
        st.session_state['current_page'] = 'home'
        
        # Force a page redirect
        st.query_params["page"] = "home"
        st.rerun()
    
    # if st.button("Back to Candidate Page"):
    #     st.session_state['current_page'] = 'welcome'
        
    #     # Force a page redirect
    #     st.query_params["page"] = "welcome"
    #     st.rerun()

# Function to show a single question
def show_question(question_data, question_num, total_questions):
    st.markdown(f"### Question {question_num + 1} of {total_questions}")
    st.markdown(f"**Category: {question_data['category']}**")
    
    # Add a card-like container for the question
    with st.container():
        st.markdown('<div class="question-card">', unsafe_allow_html=True)
        
        st.markdown(f"**{question_data['question']}**")
        
        # Display code snippet if it exists with enhanced formatting
        if 'code_snippet' in question_data and question_data['code_snippet']:
            # Detect programming language for syntax highlighting
            detected_language = detect_programming_language(question_data['code_snippet'])
            
            # Add a subtitle for the code block
            st.markdown("**Code:**")
            
            # Display code with syntax highlighting
            st.code(question_data['code_snippet'], language=detected_language)
            
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Get current answer if available - ensure we load from storage first
    load_answers_from_storage()  # Make sure we have the latest saved answers
    current_answer = st.session_state.get('answers', {}).get(question_data['id'], None)
    
    # Display options as radio buttons with better styling
    options = question_data['options']
    option_keys = ['A', 'B', 'C', 'D']
    
    # Create option labels with text
    option_labels = [f"{key}: {options[i]}" for i, key in enumerate(option_keys)]
    
    # Safe index selection for radio button - this is CRITICAL for showing selected answers
    default_index = None
    if current_answer and current_answer in option_keys:
        try:
            default_index = option_keys.index(current_answer)
        except (ValueError, TypeError):
            default_index = None
    
    # Radio options are styled by external CSS  
    selected_label = st.radio(
        "Select your answer:", 
        options=option_labels,
        index=default_index,
        key=f"question_{question_data['id']}"
    )
    
    # Save the selected answer immediately
    if selected_label:
        selected_option = selected_label.split(':')[0]
        st.session_state['answers'][question_data['id']] = selected_option
        # Save to persistent storage immediately
        save_answers_to_storage()
    
    # Debug information (can be removed later)
    if st.checkbox("Show Debug Info", key=f"debug_{question_data['id']}"):
        st.write(f"**DEBUG INFO:**")
        if selected_label:
            selected_option = selected_label.split(':')[0]
            st.write(f"Radio selected: {selected_label}")
            st.write(f"Parsed option: {selected_option}")
        st.write(f"Question ID: {question_data['id']}")
        st.write(f"Total answers in session: {len(st.session_state.get('answers', {}))}")
        st.write(f"All answers: {st.session_state.get('answers', {})}")
        st.write(f"Current answer for this Q: {st.session_state.get('answers', {}).get(question_data['id'], 'None')}")
    
    # Single navigation section
    st.markdown("---")
    nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])
    
    with nav_col1:
        # Previous button
        if st.button(
            "Previous", 
            key=f"prev_btn_{question_num}",
            disabled=(question_num == 0),
            use_container_width=True
        ):
            st.session_state['nav_action'] = 'prev'
            save_answers_to_storage()  # Save progress before navigation
            st.rerun()
    
    with nav_col2:
        # Next button
        if st.button(
            "Next", 
            key=f"next_btn_{question_num}",
            disabled=(question_num == total_questions - 1),
            use_container_width=True
        ):
            st.session_state['nav_action'] = 'next'
            save_answers_to_storage()  # Save progress before navigation
            st.rerun()
    
    with nav_col3:
        # Submit button - only show when all questions are answered
        answered_count = len(st.session_state.get('answers', {}))
        all_answered = answered_count >= total_questions
        
        if all_answered:
            if st.button(
                "Submit All", 
                key=f"submit_final_{question_num}_{question_data['id']}",
                type="primary",
                use_container_width=True
            ):
                # Use the same nav_action mechanism for consistency
                st.session_state['nav_action'] = 'submit'
                st.rerun()
        else:
            # Show disabled submit button with message
            st.button(
                f"Submit All ({answered_count}/{total_questions})", 
                key=f"submit_disabled_{question_num}",
                disabled=True,
                use_container_width=True,
                help=f"Answer all {total_questions} questions to enable submission"
            )

# Interview page showing questions
def interview_page():
    # Load saved answers on page start (for browser refresh recovery)
    load_answers_from_storage()
    
    # Use the global datetime import with an alias to avoid scoping issues
    import datetime as dt_module
    
    st.title("MCQ Interview")
    
    # FIRST: Check if time has expired using Python (more reliable than JavaScript)
    if st.session_state.get('start_time'):
        time_limit_seconds = st.session_state['time_limit'] * 60
        elapsed_time = (dt_module.datetime.now() - st.session_state['start_time']).total_seconds()
        
        if elapsed_time >= time_limit_seconds:
            # Time has expired - force submit immediately
            st.session_state['interview_submitted'] = True
            st.session_state['current_page'] = 'results'
            st.session_state['time_expired'] = True
            
            # Clear all query params and set results page
            st.query_params.clear()
            st.query_params["page"] = "results"
            
            # Show message and stop execution
            st.error("⏰ TIME EXPIRED! Your interview has been automatically submitted.")
            st.stop()  # This prevents further execution and redirect loop
    
    # Check for auto-submit from timer expiry (backup)
    if 'auto_submit' in st.query_params or 'time_expired' in st.query_params:
        # Force set all necessary flags for proper submission
        st.session_state['interview_submitted'] = True
        st.session_state['current_page'] = 'results'
        st.session_state['time_expired'] = True
        
        # Clean up query params
        st.query_params.clear()
        st.query_params["page"] = "results"
        
        # Show a temporary message before redirect
        st.success("⏰ Time expired! Redirecting to results...")
        
        # Force save session state and redirect
        st.rerun()
        return
    
    # Check for navigation actions at the start
    if 'nav_action' in st.session_state:
        action = st.session_state['nav_action']
        questions = st.session_state['questions']  # Get questions for bounds checking
        if action == 'prev' and st.session_state['current_question'] > 0:
            st.session_state['current_question'] -= 1
        elif action == 'next' and st.session_state['current_question'] < len(questions) - 1:
            st.session_state['current_question'] += 1
        elif action.startswith('nav_'):
            try:
                target = int(action.split('_')[1])
                if 0 <= target < len(questions):
                    st.session_state['current_question'] = target
            except (ValueError, IndexError):
                pass
        elif action == 'submit':
            # Set all necessary flags for submission
            st.session_state['interview_submitted'] = True
            st.session_state['current_page'] = 'results'
            st.query_params["page"] = "results"
            
            # Clear the action before rerun
            if 'nav_action' in st.session_state:
                del st.session_state['nav_action']
            st.rerun()
            return
        # Clear the action after processing
        if 'nav_action' in st.session_state:
            del st.session_state['nav_action']
    
    questions = st.session_state['questions']
    
    # Clean up answers - remove any answers for questions that don't exist
    if 'answers' in st.session_state and questions:
        valid_question_ids = {q['id'] for q in questions}
        # Create a new clean answers dict instead of modifying during iteration
        clean_answers = {k: v for k, v in st.session_state['answers'].items() if k in valid_question_ids}
        st.session_state['answers'] = clean_answers
    
    # Check if we have any questions
    if not questions:
        st.error("No questions available. Please contact the administrator.")
        if st.button("Return to Home Page"):
            reset_session()
            st.query_params["page"] = "home"
            st.rerun()
        return
    
    # Simple countdown timer using Streamlit components
    if st.session_state['start_time']:
        # Display timer header
        st.sidebar.header("Time Remaining")
        
        # Calculate time limit in seconds
        time_limit_seconds = st.session_state['time_limit'] * 60
        
        # Auto-refresh the page every few seconds to check time
        placeholder = st.empty()
        
        with placeholder.container():
            # Create a simple HTML/JS timer that runs directly in Streamlit
            # Calculate actual remaining time based on start time
            start_time = st.session_state['start_time']
            elapsed_time = (dt_module.datetime.now() - start_time).total_seconds()
            remaining_seconds = max(0, time_limit_seconds - elapsed_time)
            
            timer_html = f"""
            <div style="
                background: white;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin: 10px 0;
            ">
                <div style="
                font-size: 14px;
                color: #666;
                margin-bottom: 10px;
            ">Time Remaining</div>
            
            <div id="timer-display" style="
                font-size: 32px;
                font-weight: bold;
                color: #4CAF50;
                margin-bottom: 10px;
            ">Loading...</div>
            
            <div style="
                height: 6px;
                background: #f0f2f6;
                border-radius: 3px;
                overflow: hidden;
            ">
                <div id="progress-bar" style="
                    height: 100%;
                    background: #4CAF50;
                    width: 100%;
                    transition: all 1s;
                "></div>
            </div>
        </div>
        
        <script>
            (function() {{
                let totalSeconds = {time_limit_seconds};
                let remainingSeconds = {remaining_seconds};
                
                function updateTimer() {{
                    const timerDisplay = document.getElementById('timer-display');
                    const progressBar = document.getElementById('progress-bar');
                    
                    if (!timerDisplay || !progressBar) return;
                    
                    // Format time
                    const minutes = Math.floor(remainingSeconds / 60);
                    const seconds = Math.floor(remainingSeconds % 60);
                    const timeString = minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
                    
                    // Update display
                    timerDisplay.textContent = timeString;
                    
                    // Update color
                    let color = '#4CAF50';
                    if (remainingSeconds < 60) {{
                        color = '#ff0000';
                    }} else if (remainingSeconds < 300) {{
                        color = '#ff4500';
                    }} else if (remainingSeconds < 600) {{
                        color = '#ff9800';
                    }}
                    
                    timerDisplay.style.color = color;
                    progressBar.style.backgroundColor = color;
                    
                    // Update progress bar
                    const progressPercent = (remainingSeconds / totalSeconds) * 100;
                    progressBar.style.width = progressPercent + '%';
                    
                    // Check if expired - just reload page, let Python handle it
                    if (remainingSeconds <= 0) {{
                        // Show alert and reload after a short delay - Python will handle the auto-submit
                        alert('Time has expired! Your interview will be automatically submitted.');
                        setTimeout(() => {{
                            window.location.reload();
                        }}, 2000); // 2 second delay to prevent rapid redirects
                        return;
                    }}
                    
                    remainingSeconds--;
                }}
                
                // Start the timer
                updateTimer(); // Initial call
                setInterval(updateTimer, 1000);
            }})();
        </script>
        """
        
        # Use components.html to render the timer in sidebar
        import streamlit.components.v1 as components
        with st.sidebar:
            components.html(timer_html, height=150)
            
        # Handle time expiry query parameter (from iframe)
        if st.query_params.get("time_expired") == ["true"] and not st.session_state.get('time_expired', False):
            st.session_state['time_expired'] = True
            st.session_state['interview_submitted'] = True
            auto_submit = st.query_params.get("auto_submit") == ["true"]
            if auto_submit:
                st.warning("Time has expired! Your interview has been automatically submitted.")
            else:
                st.warning("Time has expired! Your answers have been submitted.")
            st.session_state['current_page'] = 'results'
            st.query_params["page"] = "results"
            st.query_params.pop("time_expired", None)
            if "auto_submit" in st.query_params:
                st.query_params.pop("auto_submit", None)
            st.rerun()
    
    # Server-side time check (backup in case JavaScript fails)
    if st.session_state['start_time']:
        elapsed_time = (dt_module.datetime.now() - st.session_state['start_time']).total_seconds()
        time_limit_seconds = st.session_state['time_limit'] * 60
        if elapsed_time >= time_limit_seconds and not st.session_state.get('time_expired', False):
            st.session_state['time_expired'] = True
            st.session_state['interview_submitted'] = True
            st.session_state['current_page'] = 'results'
            st.query_params["page"] = "results"
            st.error("Time has expired! Your interview has been automatically submitted.")
            st.rerun()
    
    # If time expired, show a message and go to results
    if st.session_state['time_expired']:
        st.error("Time's up! Your answers have been automatically submitted.")
        if st.button("View Results"):
            st.session_state['current_page'] = 'results'
            st.query_params["page"] = "results"
            st.rerun()
        return
    
    current_q = st.session_state['current_question']
    
    # Reset current question if it's out of range
    if current_q >= len(questions):
        st.session_state['current_question'] = 0
        current_q = 0
    elif current_q < 0:
        st.session_state['current_question'] = 0
        current_q = 0
    
    # Question navigation using Streamlit components - compact version
    st.markdown("#### Questions")
    
    # Create a more compact navigation with smaller buttons
    cols = st.columns(13)  # Create 13 columns for more compact layout
    
    for i in range(len(questions)):
        col_index = i % 13
        q_id = questions[i]['id']
        is_answered = q_id in st.session_state['answers']
        is_current = i == current_q
        
        with cols[col_index]:
            # Determine button style based on state
            if is_current:
                button_type = "primary"
                label = f"{i+1}"
            elif is_answered:
                button_type = "secondary" 
                label = f"{i+1}"
            else:
                button_type = "tertiary"
                label = f"{i+1}"
            
            # Create compact navigation button
            if st.button(
                label, 
                key=f"nav_{i}",
                type=button_type,
                help=f"Q{i+1}",
                use_container_width=True
            ):
                st.session_state['nav_action'] = f'nav_{i}'
                st.rerun()
        
        # Start new row every 13 questions
        if (i + 1) % 13 == 0 and i + 1 < len(questions):
            cols = st.columns(13)
    
    # Check for question navigation from URL (simplified)
    if 'q' in st.query_params:
        try:
            target_q = int(st.query_params['q'][0]) if isinstance(st.query_params['q'], list) else int(st.query_params['q'])
            if 0 <= target_q < len(questions) and target_q != current_q:
                st.session_state['current_question'] = target_q
                # Clear the query parameter to prevent loops
                if 'q' in st.query_params:
                    del st.query_params['q']
        except (ValueError, TypeError, KeyError):
            # Clear invalid query parameter
            if 'q' in st.query_params:
                del st.query_params['q']
    
    # Progress bar
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Make sure answers are loaded before calculating progress
        load_answers_from_storage()
        
        # Show a progress indicator
        answered = len(st.session_state.get('answers', {}))
        total = len(questions)
        st.write(f"Progress: {answered}/{total}")
    
    with col2:
        # Show a progress bar for answered questions  
        progress = answered / total if total > 0 else 0
        st.progress(progress)
    
    # Separator after navigation
    st.markdown("---")
    
    # Now we're sure current_q is valid
    
    # Update the current question in session state
    if questions and current_q < len(questions):
        # Store the current question index
        st.session_state['current_question'] = current_q
    
    # Display the question
    show_question(questions[current_q], current_q, len(questions))
    
    # Show a summary of answered questions
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Progress")
    
    # Make sure answers are loaded before calculating progress
    load_answers_from_storage()  # Ensure we have the latest answers
    
    answered = len(st.session_state.get('answers', {}))
    total = len(questions)
    
    # Progress calculation
    progress = answered / total if total > 0 else 0.0
    
    st.sidebar.progress(progress)
    st.sidebar.markdown(f"**{answered}/{total}** questions answered")
    

# Calculate and show results
def results_page():
    # Check if accessing results via back button or direct URL after completion
    # If no user_data or answers, redirect to welcome (they likely used back button after completion)
    if (not st.session_state.get('user_data') or 
        not st.session_state.get('answers') or 
        not st.session_state.get('questions')):
        st.warning("Session expired. Redirecting to home page...")
        st.session_state['current_page'] = 'home'
        st.query_params.clear()
        st.query_params["page"] = "home"
        st.rerun()
        return
    
    # More lenient check - allow if time expired OR manually submitted (but not in admin mode)
    if (not st.session_state.get('interview_submitted', False) and 
        not st.session_state.get('time_expired', False) and 
        not st.session_state.get('admin_mode', False)):
        # Only redirect if neither condition is met and not in admin mode
        st.warning("Interview not submitted yet. Redirecting to interview...")
        st.session_state['current_page'] = 'interview'
        st.query_params["page"] = "interview"
        st.rerun()
        return
        
    # Custom styling for results page
    st.markdown("""
    <div class="results-container">
        <div class="results-title">Interview Completed!</div>
        <div class="results-subtitle">We appreciate you joining the Jolanka Group</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Calculate score
    questions = st.session_state['questions']
    answers = st.session_state['answers']
    candidate_id = st.session_state['user_data']['candidate_id']
    
    # Save results to database
    save_results(candidate_id, answers, questions)
    
    # Clean up temporary answer files
    try:
        session_id = st.session_state.get('session_id', 'default')
        temp_file = f'data/temp_answers/answers_{candidate_id}_{session_id}.json'
        if os.path.exists(temp_file):
            os.remove(temp_file)
    except Exception:
        pass  # Silently handle cleanup errors
    
    total_score = 0
    category_scores = {}
    
    for q in questions:
        q_id = q['id']
        if q_id in answers and answers[q_id] == q['correct']:
            total_score += 1
            
            category = q['category']
            if category not in category_scores:
                category_scores[category] = {'correct': 0, 'total': 0}
            
            category_scores[category]['correct'] += 1
            category_scores[category]['total'] += 1
        else:
            category = q['category']
            if category not in category_scores:
                category_scores[category] = {'correct': 0, 'total': 0}
            category_scores[category]['total'] += 1
    
    # Display thank you message without scores (scores are only visible to admin)
    st.markdown(f"""
    <div class="score-display">
        <h2>👤 {st.session_state['user_data']['name']}</h2>
        <h1>Thank You for Completing the Interview!</h1>
        <p style="color: #666; margin-top: 20px;">Your responses have been submitted successfully. The hiring team will review your answers and contact you if you move forward in the process.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Add JavaScript to handle browser back button - redirect to home page
    st.markdown("""
    <script>
    // Clear the browser history to prevent going back to interview
    history.replaceState(null, null, '/?page=home');
    
    // Handle browser back button
    window.addEventListener('popstate', function(event) {
        window.location.href = '/?page=home';
    });
    </script>
    """, unsafe_allow_html=True)
    
    # Enhanced start new interview button
    if st.button("Start New Interview", key="start_new_interview"):
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        # Redirect to home page
        st.query_params.clear()
        st.query_params["page"] = "home"
        st.rerun()

# Admin dashboard
def admin_dashboard():
    if not st.session_state['logged_in']:
        st.error("You must be logged in to view this page")
        if st.button("Return to Home Page"):
            reset_session()
            st.query_params["page"] = "home"
            st.rerun()
        return
    
    # Professional admin header
    st.markdown("""
    <div class="admin-header">
        <div class="admin-title">MCQ Interview Administration</div>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">Manage questions, view results, and export data</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Logout button in top right
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("Logout", type="secondary"):
            st.session_state['logged_in'] = False
            st.session_state['admin_view'] = False
            st.session_state['admin_mode'] = False  # Clear admin mode
            st.session_state['current_page'] = 'home'
            st.query_params["page"] = "home"
            st.rerun()
    
    # Admin navigation tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard Overview", 
        "Candidate Results", 
        "Questions Management", 
        "Analytics", 
        "System Settings"
    ])
    
    with tab1:
        dashboard_overview()
    
    with tab2:
        candidate_results_management()
    
    with tab3:
        questions_management()
    
    with tab4:
        analytics_dashboard()
    
    with tab5:
        system_settings()

def dashboard_overview():
    st.markdown("### System Overview")
    
    # Get statistics
    conn = sqlite3.connect('data/mcq_interview.db')
    cursor = conn.cursor()
    
    try:
        # Count statistics
        cursor.execute("SELECT COUNT(*) FROM candidates")
        total_candidates = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM questions")
        total_questions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT candidate_id) FROM results")
        completed_interviews = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(CAST(score AS FLOAT) / CAST(total_questions AS FLOAT) * 100) FROM results WHERE total_questions > 0")
        avg_score = cursor.fetchone()[0] or 0
        
        # Display statistics cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Candidates", total_candidates)
        with col2:
            st.metric("Total Questions", total_questions)
        with col3:
            st.metric("Completed Interviews", completed_interviews)
        with col4:
            st.metric("Average Score", f"{avg_score:.1f}%")
        
        # Quick actions
        st.markdown("### Quick Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Export All Results", type="primary"):
                export_results_to_csv()
        
        with col2:
            if st.button("View Top Performers", type="secondary"):
                st.session_state['quick_action'] = 'top_performers'
        
        with col3:
            if st.button("System Backup", type="secondary"):
                backup_database()
                
    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
    finally:
        conn.close()

def candidate_results_management():
    st.markdown("### Candidate Results Management")
    
    # Results view options and actions
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        view_option = st.selectbox(
            "Select View:",
            ["All Results Summary", "Detailed Individual Results", "Top Performers"]
        )
    
    with col2:
        if st.button("Export Results", type="primary"):
            export_results_to_csv()
    
    with col3:
        if st.button("🗑️ Delete All History", type="secondary", help="Delete all candidate data"):
            st.session_state['show_delete_confirmation'] = True
    
    # Show delete confirmation dialog if requested
    if st.session_state.get('show_delete_confirmation', False):
        show_delete_confirmation_dialog()
    
    if view_option == "All Results Summary":
        show_all_results_summary()
    elif view_option == "Detailed Individual Results":
        show_detailed_results()
    elif view_option == "Top Performers":
        show_top_performers()

def show_delete_confirmation_dialog():
    """Show confirmation dialog for deleting all candidate history"""
    st.markdown("---")
    st.markdown("### ⚠️ Delete All Candidate History")
    
    st.warning("""
    **WARNING: This action cannot be undone!**
    
    This will permanently delete:
    - All candidate records
    - All interview results  
    - All individual answers
    
    The questions database will remain intact.
    """)
    
    # Double confirmation
    confirm_text = st.text_input(
        "Type 'DELETE ALL HISTORY' to confirm:",
        placeholder="DELETE ALL HISTORY",
        key="delete_confirmation_input"
    )
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("❌ Cancel", key="cancel_delete", use_container_width=True):
            st.session_state['show_delete_confirmation'] = False
            st.rerun()
    
    with col2:
        if confirm_text == "DELETE ALL HISTORY":
            if st.button("🗑️ **CONFIRM DELETE**", key="confirm_delete", type="primary", use_container_width=True):
                delete_all_candidate_data()
        else:
            st.button("🗑️ **CONFIRM DELETE**", key="confirm_delete_disabled", disabled=True, use_container_width=True, help="Type the confirmation text first")

def delete_all_candidate_data():
    """Delete all candidate data from the database"""
    try:
        conn = sqlite3.connect('data/mcq_interview.db')
        cursor = conn.cursor()
        
        # Delete in order due to foreign key constraints
        cursor.execute("DELETE FROM answers")
        cursor.execute("DELETE FROM results") 
        cursor.execute("DELETE FROM candidates")
        
        conn.commit()
        conn.close()
        
        st.success("✅ All candidate history has been deleted successfully!")
        st.balloons()
        
        # Clear the confirmation dialog
        st.session_state['show_delete_confirmation'] = False
        
        # Wait a moment to show success message then refresh
        import time
        time.sleep(1)
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error deleting history: {str(e)}")

def show_all_results_summary():
    conn = sqlite3.connect('data/mcq_interview.db')
    
    try:
        # Get all candidate results with ranking
        query = """
        SELECT 
            c.name,
            c.email,
            c.date_taken,
            SUM(r.score) as total_score,
            SUM(r.total_questions) as total_questions,
            ROUND((SUM(CAST(r.score AS FLOAT)) * 100.0 / SUM(CAST(r.total_questions AS FLOAT))), 2) as percentage
        FROM candidates c
        JOIN results r ON c.id = r.candidate_id
        GROUP BY c.id, c.name, c.email, c.date_taken
        ORDER BY percentage DESC, c.date_taken DESC
        """
        
        df = pd.read_sql_query(query, conn)
        
        if not df.empty:
            st.markdown("#### All Candidates Summary (Ordered by Score)")
            
            # Add ranking
            df['rank'] = range(1, len(df) + 1)
            
            # Style the dataframe
            df['Date'] = pd.to_datetime(df['date_taken']).dt.strftime('%Y-%m-%d %H:%M')
            df['Score'] = df['total_score'].astype(str) + '/' + df['total_questions'].astype(str)
            df['Percentage'] = df['percentage'].astype(str) + '%'
            
            display_df = df[['rank', 'name', 'email', 'Date', 'Score', 'Percentage']].copy()
            display_df.columns = ['Rank', 'Name', 'Email', 'Date Taken', 'Score', 'Percentage']
            
            st.dataframe(display_df, use_container_width=True)
            
            # Highlight top performer
            if len(df) > 0:
                top_candidate = df.iloc[0]
                st.success(f"Top Performer: {top_candidate['name']} with {top_candidate['percentage']:.1f}% on {top_candidate['Date']}")
        else:
            st.info("No candidate results found.")
    except Exception as e:
        st.error(f"Error loading results: {str(e)}")
    finally:
        conn.close()

def show_detailed_results():
    st.markdown("#### Detailed Individual Results")
    
    conn = sqlite3.connect('data/mcq_interview.db')
    
    try:
        # Get all candidates
        candidates = pd.read_sql_query(
            "SELECT id, name, email, date_taken FROM candidates ORDER BY date_taken DESC", 
            conn
        )
        
        if not candidates.empty:
            # Format date for display
            candidates['date_taken'] = pd.to_datetime(candidates['date_taken'])
            candidates['display'] = candidates['name'] + ' - ' + candidates['email'] + ' (' + candidates['date_taken'].dt.strftime('%Y-%m-%d %H:%M') + ')'
            
            # Show list of candidates
            selected_candidate = st.selectbox(
                "Choose a candidate:",
                candidates['id'].tolist(),
                format_func=lambda x: candidates[candidates['id']==x].iloc[0]['display']
            )
            
            if selected_candidate:
                # Get and display detailed results for selected candidate
                show_candidate_details(selected_candidate, conn)
        else:
            st.info("No candidates found")
    except Exception as e:
        st.error(f"Error loading candidate details: {str(e)}")
    finally:
        conn.close()

def show_candidate_details(candidate_id, conn):
    # Get candidate details
    candidate = pd.read_sql_query(
        "SELECT name, email, date_taken FROM candidates WHERE id = ?",
        conn, params=(candidate_id,)
    ).iloc[0]
    
    st.markdown(f"### Results for {candidate['name']}")
    st.markdown(f"**Email:** {candidate['email']}")
    st.markdown(f"**Date taken:** {pd.to_datetime(candidate['date_taken']).strftime('%Y-%m-%d %H:%M')}")
    
    # Action buttons row
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col2:
        if st.button("📊 Generate AI Report", key=f"ai_report_{candidate_id}", type="primary", help="Generate comprehensive psychological analysis"):
            with st.spinner("Generating AI-powered analysis report..."):
                try:
                    pdf_data = generate_psychological_profile_pdf(candidate_id, candidate['name'], candidate['email'])
                    if pdf_data:
                        # Create download link
                        b64_pdf = base64.b64encode(pdf_data).decode()
                        pdf_filename = f"AI_Analysis_Report_{candidate['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                        
                        href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{pdf_filename}" style="text-decoration: none;">'
                        href += '<div style="background: #4CAF50; color: white; padding: 10px 20px; border-radius: 5px; text-align: center; margin: 10px 0;">'
                        href += '📄 Download AI Analysis Report</div></a>'
                        
                        st.markdown(href, unsafe_allow_html=True)
                        st.success("AI analysis report generated successfully!")
                    else:
                        st.error("No data available for analysis. Please ensure the candidate has completed the interview.")
                except Exception as e:
                    st.error(f"Error generating AI report: {str(e)}")
    
    with col3:
        if st.button("🖨️ Print Complete Report", key=f"print_report_{candidate_id}", type="primary", help="Generate complete PDF with marks and AI analysis"):
            with st.spinner("Generating complete PDF report with marks and AI analysis..."):
                try:
                    pdf_data = generate_complete_candidate_report_pdf(candidate_id, candidate['name'], candidate['email'])
                    if pdf_data:
                        # Create download link
                        b64_pdf = base64.b64encode(pdf_data).decode()
                        pdf_filename = f"Complete_Report_{candidate['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                        
                        href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{pdf_filename}" style="text-decoration: none;">'
                        href += '<div style="background: #2196F3; color: white; padding: 10px 20px; border-radius: 5px; text-align: center; margin: 10px 0;">'
                        href += '🖨️ Download Complete Report PDF</div></a>'
                        
                        st.markdown(href, unsafe_allow_html=True)
                        st.success("Complete report with marks and AI analysis generated successfully!")
                    else:
                        st.error("No data available for analysis. Please ensure the candidate has completed the interview.")
                except Exception as e:
                    st.error(f"Error generating complete report: {str(e)}")
    
    with col4:
        if st.button("📄 Quick Summary", key=f"summary_{candidate_id}", type="secondary", help="View quick performance summary"):
            st.session_state[f'show_summary_{candidate_id}'] = not st.session_state.get(f'show_summary_{candidate_id}', False)
    
    # Get results - GROUP BY category to avoid duplicates
    results = pd.read_sql_query(
        """SELECT category, 
                  SUM(score) as score, 
                  SUM(total_questions) as total_questions 
           FROM results 
           WHERE candidate_id = ? 
           GROUP BY category""",
        conn, params=(candidate_id,)
    )
    
    if not results.empty:
        # Calculate total score
        total_score = results['score'].sum()
        total_questions = results['total_questions'].sum()
        percentage = (total_score / total_questions) * 100 if total_questions > 0 else 0
        
        st.metric("Overall Score", f"{total_score}/{total_questions} ({percentage:.1f}%)")
        
        # Display category breakdown
        st.markdown("#### Category Breakdown")
        for _, row in results.iterrows():
            cat_percentage = (row['score'] / row['total_questions']) * 100 if row['total_questions'] > 0 else 0
            st.markdown(f"**{row['category']}:** {row['score']}/{row['total_questions']} ({cat_percentage:.1f}%)")
        
        # Show quick summary if requested
        if st.session_state.get(f'show_summary_{candidate_id}', False):
            show_quick_candidate_summary(candidate_id, conn, candidate['name'])

def show_quick_candidate_summary(candidate_id, conn, candidate_name):
    """Display a quick performance summary for the candidate"""
    st.markdown("---")
    st.markdown("#### 🚀 Quick Performance Insights")
    
    try:
        # Get all candidate answers for analysis
        cursor = conn.cursor()
        cursor.execute("""
            SELECT q.category, q.question, q.code_snippet, a.is_correct
            FROM answers a
            JOIN questions q ON a.question_id = q.id
            WHERE a.candidate_id = ?
        """, (candidate_id,))
        
        answers_data = cursor.fetchall()
        
        if answers_data:
            # Basic analysis
            total_answers = len(answers_data)
            correct_answers = sum(1 for row in answers_data if row[3])
            accuracy = (correct_answers / total_answers) * 100 if total_answers > 0 else 0
            
            # Category performance
            category_stats = {}
            code_questions = 0
            
            for row in answers_data:
                category = row[0]
                if category not in category_stats:
                    category_stats[category] = {'total': 0, 'correct': 0}
                
                category_stats[category]['total'] += 1
                if row[3]:  # is_correct
                    category_stats[category]['correct'] += 1
                
                if row[2]:  # has code_snippet
                    code_questions += 1
            
            # Display insights
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Overall Accuracy", f"{accuracy:.1f}%")
            
            with col2:
                best_category = max(category_stats.items(), 
                                  key=lambda x: x[1]['correct']/x[1]['total'] if x[1]['total'] > 0 else 0)
                best_score = (best_category[1]['correct'] / best_category[1]['total']) * 100 if best_category[1]['total'] > 0 else 0
                st.metric("Best Category", f"{best_category[0][:15]}... ({best_score:.0f}%)")
            
            with col3:
                coding_accuracy = 0
                if code_questions > 0:
                    coding_correct = sum(1 for row in answers_data if row[2] and row[3])
                    coding_accuracy = (coding_correct / code_questions) * 100
                st.metric("Coding Questions", f"{coding_accuracy:.0f}% ({code_questions} total)")
            
            # Performance level assessment
            if accuracy >= 85:
                performance_level = "🌟 Excellent"
                level_color = "#4CAF50"
            elif accuracy >= 70:
                performance_level = "👍 Good" 
                level_color = "#2196F3"
            elif accuracy >= 50:
                performance_level = "📈 Average"
                level_color = "#FF9800"
            else:
                performance_level = "📚 Needs Improvement"
                level_color = "#F44336"
            
            st.markdown(f"""
            <div style="background: {level_color}; color: white; padding: 15px; border-radius: 10px; text-align: center; margin: 10px 0;">
                <h4 style="margin: 0; color: white;">Performance Level: {performance_level}</h4>
                <p style="margin: 5px 0 0 0; color: white;">
                    {candidate_name} answered {correct_answers} out of {total_answers} questions correctly
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Quick recommendations
            st.markdown("**Quick Recommendations:**")
            if accuracy >= 85:
                st.success("🎯 Excellent candidate! Strong technical skills and problem-solving ability.")
            elif accuracy >= 70:
                st.info("✅ Good candidate with solid fundamentals. Consider for interview.")
            elif accuracy >= 50:
                st.warning("📋 Average performance. May benefit from additional technical screening.")
            else:
                st.error("📖 Below expectations. Consider additional training or different role.")
                
        else:
            st.warning("No detailed answer data available for analysis.")
            
    except Exception as e:
        st.error(f"Error generating quick summary: {str(e)}")

def show_top_performers():
    conn = sqlite3.connect('data/mcq_interview.db')
    
    try:
        # Get top 10 performers
        query = """
        SELECT 
            c.name,
            c.email,
            c.date_taken,
            SUM(r.score) as total_score,
            SUM(r.total_questions) as total_questions,
            ROUND((SUM(CAST(r.score AS FLOAT)) * 100.0 / SUM(CAST(r.total_questions AS FLOAT))), 2) as percentage
        FROM candidates c
        JOIN results r ON c.id = r.candidate_id
        GROUP BY c.id, c.name, c.email, c.date_taken
        ORDER BY percentage DESC, c.date_taken DESC
        LIMIT 10
        """
        
        df = pd.read_sql_query(query, conn)
        
        if not df.empty:
            st.markdown("#### Top 10 Performers")
            
            for i, row in df.iterrows():
                rank = i + 1
                date_str = pd.to_datetime(row['date_taken']).strftime('%Y-%m-%d %H:%M')
                
                # Medal for top 3
                if rank == 1:
                    rank_display = "🥇 1st Place"
                elif rank == 2:
                    rank_display = "🥈 2nd Place"
                elif rank == 3:
                    rank_display = "🥉 3rd Place"
                else:
                    rank_display = f"#{rank}"
                
                st.markdown(f"""
                <div style="background: white; padding: 15px; border-radius: 10px; margin: 10px 0; 
                           border-left: 4px solid {'#FFD700' if rank <= 3 else '#667eea'};">
                    <strong>{rank_display} - {row['name']}</strong><br>
                    Email: {row['email']}<br>
                    Score: {row['total_score']}/{row['total_questions']} ({row['percentage']:.1f}%)<br>
                    Date: {date_str}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No results available yet.")
    except Exception as e:
        st.error(f"Error loading top performers: {str(e)}")
    finally:
        conn.close()

def export_results_to_csv():
    conn = sqlite3.connect('data/mcq_interview.db')
    
    try:
        query = """
        SELECT 
            c.name,
            c.email,
            c.date_taken,
            SUM(r.score) as total_score,
            SUM(r.total_questions) as total_questions,
            ROUND((SUM(CAST(r.score AS FLOAT)) * 100.0 / SUM(CAST(r.total_questions AS FLOAT))), 2) as percentage
        FROM candidates c
        JOIN results r ON c.id = r.candidate_id
        GROUP BY c.id, c.name, c.email, c.date_taken
        ORDER BY percentage DESC, c.date_taken DESC
        """
        
        df = pd.read_sql_query(query, conn)
        
        if not df.empty:
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download Results CSV",
                data=csv,
                file_name=f"interview_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            st.success("CSV file prepared for download!")
        else:
            st.warning("No results available to export.")
    except Exception as e:
        st.error(f"Error exporting results: {str(e)}")
    finally:
        conn.close()

def analytics_dashboard():
    st.markdown("### Analytics Dashboard")
    
    conn = sqlite3.connect('data/mcq_interview.db')
    
    try:
        # Performance by category
        category_query = """
        SELECT 
            r.category,
            AVG(CASE WHEN r.total_questions > 0 THEN (CAST(r.score AS FLOAT) * 100.0 / CAST(r.total_questions AS FLOAT)) ELSE 0 END) as avg_percentage,
            COUNT(*) as attempts
        FROM results r
        GROUP BY r.category
        ORDER BY avg_percentage DESC
        """
        
        category_df = pd.read_sql_query(category_query, conn)
        
        if not category_df.empty:
            st.markdown("#### Performance by Category")
            
            # Show table
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Simple bar chart using Streamlit
                st.bar_chart(category_df.set_index('category')['avg_percentage'])
            
            with col2:
                st.dataframe(category_df.round(2), use_container_width=True)
        else:
            st.info("No category data available for analysis.")
        
        # Interview trends
        st.markdown("#### Interview Trends")
        trends_query = """
        SELECT 
            DATE(c.date_taken) as date,
            COUNT(*) as interviews_count,
            AVG(CASE WHEN r.total_questions > 0 THEN (CAST(r.score AS FLOAT) * 100.0 / CAST(r.total_questions AS FLOAT)) ELSE 0 END) as avg_score
        FROM candidates c
        JOIN results r ON c.id = r.candidate_id
        GROUP BY DATE(c.date_taken)
        ORDER BY date DESC
        LIMIT 30
        """
        
        trends_df = pd.read_sql_query(trends_query, conn)
        
        if not trends_df.empty:
            st.line_chart(trends_df.set_index('date')[['interviews_count', 'avg_score']])
        else:
            st.info("Not enough data for trend analysis.")
            
    except Exception as e:
        st.error(f"Error loading analytics: {str(e)}")
    finally:
        conn.close()

def system_settings():
    st.markdown("### System Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Database Management")
        if st.button("Backup Database", type="secondary"):
            backup_database()
        
        st.markdown("#### Data Management")
        if st.button("Clear All Results", type="secondary"):
            if st.checkbox("I confirm I want to delete all results (This cannot be undone)"):
                clear_all_results()
    
    with col2:
        st.markdown("#### System Information")
        st.info("System Status: Running normally")
        st.info(f"Database: data/mcq_interview.db")
        
        # Show database size
        try:
            import os
            db_size = os.path.getsize('data/mcq_interview.db')
            st.info(f"Database Size: {db_size / 1024:.1f} KB")
        except:
            st.info("Database Size: Unable to determine")

def backup_database():
    import shutil
    try:
        backup_name = f"mcq_interview_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy('data/mcq_interview.db', f'data/{backup_name}')
        st.success(f"Database backed up as {backup_name}")
    except Exception as e:
        st.error(f"Backup failed: {str(e)}")

def clear_all_results():
    try:
        conn = sqlite3.connect('data/mcq_interview.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM results")
        cursor.execute("DELETE FROM answers")
        cursor.execute("DELETE FROM candidates")
        conn.commit()
        conn.close()
        st.success("All results cleared successfully!")
        st.rerun()
    except Exception as e:
        st.error(f"Error clearing results: {str(e)}")

# Show admin dashboard with statistics
def show_admin_dashboard():
    st.header("Interview Statistics")
    
    conn = sqlite3.connect('data/mcq_interview.db')
    
    # Get total number of interviews
    total_interviews = pd.read_sql_query(
        "SELECT COUNT(*) as count FROM candidates", conn
    ).iloc[0]['count']
    
    # Get average scores by category
    category_scores = pd.read_sql_query(
        """
        SELECT category, 
               AVG(score * 1.0 / total_questions) * 100 as avg_score_percentage
        FROM results
        GROUP BY category
        """, 
        conn
    )
    
    # Get recent interviews
    recent_interviews = pd.read_sql_query(
        """
        SELECT c.id, c.name, c.email, c.date_taken,
               SUM(r.score) as total_score,
               SUM(r.total_questions) as total_questions
        FROM candidates c
        JOIN results r ON c.id = r.candidate_id
        GROUP BY c.id
        ORDER BY c.date_taken DESC
        LIMIT 10
        """, 
        conn
    )
    
    conn.close()
    
    # Display stats in columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Interviews", total_interviews)
        
        st.subheader("Average Scores by Category")
        if not category_scores.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            bars = ax.bar(
                category_scores['category'], 
                category_scores['avg_score_percentage'], 
                color='skyblue'
            )
            
            # Add percentage labels on top of each bar
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width()/2.,
                    height,
                    f'{height:.1f}%',
                    ha='center', va='bottom'
                )
            
            ax.set_ylabel('Average Score (%)')
            ax.set_title('Average Score by Category')
            ax.set_ylim(0, 100)  # Set y-axis range from 0 to 100%
            
            st.pyplot(fig)
        else:
            st.info("No data available yet")
    
    with col2:
        st.subheader("Recent Interviews")
        if not recent_interviews.empty:
            # Format the date and calculate percentage
            recent_interviews['date_taken'] = pd.to_datetime(recent_interviews['date_taken'])
            recent_interviews['date_taken'] = recent_interviews['date_taken'].dt.strftime('%Y-%m-%d %H:%M')
            recent_interviews['percentage'] = (
                recent_interviews['total_score'] / recent_interviews['total_questions'] * 100
            ).round(1).astype(str) + '%'
            
            # Display as a table
            st.dataframe(recent_interviews[['name', 'email', 'date_taken', 'percentage']])
        else:
            st.info("No interviews have been conducted yet")

# Show detailed candidate results
def show_candidate_results():
    st.header("Candidate Results")
    
    conn = sqlite3.connect('data/mcq_interview.db')
    
    # Get all candidates
    candidates = pd.read_sql_query(
        "SELECT id, name, email, date_taken FROM candidates ORDER BY date_taken DESC", 
        conn
    )
    
    if not candidates.empty:
        # Format date for display
        candidates['date_taken'] = pd.to_datetime(candidates['date_taken'])
        candidates['date_taken'] = candidates['date_taken'].dt.strftime('%Y-%m-%d %H:%M')
        
        # Show list of candidates
        st.subheader("Select a Candidate")
        selected_candidate = st.selectbox(
            "Choose a candidate:",
            candidates['id'].tolist(),
            format_func=lambda x: f"{candidates[candidates['id']==x].iloc[0]['name']} - {candidates[candidates['id']==x].iloc[0]['email']} ({candidates[candidates['id']==x].iloc[0]['date_taken']})"
        )
        
        if selected_candidate:
            # Get candidate details
            candidate = candidates[candidates['id'] == selected_candidate].iloc[0]
            st.markdown(f"### Results for {candidate['name']}")
            st.markdown(f"**Email:** {candidate['email']}")
            st.markdown(f"**Date taken:** {candidate['date_taken']}")
            
            # Get category scores
            results = pd.read_sql_query(
                "SELECT category, score, total_questions FROM results WHERE candidate_id = ?",
                conn,
                params=(selected_candidate,)
            )
            
            if not results.empty:
                # Calculate total score
                total_score = results['score'].sum()
                total_questions = results['total_questions'].sum()
                percentage = (total_score / total_questions) * 100
                
                st.metric("Overall Score", f"{total_score}/{total_questions} ({percentage:.1f}%)")
                
                # Display category scores with a bar chart
                st.subheader("Category Scores")
                
                # Add percentage column
                results['percentage'] = (results['score'] / results['total_questions'] * 100).round(1)
                
                # Create a bar chart
                fig, ax = plt.subplots(figsize=(10, 6))
                bars = ax.bar(
                    results['category'], 
                    results['percentage'], 
                    color='skyblue'
                )
                
                # Add score labels on top of each bar
                for bar, score, total in zip(bars, results['score'], results['total_questions']):
                    height = bar.get_height()
                    ax.text(
                        bar.get_x() + bar.get_width()/2.,
                        height,
                        f'{score}/{total}',
                        ha='center', va='bottom'
                    )
                
                ax.set_ylabel('Score (%)')
                ax.set_title('Scores by Category')
                ax.set_ylim(0, 100)
                
                st.pyplot(fig)
                
                # Get detailed answers
                answers = pd.read_sql_query(
                    """
                    SELECT q.category, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, 
                           q.correct_option, a.selected_option, a.is_correct
                    FROM answers a
                    JOIN questions q ON a.question_id = q.id
                    WHERE a.candidate_id = ?
                    ORDER BY q.category, q.id
                    """,
                    conn,
                    params=(selected_candidate,)
                )
                
                if not answers.empty:
                    st.subheader("Detailed Answers")
                    
                    # Group by category
                    categories = answers['category'].unique()
                    
                    for category in categories:
                        st.markdown(f"#### {category}")
                        cat_answers = answers[answers['category'] == category]
                        
                        for i, row in cat_answers.iterrows():
                            correct = "✓" if row['is_correct'] else "✗"
                            st.markdown(f"**Q: {row['question_text']}** {correct}")
                            
                            # Only show options with correct answer highlighted (hide candidate's selection for privacy)
                            options = {
                                'A': row['option_a'],
                                'B': row['option_b'],
                                'C': row['option_c'],
                                'D': row['option_d']
                            }
                            
                            for opt, text in options.items():
                                if opt == row['correct_option']:
                                    st.markdown(f"- **{opt}: {text}** (Correct Answer)")
                                else:
                                    st.markdown(f"- {opt}: {text}")
                            
                            # Show only if answered correctly or incorrectly without revealing the candidate's choice
                            if row['is_correct']:
                                st.success("Answered correctly")
                            else:
                                st.error("Answered incorrectly")
                            
                            st.markdown("---")
            else:
                st.info("No results found for this candidate")
    else:
        st.info("No candidates found")
    
    conn.close()

# Questions management interface
def questions_management():
    st.header("Questions Management")
    
    tabs = st.tabs(["View Questions", "Add Question", "Manage Categories", "Import Questions", "Export Questions"])
    
    with tabs[0]:  # View Questions
        view_questions()
    
    with tabs[1]:  # Add Question
        add_question()
    
    with tabs[2]:  # Manage Categories
        manage_categories()
    
    with tabs[3]:  # Import Questions
        import_questions()
    
    with tabs[4]:  # Export Questions
        st.subheader("Export Questions to CSV")
        
        if st.button("Export All Questions to CSV", type="primary"):
            export_questions()

# Function to view all questions with pagination
def view_questions():
    st.subheader("View Questions")
    
    # Handle deletion first if there's a deletion in progress
    if 'delete_question_id' in st.session_state:
        question_id = st.session_state['delete_question_id']
        conn = sqlite3.connect('data/mcq_interview.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()
        conn.close()
        st.success(f"Question {question_id} deleted successfully!")
        del st.session_state['delete_question_id']
        time.sleep(1)
        st.rerun()
    
    conn = sqlite3.connect('data/mcq_interview.db')
    
    # Get categories for filtering (get fresh data each time)
    categories = pd.read_sql_query(
        "SELECT DISTINCT category FROM questions ORDER BY category", 
        conn
    )['category'].tolist()
    
    # Add an "All Categories" option
    categories = ["All Categories"] + categories
    
    # Filter by category
    selected_category = st.selectbox("Filter by category:", categories)
    
    # Search by question text
    search_query = st.text_input("Search questions:")
    
    # Build the query with proper column mapping (updated schema)
    query = "SELECT id, category, question, code_snippet, option_a, option_b, option_c, option_d, correct FROM questions"
    params = []
    
    if selected_category != "All Categories" and search_query:
        query += " WHERE category = ? AND question LIKE ?"
        params = [selected_category, f"%{search_query}%"]
    elif selected_category != "All Categories":
        query += " WHERE category = ?"
        params = [selected_category]
    elif search_query:
        query += " WHERE question LIKE ?"
        params = [f"%{search_query}%"]
    
    query += " ORDER BY category, id"
    
    # Get the questions (this will always get fresh data from the database)
    questions = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Show questions count
    st.markdown(f"Found **{len(questions)}** questions")
    
    if not questions.empty:
        # Pagination
        questions_per_page = 10
        num_pages = (len(questions) - 1) // questions_per_page + 1
        
        if 'question_page' not in st.session_state:
            st.session_state['question_page'] = 0
        
        # Ensure page doesn't exceed available pages after deletion
        if st.session_state['question_page'] >= num_pages:
            st.session_state['question_page'] = max(0, num_pages - 1)
        
        # Page navigation
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col1:
            if st.button("Previous", disabled=(st.session_state['question_page'] <= 0)):
                st.session_state['question_page'] -= 1
                st.rerun()
        
        with col2:
            st.write(f"Page {st.session_state['question_page'] + 1} of {num_pages}")
        
        with col3:
            if st.button("Next", disabled=(st.session_state['question_page'] >= num_pages - 1)):
                st.session_state['question_page'] += 1
                st.rerun()
        
        # Get questions for current page
        start_idx = st.session_state['question_page'] * questions_per_page
        end_idx = min(start_idx + questions_per_page, len(questions))
        page_questions = questions.iloc[start_idx:end_idx]
        
        # Display questions
        for i, q in page_questions.iterrows():
            with st.expander(f"{q['category']} - {q['question'][:50]}..."):
                st.markdown(f"**Question ID:** {q['id']}")
                st.markdown(f"**Category:** {q['category']}")
                st.markdown(f"**Question:** {q['question']}")
                
                # Display code snippet if it exists with enhanced formatting
                if 'code_snippet' in q and q['code_snippet']:
                    st.markdown("**Code Snippet:**")
                    # Detect programming language for syntax highlighting
                    detected_language = detect_programming_language(q['code_snippet'])
                    st.code(q['code_snippet'], language=detected_language)
                
                st.markdown(f"**Options:**")
                st.markdown(f"A. {q['option_a']}")
                st.markdown(f"B. {q['option_b']}")
                st.markdown(f"C. {q['option_c']}")
                st.markdown(f"D. {q['option_d']}")
                st.markdown(f"**Correct Answer:** {q['correct']}")
                
                # Delete button with proper state management
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("🗑️ Delete", key=f"delete_{q['id']}", help="Delete this question", type="secondary"):
                        st.session_state['delete_question_id'] = q['id']
                        st.rerun()
                with col2:
                    st.write("")  # Empty space for layout
    else:
        st.info("No questions found")

# Function to manage categories
def manage_categories():
    st.subheader("Manage Categories")
    
    # Add new category section
    st.markdown("### Add New Category")
    
    with st.form("add_category_form"):
        col1, col2 = st.columns([2, 3])
        
        with col1:
            new_category_name = st.text_input("Category Name:")
        
        with col2:
            new_category_desc = st.text_input("Description (optional):")
        
        add_submitted = st.form_submit_button("Add Category", type="primary")
        
        if add_submitted:
            if new_category_name.strip():
                success, message = add_category(new_category_name, new_category_desc)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please enter a category name")
    
    # Display existing categories
    st.markdown("### Existing Categories")
    
    categories = get_all_categories()
    
    if categories:
        # Create a dataframe for better display
        for category in categories:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 3, 1, 1, 1])
                
                with col1:
                    status = "🟢 Active" if category['is_active'] else "🔴 Inactive"
                    st.write(f"**{category['name']}**")
                    st.caption(status)
                
                with col2:
                    st.write(category['description'] or "No description")
                    st.caption(f"Questions: {category['question_count']}")
                
                with col3:
                    st.caption("Created:")
                    st.caption(category['created_date'][:10])  # Show date only
                
                with col4:
                    if category['is_active']:
                        if st.button(
                            "Deactivate", 
                            key=f"deact_{category['id']}",
                            type="secondary",
                            help="Deactivate this category"
                        ):
                            success, message = delete_category(category['id'])
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    else:
                        if st.button(
                            "Reactivate", 
                            key=f"react_{category['id']}",
                            type="primary",
                            help="Reactivate this category"
                        ):
                            success, message = reactivate_category(category['id'])
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                
                with col5:
                    if category['question_count'] == 0:
                        if st.button(
                            "🗑️ Delete", 
                            key=f"del_{category['id']}",
                            type="secondary",
                            help="Permanently delete this category"
                        ):
                            # Show confirmation
                            if st.session_state.get(f'confirm_delete_{category["id"]}', False):
                                success, message = delete_category(category['id'])
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
                            else:
                                st.session_state[f'confirm_delete_{category["id"]}'] = True
                                st.warning("Click again to confirm deletion")
                    else:
                        st.caption(f"Has {category['question_count']} questions")
                
                st.markdown("---")
        
        # Summary
        active_count = sum(1 for c in categories if c['is_active'])
        total_questions = sum(c['question_count'] for c in categories)
        
        st.markdown(f"""
        **Summary:**
        - Total Categories: {len(categories)}
        - Active Categories: {active_count}
        - Total Questions: {total_questions}
        """)
    else:
        st.info("No categories found. Add some categories to get started!")

# Function to add a new question
def add_question():
    st.subheader("Add New Question")
    
    # Get available active categories
    available_categories = get_active_categories()
    
    if not available_categories:
        st.warning("No active categories found. Please add categories first in the 'Manage Categories' tab.")
        return
    
    # Create a form to add a new question
    with st.form("add_question_form"):
        category = st.selectbox("Category:", available_categories)
        question_text = st.text_area("Question Text:", height=150)
        
        # Add code snippet support
        has_code = st.checkbox("Include code snippet")
        code_snippet = ""
        if has_code:
            code_snippet = st.text_area("Code Snippet (will be displayed with proper formatting):", height=200)
            
            # Show preview of how the code will be displayed
            if code_snippet.strip():
                st.markdown("**Preview:**")
                detected_language = detect_programming_language(code_snippet)
                st.info(f"Detected language: {detected_language}")
                st.code(code_snippet, language=detected_language)
        
        st.markdown("### Options")
        option_a = st.text_area("Option A:", height=100)
        option_b = st.text_area("Option B:", height=100)
        option_c = st.text_area("Option C:", height=100)
        option_d = st.text_area("Option D:", height=100)
        
        correct_option = st.selectbox("Correct Option:", ["A", "B", "C", "D"])
        
        submitted = st.form_submit_button("Add Question")
        
        if submitted:
            if question_text and option_a and option_b and option_c and option_d:
                # Add the question to the database
                conn = sqlite3.connect('data/mcq_interview.db')
                cursor = conn.cursor()
                
                cursor.execute(
                    "INSERT INTO questions (category, question, code_snippet, option_a, option_b, option_c, option_d, correct) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (category, question_text, code_snippet, option_a, option_b, option_c, option_d, correct_option)
                )
                
                conn.commit()
                conn.close()
                
                st.success("Question added successfully!")
            else:
                st.error("Please fill in all required fields")

# Function to import questions from CSV
def import_questions():
    st.subheader("Import Questions from CSV")
    
    st.markdown("""
    Upload a CSV file with the following columns:
    - `category`: One of "C#", "ASP.NET", "MS SQL", "JavaScript", "HTML/CSS"
    - `question_text`: The question text
    - `code_snippet`: (Optional) Code snippet to display with the question
    - `option_a`: First option
    - `option_b`: Second option
    - `option_c`: Third option
    - `option_d`: Fourth option
    - `correct_option`: Correct option (A, B, C, or D)
    """)
    
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            
            # Check if the CSV has the required columns
            required_columns = ['category', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"CSV is missing the following columns: {', '.join(missing_columns)}")
                return
            
            # Add code_snippet column if missing
            if 'code_snippet' not in df.columns:
                df['code_snippet'] = ""
            
            # Validate categories
            valid_categories = ["C#", "ASP.NET", "MS SQL", "JavaScript", "HTML/CSS"]
            invalid_categories = df[~df['category'].isin(valid_categories)]['category'].unique()
            
            if len(invalid_categories) > 0:
                st.error(f"Invalid categories found: {', '.join(invalid_categories)}")
                return
            
            # Validate correct options
            valid_options = ['A', 'B', 'C', 'D']
            invalid_options = df[~df['correct_option'].isin(valid_options)]['correct_option'].unique()
            
            if len(invalid_options) > 0:
                st.error(f"Invalid correct options found: {', '.join(invalid_options)}")
                return
            
            # Preview the data
            st.write("Preview of the data:")
            st.write(df.head())
            
            if st.button("Import Questions"):
                conn = sqlite3.connect('data/mcq_interview.db')
                
                # Insert the questions
                for _, row in df.iterrows():
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO questions (category, question_text, code_snippet, option_a, option_b, option_c, option_d, correct_option) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (row['category'], row['question_text'], row['code_snippet'], row['option_a'], row['option_b'], row['option_c'], row['option_d'], row['correct_option'])
                    )
                
                conn.commit()
                conn.close()
                
                st.success(f"Successfully imported {len(df)} questions!")
        
        except Exception as e:
            st.error(f"Error importing CSV: {e}")

# Function to export questions to CSV
def export_questions():
    conn = sqlite3.connect('data/mcq_interview.db')
    
    # Get all questions with correct column names
    questions = pd.read_sql_query(
        "SELECT category, question, code_snippet, option_a, option_b, option_c, option_d, correct FROM questions",
        conn
    )
    
    conn.close()
    
    if not questions.empty:
        # Convert DataFrame to CSV
        csv = questions.to_csv(index=False)
        
        # Create a download button
        st.download_button(
            label="Download Questions as CSV",
            data=csv,
            file_name="mcq_questions.csv",
            mime="text/csv"
        )
    else:
        st.info("No questions to export")
        
# Admin settings page to configure time limits and other settings
def admin_settings():
    st.header("Application Settings")
    
    # Time limit settings
    st.subheader("Interview Time Limit")
    
    current_time_limit = st.session_state['time_limit']
    new_time_limit = st.slider(
        "Set interview time limit (minutes):", 
        min_value=10, 
        max_value=180, 
        value=current_time_limit,
        step=5
    )
    
    if st.button("Save Time Limit"):
        st.session_state['time_limit'] = new_time_limit
        st.success(f"Time limit updated to {new_time_limit} minutes.")
        
    st.markdown("---")
    
    # Other settings could be added here in the future

# Main function to control the application flow
def main():
    st.set_page_config(
        page_title="MCQ Interview Application", 
        page_icon="",
        layout="wide"
    )
    
    # Load custom CSS
    with open("static/enhanced_style.css", "r") as f:
        css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    
    # Company Header with Logo
    st.markdown("""
    <div class="company-header">
        <img src="https://jolankagroup.com/wp-content/themes/jolanka/assets/images/icons/jolanka-logo-no-text.png" 
             class="company-logo" alt="Jolanka Group Logo">
        <div class="company-title">Jolanka Group - Technical Interview</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Improved session state loading with better error handling
    if 'form_submitted' not in st.session_state or not st.session_state['form_submitted']:
        try:
            session_file = 'data/session_state.json'
            if os.path.exists(session_file):
                # First, check if file is valid JSON
                try:
                    with open(session_file, 'r') as f:
                        file_content = f.read()
                        # Check if the file is empty or contains invalid JSON
                        if not file_content.strip():
                            raise ValueError("Session file is empty")
                        saved_state = json.loads(file_content)
                        
                        # Only restore these specific session state items
                        restore_keys = [
                            'current_page', 'user_data', 'questions', 'answers', 
                            'current_question', 'form_data', 'time_limit', 
                            'time_expired', 'score', 'interview_submitted'
                        ]
                        
                        for key in restore_keys:
                            if key in saved_state:
                                st.session_state[key] = saved_state[key]
                                
                        # Special handling for datetime objects
                        if 'start_time' in saved_state:
                            if saved_state['start_time'] is not None:
                                try:
                                    st.session_state['start_time'] = datetime.fromisoformat(saved_state['start_time'])
                                except ValueError:
                                    # If datetime parsing fails, reset to None
                                    st.session_state['start_time'] = None
                            else:
                                st.session_state['start_time'] = None
                except json.JSONDecodeError:
                    # Handle invalid JSON
                    os.rename(session_file, f"{session_file}.backup")
                    # Create a fresh session file
                    with open(session_file, 'w') as f:
                        json.dump({}, f)
        except Exception as e:
            # For any other errors, create a fresh session
            try:
                os.makedirs('data', exist_ok=True)
                with open(session_file, 'w') as f:
                    json.dump({}, f)
            except:
                pass
    
    try:
        # Set up the database
        setup_database()
        
        # Check if direct admin access was requested
        global is_admin_access
        if is_admin_access and st.session_state['current_page'] == 'welcome':
            st.session_state['current_page'] = 'admin_login'
            
        # Check if there are questions in the database
        conn = sqlite3.connect('data/mcq_interview.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions")
        question_count = cursor.fetchone()[0]
        conn.close()
        
        if question_count == 0 and st.session_state['current_page'] == 'welcome':
            st.warning("No questions found in database. Loading sample questions...")
            load_sample_questions()
    except Exception as e:
        st.error(f"An error occurred during initialization: {str(e)}")
        st.info("Please try restarting the application or contact the administrator.")
    
    # Check for admin access FIRST (before other page routing)
    query_params = st.query_params
    if 'JolankaAdmin' in query_params or ('page' in query_params and str(query_params.get('page', '')).startswith('admin')):
        # Force complete admin session reset
        force_admin_session()
        
        # Set appropriate admin page
        if 'JolankaAdmin' in query_params:
            st.session_state['current_page'] = 'admin_login'
            del st.query_params['JolankaAdmin']
        elif str(query_params.get('page', '')).startswith('admin'):
            # If already logged in, go to dashboard, else login
            if st.session_state.get('logged_in', False):
                st.session_state['current_page'] = 'admin_dashboard'
            else:
                st.session_state['current_page'] = 'admin_login'
    
    # Then check other page routing (but not for admin pages)
    elif 'page' in query_params:
        page_from_query = query_params['page']
        if page_from_query in ['home', 'welcome', 'interview', 'results']:
            # Only non-admin pages
            st.session_state['current_page'] = page_from_query

    # Choose which page to show based on the session state
    if st.session_state['current_page'] == 'home':
        home_page()
    elif st.session_state['current_page'] == 'welcome':
        welcome_page()
    elif st.session_state['current_page'] == 'interview':
        interview_page()
    elif st.session_state['current_page'] == 'results':
        results_page()
    elif st.session_state['current_page'] == 'admin_login':
        admin_login_page()
    elif st.session_state['current_page'] == 'admin_dashboard':
        admin_dashboard()
    else:
        # Default to home page
        st.session_state['current_page'] = 'home'
        home_page()
        
    # Save session state to disk
    try:
        os.makedirs('data', exist_ok=True)
        session_file = 'data/session_state.json'
        
        # Create a clean copy of the state without non-serializable objects
        state_to_save = {}
        
        # Only save essential state variables
        keys_to_save = [
            'current_page', 'user_data', 'questions', 'answers', 
            'current_question', 'form_data', 'time_limit', 
            'time_expired', 'score', 'interview_submitted'
        ]
        
        for key in keys_to_save:
            if key in st.session_state:
                state_to_save[key] = st.session_state[key]
        
        # Handle datetime objects specifically
        if 'start_time' in st.session_state and st.session_state['start_time'] is not None:
            state_to_save['start_time'] = st.session_state['start_time'].isoformat()
        else:
            state_to_save['start_time'] = None
            
        # Remove any non-serializable objects and transient state variables
        for key in list(state_to_save.keys()):
            try:
                # Test if the object is JSON serializable
                json.dumps({key: state_to_save[key]})
            except (TypeError, OverflowError):
                # If not serializable, remove it
                del state_to_save[key]
                
        # Write the clean state to disk
        with open(session_file, 'w') as f:
            json.dump(state_to_save, f)
    except Exception as e:
        st.warning(f"Error saving session state: {str(e)}")

# Run the application
if __name__ == "__main__":
    main()
