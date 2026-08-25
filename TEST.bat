@echo off
setlocal
cd /d "%~dp0"
echo [1/4] Installing Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo [2/4] Pulling FotMob + RotoWire data...
python scripts\update.py
if errorlevel 1 goto fail
echo [3/4] Data generated successfully.
echo [4/4] Starting local FootballEdge...
start "FootballEdge" cmd /c "python -m http.server 8765"
timeout /t 2 >nul
start "" http://127.0.0.1:8765/
echo.
echo Site: http://127.0.0.1:8765/
pause
exit /b 0
:fail
echo.
echo TEST FAILED. Read the error above.
pause
exit /b 1
