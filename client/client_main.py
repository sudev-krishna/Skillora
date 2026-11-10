"""
Skillora Desktop Client Entry Point (client/client_main.py)
Orchestrates CLI parsing, socket client startup, GUI initialization, and clean shutdown.
Strictly Modern Light Theme (Slate background, white cards, blue/indigo accents).
"""

import argparse
import logging
from pathlib import Path
import signal
import sys
from typing import Optional

# Prepend project root to sys.path for direct invocation without -m
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import customtkinter as ctk

from client.gui.app_window import AppWindow
from client.gui.theme import enforce_light_theme
from client.gui.views import (
    CodingSandboxView,
    CompanyView,
    DashboardView,
    InterviewView,
    MathStudioView,
)
from client.network.socket_client import SocketClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("skillora.client_main")


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for the Skillora desktop client."""
    parser = argparse.ArgumentParser(
        description="Skillora — Campus Placement Preparation & Evaluation System Desktop Client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server TCP host address")
    parser.add_argument("--port", type=int, default=9999, help="Server TCP port")
    parser.add_argument("--offline", action="store_true", help="Launch in offline mode without attempting TCP connection")
    parser.add_argument("--mock", action="store_true", help="Simulate server responses locally for testing and review")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


def main() -> int:
    """Main client bootstrap function."""
    args = parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Initializing Skillora Desktop Client (Modern Light Theme)...")
    enforce_light_theme()

    # 1. Initialize Network Layer
    socket_client: Optional[SocketClient] = None
    if not args.offline:
        socket_client = SocketClient(
            host=args.host,
            port=args.port,
            auto_reconnect=True,
            reconnect_interval=2.0,
        )
        try:
            socket_client.start()
            logger.info("Socket client started in background (target: %s:%d)", args.host, args.port)
        except Exception as ex:
            logger.warning("Could not start socket client: %s; falling back to offline mode", ex)

    # 2. Initialize GUI Shell
    root = ctk.CTk()
    app = AppWindow(
        root=root,
        socket_client=socket_client,
        mock_mode=args.mock,
        offline_mode=args.offline,
    )

    # 3. Register All 5 Core Views
    app.register_view("dashboard", DashboardView)
    app.register_view("company", CompanyView)
    app.register_view("math_studio", MathStudioView)
    app.register_view("coding_sandbox", CodingSandboxView)
    app.register_view("interview", InterviewView)

    # Default to dashboard view
    app.navigate_to("dashboard")

    # 4. Clean Shutdown Lifecycle Handler
    def on_closing() -> None:
        logger.info("Shutting down Skillora client cleanly...")
        try:
            if socket_client is not None:
                socket_client.stop(timeout=1.0)
        except Exception as ex:
            logger.warning("Error stopping socket client: %s", ex)
        finally:
            try:
                root.destroy()
            except Exception:
                pass
        sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Handle OS SIGINT / Ctrl+C
    def sigint_handler(sig, frame):
        on_closing()

    try:
        signal.signal(signal.SIGINT, sigint_handler)
    except Exception:
        pass

    # 5. Start Tkinter Main Event Loop
    logger.info("Entering main GUI loop.")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        on_closing()
    return 0


if __name__ == "__main__":
    sys.exit(main())
