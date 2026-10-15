@echo off
title INRS live timing
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version >nul 2>nul || (echo Python is not installed. Install it from https://www.python.org/downloads/ then run this again. & pause & exit /b)
%PY% -c "import irsdk" 2>nul || (echo Installing pyirsdk... & %PY% -m pip install --user pyirsdk)
%PY% inrs_live.py
pause
