@echo off
title AetherLab (with Watchdog)
cd /d "%~dp0"
echo [%date% %time%] Starting AetherLab Watchdog...
echo AetherLab will auto-restart if it crashes.
echo.
python aetherlab_watchdog.py
echo [%date% %time%] Watchdog exited.
