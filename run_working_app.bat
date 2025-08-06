@echo off
echo ============================================
echo Flask Working App Launcher
echo ============================================
echo.

echo Stopping any existing Flask processes...
taskkill /f /im python.exe 2>nul

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Starting working Flask application...
echo ============================================
echo.
echo 🔑 LOGIN CREDENTIALS:
echo    Username: admin  
echo    Password: Administrator123!
echo.
echo 🌐 URLS TO TEST:
echo    http://127.0.0.1:5000/hello    (Simple test)
echo    http://127.0.0.1:5000/app      (Login interface)
echo    http://127.0.0.1:5000/test     (API test)
echo.
echo ============================================
echo.

python app_working.py

pause
