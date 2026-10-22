@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Khong thay .venv. Dat tep nay trong thu muc demo da cai, cung cap voi start-demo.bat.
  pause
  exit /b 1
)
echo Kiem tra AI tren may. Vui long doi den khi co ket qua cuoi.
echo Phan OCR se doc chung tu mau. Khong su dung giao dich cua ban.
.venv\Scripts\python.exe -X utf8 scripts\doctor.py --speech --ocr
if errorlevel 1 goto failed
echo.
echo KIEM TRA THANH CONG. Mo lai start-demo.bat de thu giong noi va anh.
pause
exit /b 0
:failed
echo.
echo CO THANH PHAN CHUA CHAY DUOC. Chup phan FAILED va loi phia tren.
pause
exit /b 1
