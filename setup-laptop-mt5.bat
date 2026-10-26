@echo off
cd /d "%~dp0"
echo Setting up RobustForexEA on this PC's MetaTrader 5 data folders.
echo This does not close MetaTrader. Restart MT5 yourself after it finishes.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-laptop-mt5.ps1"
echo.
pause
