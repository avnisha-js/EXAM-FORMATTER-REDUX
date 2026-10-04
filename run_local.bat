@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
set PYTHONPATH=%CD%
.venv\Scripts\python.exe -m flask --app app.web:create_app run --host 127.0.0.1 --port 5000
