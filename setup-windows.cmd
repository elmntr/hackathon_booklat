@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo Install uv first: winget install --id astral-sh.uv -e
  echo Then reopen your terminal and run this script again.
  exit /b 1
)
if not "%~1"=="" if /i not "%~1"=="whisper" (
  echo Usage: setup-windows.cmd [whisper]
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  if exist ".venv" (
    echo This .venv is not a Windows environment. Use a fresh clone without .venv.
    exit /b 1
  )
  uv venv --python 3.12 .venv
  if errorlevel 1 exit /b 1
)
uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt -r requirements-vosk.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" scripts\download_vosk.py
if errorlevel 1 exit /b 1
if /i "%~1"=="whisper" (
  ".venv\Scripts\python.exe" scripts\download_model.py
  if errorlevel 1 exit /b 1
)
echo Setup complete. Run .\run-windows.cmd and select Vosk in Booklat.
exit /b 0
