@echo off
setlocal
title ESP32 Companion Feature Preview
cd /d "%~dp0"
if not defined ESP32_COMPANION_DATA_DIR set "ESP32_COMPANION_DATA_DIR=%LOCALAPPDATA%\ESP32ClassroomCompanion-Feature"
rem Keep the production companion and handheld receiver undisturbed.
rem Opt in using Settings, then relaunch. The test receiver has a separate port.
rem The feature app defaults these off. Settings can enable them on relaunch.
if not defined ESP32_RECEIVER_PORT set "ESP32_RECEIVER_PORT=8788"
if not defined ESP32_DISCOVERY_UDP_PORT set "ESP32_DISCOVERY_UDP_PORT=8789"
call "%~dp0tools\compose\start_compose.bat"
endlocal
