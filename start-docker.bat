@echo off
setlocal
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
where docker >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop is required. Install and start it, then run this file again.
  pause
  exit /b 1
)
docker compose up -d --build
if errorlevel 1 (
  echo Startup failed. Check the error above. Run: docker compose logs api
  pause
  exit /b 1
)
echo.
echo Open http://localhost:3000
start http://localhost:3000
pause
