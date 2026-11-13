@echo off
cd /d "%~dp0"
echo [worm shadow] запуск сервера...
python -m uvicorn server.main:app --reload --host 127.0.0.1 --port 8000
pause
