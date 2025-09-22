@echo off
echo ============================================
echo Flask Application Startup Script
echo ============================================
echo.

echo Checking if virtual environment exists...
if not exist "venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created.
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing required packages from requirements.txt...
pip install -r requirements.txt

echo.

echo Checking if admin user exists...
if not exist "config\users.json" (
    echo Creating admin user...
    python init_admin.py
)

echo.
echo ============================================
echo Starting Flask Application...
echo ============================================
echo.
echo Open your browser and visit:
echo   http://127.0.0.1:5000/hello    (Simple test)
echo   http://127.0.0.1:5000          (Landing page)
echo   http://127.0.0.1:5000/app      (Main application)
echo   http://127.0.0.1:5000/test     (API test)
echo.
echo Press Ctrl+C to stop the server
echo ============================================
echo.


set FLASK_APP=app.py
set FLASK_ENV=development
set FLASK_DEBUG=true
python app.py

pause
