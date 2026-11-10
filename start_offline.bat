@echo off
title Skillora — Standalone Offline Placement Preparation Coach
color 0A

echo ======================================================================
echo     SKILLORA — STANDALONE OFFLINE INTERVIEW PREPARATION COACH
echo     Linear/Vercel Command Shell • LeetCode 3.0 Split-Pane Studio
echo     Funnel: Round 1 (Aptitude) ^| Round 2 (Coding Lab) ^| Round 3 (Interview)
echo ======================================================================
echo.

cd /d "%~dp0"

:: Verify Python Environment
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python was not found in your system PATH.
    pause
    exit /b 1
)

echo Launching Skillora in 100%% Standalone Offline Mode (Zero Sockets)...
python run_client.py --offline %*

echo.
echo Skillora GUI session ended.
pause
