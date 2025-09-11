@echo off
echo MCQ Interview Application Launcher
echo ==============================

REM Check if Python is installed
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in the PATH. Please install Python and try again.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Load sample questions
echo Loading sample data...
python load_samples.py

REM Run the application
echo Starting Streamlit application...
streamlit run app.py

pause
