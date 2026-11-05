@echo off
cd /d "%~dp0"
echo Creating Python 3.11 virtual environment...
py -3.11 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Installation complete. Open run_windows.bat to start.
pause
exit /b 0
:fail
echo Installation failed. Install Python 3.11 64-bit with Python Launcher.
echo Check the error above and your internet connection. See README.md.
pause
exit /b 1
