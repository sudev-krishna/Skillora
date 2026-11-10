#!/usr/bin/env python3
"""
Convenience Launcher for Skillora Desktop Client GUI
Runs the modern light-themed desktop application.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from client.client_main import main

if __name__ == "__main__":
    main()
