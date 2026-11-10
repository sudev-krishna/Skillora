"""
Skillora Server Action Dispatcher (server/network/dispatcher.py)
Routes incoming client requests to registered action handlers with standardized envelopes.
Strictly zero third-party web frameworks (standard library only).
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("skillora.dispatcher")


class ActionDispatcher:
    """Thread-safe registry and dispatcher for network actions."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._lock = threading.Lock()
        # Register default actions
        self.register("PING", self._handle_ping)

    def register(self, action: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """Register an action handler."""
        if not action or not isinstance(action, str):
            raise ValueError("Action name must be a non-empty string")
        if not callable(handler):
            raise TypeError("Handler must be callable")
        with self._lock:
            self._handlers[action] = handler
            logger.debug(f"Registered route: {action}")

    def route(self, action: str) -> Callable[[Callable[[Dict[str, Any]], Any]], Callable[[Dict[str, Any]], Any]]:
        """Decorator for registering route handlers."""
        def decorator(handler: Callable[[Dict[str, Any]], Any]) -> Callable[[Dict[str, Any]], Any]:
            self.register(action, handler)
            return handler
        return decorator

    def unregister(self, action: str) -> bool:
        """Unregister an action handler. Returns True if removed."""
        with self._lock:
            return self._handlers.pop(action, None) is not None

    def has_action(self, action: str) -> bool:
        """Check if an action handler is registered."""
        with self._lock:
            return action in self._handlers

    def registered_actions(self) -> List[str]:
        """Return list of all registered action names."""
        with self._lock:
            return list(self._handlers.keys())

    def _handle_ping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Built-in PING health check handler."""
        return {
            "echo_timestamp": payload.get("timestamp"),
            "server_time": time.time(),
        }

    def dispatch(self, request: Any) -> Dict[str, Any]:
        """
        Dispatch an incoming request envelope to the appropriate handler.
        Guarantees response envelope:
            {"action": str, "request_id": str, "status": "SUCCESS" | "ERROR", "payload": dict | None, "error": str | None}
        """
        # 1. Validate envelope type
        if not isinstance(request, dict):
            return {
                "action": "UNKNOWN",
                "request_id": "",
                "status": "ERROR",
                "payload": None,
                "error": "Invalid request envelope: expected a JSON object",
            }

        # 2. Extract correlation ID and action
        request_id = str(request.get("request_id", ""))
        action = request.get("action")

        # 3. Validate action string
        if not action or not isinstance(action, str):
            return {
                "action": str(action) if action else "",
                "request_id": request_id,
                "status": "ERROR",
                "payload": None,
                "error": "Missing or invalid 'action' field in request",
            }

        # 4. Extract and validate payload
        payload = request.get("payload")
        if payload is None:
            payload = {}
        elif not isinstance(payload, dict):
            return {
                "action": action,
                "request_id": request_id,
                "status": "ERROR",
                "payload": None,
                "error": "Invalid payload format: expected a dictionary",
            }

        # 5. Route lookup
        with self._lock:
            handler = self._handlers.get(action)

        if handler is None:
            return {
                "action": action,
                "request_id": request_id,
                "status": "ERROR",
                "payload": None,
                "error": f"Action '{action}' is not registered",
            }

        # 6. Handler execution within exception boundary
        try:
            result = handler(payload)
        except Exception as exc:
            logger.exception(f"Unhandled exception executing action '{action}': {exc}")
            return {
                "action": action,
                "request_id": request_id,
                "status": "ERROR",
                "payload": None,
                "error": str(exc),
            }

        # 7. Check if handler explicitly returned an error envelope
        if isinstance(result, dict) and result.get("status") == "ERROR":
            return {
                "action": action,
                "request_id": request_id,
                "status": "ERROR",
                "payload": result.get("payload"),
                "error": str(result.get("error", "Unknown handler error")),
            }

        # 8. Standard SUCCESS envelope
        return {
            "action": action,
            "request_id": request_id,
            "status": "SUCCESS",
            "payload": result if isinstance(result, dict) else {"result": result},
            "error": None,
        }
