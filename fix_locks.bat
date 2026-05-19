@echo off
REM Remove stale git lock files left over from interrupted git operations.
setlocal
cd /d "%~dp0"
echo Removing stale git lock files...
del /f /q ".git\index.lock" 2>nul
del /f /q ".git\HEAD.lock" 2>nul
del /f /q ".git\refs\heads\main.lock" 2>nul
del /f /q ".git\refs\remotes\origin\main.lock" 2>nul
del /f /q "%USERPROFILE%\Downloads\cscs-deploy-token.txt" 2>nul
echo Done.
pause
