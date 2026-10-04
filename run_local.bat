@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
set PYTHONPATH=%CD%
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:5000/"
.venv\Scripts\python.exe -m flask --app app.web:create_app run --host 127.0.0.1 --port 5000
