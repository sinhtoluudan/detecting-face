@echo off
setlocal
cd /d "%~dp0"
if not exist .env.local copy .env.example .env.local >nul
call npm ci
if errorlevel 1 goto fail
call npm run dev
goto end
:fail
echo Failed. Install Node.js 22 LTS and check the error above.
:end
pause
