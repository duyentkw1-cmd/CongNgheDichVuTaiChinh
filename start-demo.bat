@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\local-ready.txt" (
  call setup-local.bat
  if errorlevel 1 exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Thieu giao dien da build. Chay npm ci va npm run build trong frontend.
  pause
  exit /b 1
)
echo So Thu Chi AI Local - http://localhost:8000
echo Giu cua so nay mo khi dung app. Ctrl+C de dung.
echo Lan nhan giong noi dau tien can vai giay de nap model.
start "" powershell -NoProfile -Command "Start-Sleep -Seconds 4; Start-Process 'http://localhost:8000'"
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
