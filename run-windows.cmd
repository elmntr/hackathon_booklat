@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run .\setup-windows.cmd once while online first.
  exit /b 1
)
set "HF_HUB_OFFLINE=1"
echo Open http://localhost:8000 in Chrome, Edge, or Brave. Press Ctrl+C here to stop.
".venv\Scripts\python.exe" -m uvicorn server.main:app --host 127.0.0.1 --port 8000
exit /b %errorlevel%
