@echo off
title Hermes Voice Satellite Receiver
cd /d "%~dp0"

echo =======================================================
echo   Starting Hermes Voice Satellite Receiver
echo =======================================================

rem Phase 17 & 18: Tune Work Ollama and enforce privacy defaults
if "%RECEIVER_ENV%"=="" set RECEIVER_ENV=work
if "%OLLAMA_KEEP_ALIVE%"=="" set OLLAMA_KEEP_ALIVE=8h
if "%OLLAMA_NO_CLOUD%"=="" set OLLAMA_NO_CLOUD=1

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -u hermes_voice_receiver.py
) else if exist "C:\Python312\python.exe" (
    "C:\Python312\python.exe" -u hermes_voice_receiver.py
) else if exist "C:\Python313\python.exe" (
    "C:\Python313\python.exe" -u hermes_voice_receiver.py
) else (
    python -u hermes_voice_receiver.py
)

pause
