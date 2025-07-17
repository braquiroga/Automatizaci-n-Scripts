@echo off
cd /d "%~dp0"
powershell -NoExit -ExecutionPolicy Bypass -File ".\Consultas.ps1"
