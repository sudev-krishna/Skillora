@echo off
title Skillora - Automated Test Suite Runner
color 0E
echo ======================================================================
echo             SKILLORA - AUTOMATED TEST RUNNER (383 TESTS)
echo ======================================================================
echo.

cd /d "%~dp0"

echo Running all 383 automated unit, integration, and stress tests...
echo.
python tests\run_all_tests.py

echo.
echo Test execution complete.
pause
