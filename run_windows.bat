@echo off
setlocal
cd /d "%~dp0"
call start-docker.bat
exit /b %errorlevel%
