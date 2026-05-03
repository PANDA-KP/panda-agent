@echo off
echo.
echo  ================================
echo    Panda Agent - Install
echo  ================================
echo.
echo  Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  Python not found!
    echo  Please install Python from https://python.org
    echo  Remember to check "Add Python to PATH"
    echo.
    pause
    exit /b
)
echo  Python OK
echo.
echo  Installing packages...
pip install -r requirements.txt
echo.
echo  ================================
echo    Install Done!
echo    Double-click start.bat to run
echo  ================================
echo.
pause
