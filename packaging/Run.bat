@echo off
setlocal
cd /d "%~dp0"

"%~dp0MTGRandomCommander.exe" %*
set "RESULT=%errorlevel%"

echo.
pause
exit /b %RESULT%
