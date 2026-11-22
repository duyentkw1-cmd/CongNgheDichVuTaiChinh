@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Khong thay .venv. Vui long kiem tra lai thu muc cai dat.
  pause
  exit /b 1
)
echo ======================================================================
echo CHẠY KIỂM THỬ TRỢ LÝ THU CHI GIỌNG NÓI CHO TIỂU THƯƠNG CHỢ
echo ======================================================================
echo.
.venv\Scripts\python.exe -X utf8 scripts\demo_market_voice.py --interactive
pause
