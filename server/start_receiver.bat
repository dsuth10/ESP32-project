@echo off
title Hermes Voice Satellite Receiver
echo Starting Hermes Voice Satellite Receiver...

if exist "C:\Python312\python.exe" (
    "C:\Python312\python.exe" -u "%~dp0hermes_voice_receiver.py"
) else (
    python -u "%~dp0hermes_voice_receiver.py"
)

pause
