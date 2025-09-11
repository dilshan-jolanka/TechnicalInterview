@echo off
echo MCQ Interview Application - Direct Admin Access
echo ==========================================

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the application with a special query parameter to go directly to admin page
echo Starting Streamlit application with admin access...
streamlit run app.py -- --admin

pause
