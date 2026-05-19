@echo off
REM One-click: pull latest, commit any local edits, push to GitHub.
REM Use this after Claude has made changes to push them to the live site.
setlocal
cd /d "%~dp0"

echo === Pulling latest from origin ===
git pull --rebase 2>&1
echo.

echo === Staging changes ===
git add -A
git status --short
echo.

REM Check if there is anything to commit
git diff --cached --quiet
if errorlevel 1 (
    echo === Committing ===
    git commit -m "Update %date% %time%"
    echo.
    echo === Pushing to GitHub ===
    git push
    echo.
    echo Done. GitHub Actions will redeploy in ~30 seconds.
    echo Live site: https://dsingson5.github.io/cscs-study/
) else (
    REM Nothing staged. Maybe there is already an unpushed commit waiting.
    git status -sb | findstr /C:"ahead" >nul
    if not errorlevel 1 (
        echo === Pushing existing commits ===
        git push
        echo Done.
    ) else (
        echo No changes to commit, nothing to push.
    )
)
echo.
pause
