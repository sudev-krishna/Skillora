#!/usr/bin/env python3
"""
Convenience Launcher for Skillora Server
Runs the multi-client TCP socket server on port 9999.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from server.server_main import main

if __name__ == "__main__":
    main()
