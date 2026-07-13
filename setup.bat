@echo off
echo Installing Tech Buy Stock Tool dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Setup failed. Make sure Python is installed and added to PATH.
    echo Download it from https://www.python.org/downloads/ and check
    echo "Add python.exe to PATH" during install.
    pause
    exit /b 1
)
echo.
echo Setup complete. Run start.bat to launch the app.
pause
