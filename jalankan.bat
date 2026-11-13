@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Menyiapkan lingkungan Python pertama kali...
    python -m venv .venv || goto :gagal
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :gagal
)
start "" http://localhost:5000
".venv\Scripts\python.exe" run.py
pause
exit /b 0

:gagal
echo Gagal menyiapkan aplikasi. Pastikan Python 3 sudah terpasang.
pause
exit /b 1
