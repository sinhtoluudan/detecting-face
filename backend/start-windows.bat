@echo off
setlocal
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
goto end
:fail
echo Failed. Install Python 3.11 and check the error above.
:end
pause
