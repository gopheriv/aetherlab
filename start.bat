@echo off
title PhysLab (with Watchdog)
cd /d "%~dp0"
echo [%date% %time%] Starting PhysLab Watchdog...
echo PhysLab will auto-restart if it crashes.
echo.
python aetherlab_watchdog.py
echo [%date% %time%] Watchdog exited.
