@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Cai Tesseract OCR cho Windows 64-bit. Khong can tai khoan hay khoa API.
echo Giu thu muc cai mac dinh: C:\Program Files\Tesseract-OCR
echo Bo tieng Viet va tieng Anh da co san trong thu muc models\tessdata.
if exist "installers\tesseract-setup.exe" (
  start /wait "" "installers\tesseract-setup.exe"
) else (
  start "" "https://github.com/UB-Mannheim/tesseract/wiki"
  echo Tai ban Windows 64-bit tu trang vua mo va cai dat.
)
echo Dong va mo lai app sau khi cai xong.
pause
