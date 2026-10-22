@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 scripts\setup_local.py
) else (
  python scripts\setup_local.py
)
if errorlevel 1 goto error
echo.
echo Cai thu vien xong. Neu OCR bao MISSING, chay install-ocr-windows.bat.
echo Sau do chay start-demo.bat.
pause
exit /b 0
:error
echo Chua cai xong. Xem thong bao ben tren va HUONG-DAN-WINDOWS.md.
pause
exit /b 1
