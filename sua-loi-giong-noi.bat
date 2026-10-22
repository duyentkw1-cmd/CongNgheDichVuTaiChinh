@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua co moi truong Python. Hay cai demo truoc.
  pause
  exit /b 1
)
echo Can Internet de cai dung phien ban setuptools cho CTranslate2 tren Windows.
echo Hay dung cua so start-demo cu bang Ctrl+C truoc khi thu lai ung dung.
.venv\Scripts\python.exe -m pip install "setuptools==80.9.0"
if errorlevel 1 goto error
.venv\Scripts\python.exe scripts\doctor.py --speech
if errorlevel 1 goto error
echo.
echo Kiem tra thanh cong. Mo lai start-demo.bat va thu ghi am.
pause
exit /b 0
:error
echo.
echo Chua sua xong. Chup phan Traceback hoac ERROR ben tren de kiem tra tiep.
pause
exit /b 1
