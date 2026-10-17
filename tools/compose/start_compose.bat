@echo off
title ESP32 and Windows Compose Companion
cd /d "%~dp0"

echo =======================================================
echo   Starting ESP32 Voice Compose and Dictate Companion
echo =======================================================

if exist "C:\Python313\python.exe" (
    "C:\Python313\python.exe" compose_gui.py
) else (
    python compose_gui.py
)

if errorlevel 1 (
    echo Companion failed. Review the error above.
    pause
)
exit /b 0
