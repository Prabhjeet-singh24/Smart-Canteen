@echo off
REM One-click setup + start for Windows. Double-click or run from Command Prompt.
cd /d "%~dp0"
if not exist .env (
  copy .env.example .env >nul
  echo Created .env from .env.example  -  open it and change ADMIN_PASSWORD and SECRET_KEY!
)
if not exist venv (
  echo Creating virtual environment...
  py -m venv venv || python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install -r backend\requirements.txt
python run.py
pause
