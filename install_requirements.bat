@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo   ZeloraTech HR Engine - Install Requirements
echo ===============================================

where python >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=python"
) else (
    set "PY_CMD=py -3"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Please check Python installation.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo Installation failed. Please check your internet connection.
) else (
    echo Installation completed successfully.
)

pause
