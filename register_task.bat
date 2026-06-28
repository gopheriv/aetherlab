@echo off
echo ============================================
echo  AetherLab - Register Scheduled Task
echo  Run this as Administrator!
echo ============================================
echo.

:: Get the directory where this script lives
set "AETHERLAB_DIR=%~dp0"
set "PYTHON_EXE=C:\Python314\pythonw.exe"
set "SCRIPT=%AETHERLAB_DIR%aetherlab_watchdog.py"

schtasks /create ^
  /tn "AetherLab Watchdog" ^
  /tr "\"%PYTHON_EXE%\" \"%SCRIPT%\"" ^
  /sc onlogon ^
  /rl highest ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] Scheduled task "AetherLab Watchdog" created.
    echo      AetherLab GUI will auto-start on every user login.
) else (
    echo.
    echo [FAIL] Could not create task. Run this script as Administrator.
)

echo.
pause
