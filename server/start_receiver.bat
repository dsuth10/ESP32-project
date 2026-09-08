@echo off
title Hermes Voice Satellite Receiver
cd /d "%~dp0"

echo =======================================================
echo   Starting Hermes Voice Satellite Receiver
echo =======================================================

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -u hermes_voice_receiver.py
) else if exist "C:\Python313\python.exe" (
    "C:\Python313\python.exe" -u hermes_voice_receiver.py
) else if exist "C:\Python312\python.exe" (
    "C:\Python312\python.exe" -u hermes_voice_receiver.py
) else (
    python -u hermes_voice_receiver.py
)

pause
