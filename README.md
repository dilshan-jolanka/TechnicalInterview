# MCQ Interview Application

This is a web application for conducting MCQ (Multiple Choice Questions) interviews with the following features:

- Questions with radio button answer selection
- Admin login to view results with bar charts and marks
- Candidates don't need to login, just enter name and email
- Random selection of questions from categories:
  - 10 C# questions
  - 10 ASP.NET questions
  - 10 MS SQL questions
  - 10 JavaScript questions
  - 10 HTML/CSS questions
- **Live timer without page refresh**
- Question navigation bar
- Support for code snippets
- Persistent state between refreshes
- Automatic submission when time expires

## Setup Instructions

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the Streamlit application:
   ```
   streamlit run app.py
   ```

3. The application will start and open in your default web browser at `http://localhost:8501`.

## New Features

### Live Timer With Code Display

The application features an advanced React-based timer that not only updates in real-time without page refresh but also displays the current question's code snippet. This innovative solution:

1. Uses a React component in a separate HTML file (`static/react_timer.html`) 
2. Updates continuously without affecting the main application
3. Displays the code snippet from the current question for easy reference
4. Features a tabbed interface to switch between timer and code views
5. Changes color as time runs low (green → yellow → orange → red)
6. Provides visual feedback with a progress bar
7. Sends a message to the main app when time expires

### Question Navigation

The question navigation bar allows candidates to:
- See which questions have been answered
- Jump directly to specific questions
- Easily track progress through color coding

### Persistent State

The application saves the session state to a JSON file, ensuring that:
- Progress is saved even if the page is refreshed
- Answers are preserved in case of accidental navigation
- The timer continues from where it left off

## Admin Access

Default admin credentials:
- Username: `admin`
- Password: `admin123`

You can also access admin features directly by running:
```
streamlit run app.py -- --admin
```

## Adding Questions

You can add questions in several ways:

1. Manually through the admin interface
2. Import from a CSV file
3. Directly in the database

## Database Structure

The application uses SQLite with the following tables:
- admins: Stores admin credentials
- candidates: Stores information about candidates who take the interview
- questions: Stores all MCQ questions with their options
- results: Stores candidate scores by category
- answers: Stores detailed candidate responses to each question

## Features

### For Candidates
- Simple registration with name and email
- 50 random MCQ questions (10 from each category)
- Immediate feedback after test completion
- Score breakdown by category

### For Admins
- Secure login system
- Dashboard with statistics and visualization
- Detailed candidate results with charts
- Question management (add, view, delete)
- Import/Export questions via CSV

## Sample Question Format (CSV import)

When importing questions via CSV, use the following format:

```
category,question_text,option_a,option_b,option_c,option_d,correct_option
C#,What is C#?,A language,A fruit,A car,A planet,A
```

Valid categories are:
- C#
- ASP.NET
- MS SQL
- JavaScript
- HTML/CSS

Valid correct options are A, B, C, or D.
