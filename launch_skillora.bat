@echo off
title Skillora — Campus Placement Preparation ^& Interview System
color 0B

echo ======================================================================
echo     SKILLORA — WARM MINIMALIST STUDIO PLACEMENT OS
echo     ClientRidge-Inspired Warm Off-White (#FAF9F5) ^& Vibrant Coral (#FF6442)
echo     Hero KPI Stat Grid • Rounded Capsule Charts • Smooth Spline Curves
echo     Funnel: Round 1 (Aptitude) ^| Round 2 (Coding Lab) ^| Round 3 (Interview)
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Validate Python Environment and Core Dependencies
echo [1/3] Validating Python Runtime and Core Libraries...
where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python was not found in your system PATH.
    echo Please install Python 3.10+ and ensure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

python -c "import sys, customtkinter, sympy; print(f'      [+] Verified Python {sys.version.split()[0]} with CustomTkinter and SymPy.')"
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Required dependencies are missing.
    echo Please install requirements via: pip install -r requirements.txt
    pause
    exit /b 1
)

:: 2. Verify Database Cache and Local SQLite Fallback
echo [2/3] Verifying Database Storage ^& Placement Benchmarks...
if not exist "skillora_offline.db" (
    echo       [*] First-time setup: Initializing offline database seed records...
    python -c "from server.db.init_db import main; main()"
) else (
    echo       [+] Local database cache ready [skillora_offline.db].
)

:: 3. Intelligent Backend TCP Server Launch and Port Synchronization
echo [3/3] Synchronizing Distributed Network Bridge (Port 9999)...
python -c "import socket, sys; s = socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1', 9999)) == 0 else 1)"
if %errorlevel% equ 0 (
    echo       [+] Detected existing Skillora TCP Server on port 9999. Reusing active instance.
) else (
    echo       [*] Spawning Background TCP Socket Server on 127.0.0.1:9999...
    start "Skillora TCP Server" /d "%~dp0" cmd /k "title Skillora Backend Server & python run_server.py"
    python -m common.wait_for_server 9999 127.0.0.1
)

echo.
echo ======================================================================
echo Launching Skillora Desktop Client (Warm Minimalist Studio):
echo   • Top Command Bar: Candidate Profile Chip, Placement Season Milestone Chip
echo   • [🔍] Invisible-by-Default Zoom: Ctrl + Wheel / Ctrl + +/- (80%% - 180%%)
echo   • [1] Placement Readiness Hub: Hero 32pt KPI Counters ^& Stepped Funnel
echo   • [2] Target Companies ^& Cutoffs: 10 Drives, CTC Badges, Drawer Stages
echo   • [3] Round 1: Aptitude Studio: SymPy Solvers ^& Step-by-Step Proofs
echo   • [4] Round 2: Coding Sandbox: Spline Curves, Dark Tooltips, Scaling-Aware Auto-Wrap
echo   • [5] Round 3: Mock Interview: 3-Pillar Radar Scoring ^& AST Validation
echo ======================================================================
echo.

python run_client.py %*

echo.
echo ======================================================================
echo Skillora GUI session ended cleanly.
echo ======================================================================
pause
