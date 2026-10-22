@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chay setup-local.bat truoc.
  pause
  exit /b 1
)
echo Huan luyen tu datasets\train.csv, chon tham so bang validation.csv, danh gia bang test.csv.
echo Khong tu tao lai hay ghi de du lieu CSV cua ban.
.venv\Scripts\python.exe -m ml.train
if errorlevel 1 goto error
echo Da luu model va bao cao trong models\finance. Khoi dong lai app de nap model moi.
pause
exit /b 0
:error
echo Huan luyen khong thanh cong. Kiem tra cac cot, nhan va group_id cua du lieu.
pause
exit /b 1
