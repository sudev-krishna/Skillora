"""
Skillora Wire Protocol Module (common/protocol.py)
Provides binary 4-byte big-endian length-prefixed JSON framing, socket accumulation,
16MB payload protection, and structured envelope helpers.
Strictly offline, zero third-party dependencies (pure standard library).
"""

import json
import socket
import struct
import uuid
from typing import Any, Dict, Optional, Tuple, Union

# Protocol Wire Constants
HEADER_FORMAT: str = '!I'
HEADER_SIZE: int = 4
MAX_PAYLOAD_SIZE: int = 16 * 1024 * 1024  # 16 MB maximum payload threshold
MIN_PAYLOAD_SIZE: int = 2  # Minimum valid JSON object ("{}")


# Custom Protocol Exception Hierarchy
class ProtocolError(Exception):
    """Base class for all protocol-level violations."""
    pass


class FrameSizeExceededError(ProtocolError, ValueError):
    """Raised when a packet's payload length exceeds the 16MB threshold."""
    pass


class IncompleteFrameError(ProtocolError, ConnectionError):
    """Raised when a socket disconnects abruptly mid-frame."""
    pass


class MalformedJSONError(ProtocolError, ValueError):
    """Raised when a packet's payload cannot be parsed as valid JSON or is not a dict."""
    pass


class InvalidEnvelopeError(ProtocolError, ValueError):
    """Raised when an envelope does not conform to request or response schema."""
    pass


# ---------------------------------------------------------------------------
# Buffer-Level Pure Framing Functions (In-Memory / Non-Blocking Sockets)
# ---------------------------------------------------------------------------

def encode_packet(data: Dict[str, Any]) -> bytes:
    """
    Serializes a dictionary to a UTF-8 JSON string prefixed with a 4-byte
    big-endian unsigned integer length header.

    Args:
        data: Python dictionary representing request or response envelope.

    Returns:
        bytes: 4-byte header + UTF-8 JSON payload.

    Raises:
        TypeError: If data is not a dictionary.
        MalformedJSONError: If data cannot be serialized to JSON.
        FrameSizeExceededError: If serialized bytes exceed MAX_PAYLOAD_SIZE (16MB).
        ValueError: If serialized bytes are smaller than MIN_PAYLOAD_SIZE.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Packet data must be a dict, got {type(data).__name__}")

    try:
        json_bytes = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    except (TypeError, ValueError) as err:
        raise MalformedJSONError(f"Failed to serialize packet dictionary to JSON: {err}") from err

    payload_len = len(json_bytes)
    if payload_len > MAX_PAYLOAD_SIZE:
        raise FrameSizeExceededError(
            f"Payload size {payload_len} exceeds maximum allowed size of {MAX_PAYLOAD_SIZE} bytes"
        )
    if payload_len < MIN_PAYLOAD_SIZE:
        raise ValueError(
            f"Payload size {payload_len} is smaller than minimum JSON size {MIN_PAYLOAD_SIZE}"
        )

    header = struct.pack(HEADER_FORMAT, payload_len)
    return header + json_bytes


def decode_packet(buffer: bytes) -> Tuple[Optional[Dict[str, Any]], bytes]:
    """
    Attempts to decode a single packet from a stream buffer.
    If a complete packet is present, parses and returns (packet_dict, remaining_buffer).
    If the buffer has an incomplete packet or partial header, returns (None, buffer).

    Args:
        buffer: Accumulated raw stream bytes.

    Returns:
        tuple[dict | None, bytes]: (decoded_dict, remaining_unparsed_bytes).

    Raises:
        FrameSizeExceededError: If the 4-byte header indicates length > MAX_PAYLOAD_SIZE.
        ValueError: If header indicates length < MIN_PAYLOAD_SIZE.
        MalformedJSONError: If payload bytes cannot be decoded as UTF-8 or parsed as JSON dict.
    """
    if len(buffer) < HEADER_SIZE:
        return None, buffer

    payload_len = struct.unpack(HEADER_FORMAT, buffer[:HEADER_SIZE])[0]

    # Enforce security and validity boundaries immediately
    if payload_len > MAX_PAYLOAD_SIZE:
        raise FrameSizeExceededError(
            f"Frame size {payload_len} exceeds maximum allowed limit {MAX_PAYLOAD_SIZE}"
        )
    if payload_len < MIN_PAYLOAD_SIZE:
        raise ValueError(
            f"Frame size {payload_len} is smaller than minimum required JSON {MIN_PAYLOAD_SIZE}"
        )

    total_frame_len = HEADER_SIZE + payload_len
    if len(buffer) < total_frame_len:
        # Header is complete, but payload is still partially received
        return None, buffer

    # Extract exact payload slice and remaining buffer
    payload_bytes = buffer[HEADER_SIZE:total_frame_len]
    remaining_buffer = buffer[total_frame_len:]

    try:
        payload_str = payload_bytes.decode('utf-8')
        data = json.loads(payload_str)
    except UnicodeDecodeError as err:
        raise MalformedJSONError(f"Payload contains invalid UTF-8 bytes: {err}") from err
    except json.JSONDecodeError as err:
        raise MalformedJSONError(f"Payload contains malformed JSON syntax: {err}") from err

    if not isinstance(data, dict):
        raise MalformedJSONError(f"Decoded JSON root must be a dict, got {type(data).__name__}")

    return data, remaining_buffer


# ---------------------------------------------------------------------------
# Socket-Level I/O Functions (Blocking Worker Threads)
# ---------------------------------------------------------------------------

def read_exact(sock: socket.socket, n_bytes: int) -> bytes:
    """
    Reads exactly n_bytes from a connected TCP socket, accumulating fragmented chunks.

    Args:
        sock: Connected socket instance.
        n_bytes: Total number of bytes required.

    Returns:
        bytes: Exactly n_bytes of accumulated data, or b"" if socket closed cleanly at boundary.

    Raises:
        ValueError: If n_bytes < 0.
        IncompleteFrameError: If socket closes mid-stream before n_bytes are accumulated.
    """
    if n_bytes < 0:
        raise ValueError(f"n_bytes must be non-negative, got {n_bytes}")
    if n_bytes == 0:
        return b""

    buf = bytearray()
    while len(buf) < n_bytes:
        remaining = n_bytes - len(buf)
        chunk = sock.recv(min(remaining, 65536))
        if not chunk:
            if len(buf) == 0:
                # Clean EOF at message boundary
                return b""
            raise IncompleteFrameError(
                f"Socket closed prematurely: expected {n_bytes} bytes, received {len(buf)} bytes"
            )
        buf.extend(chunk)
    return bytes(buf)


def receive_packet(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """
    Receives and unpacks a single length-prefixed JSON packet from a TCP socket.

    Args:
        sock: Connected socket instance.

    Returns:
        dict: The parsed JSON packet, or None if the peer cleanly closed the connection.

    Raises:
        FrameSizeExceededError: If header claims size > 16 MB.
        ValueError: If header claims size < MIN_PAYLOAD_SIZE.
        IncompleteFrameError: If socket drops mid-header or mid-payload.
        MalformedJSONError: If payload fails UTF-8 or JSON decoding.
    """
    header_bytes = read_exact(sock, HEADER_SIZE)
    if not header_bytes:
        # Clean peer disconnection at frame boundary
        return None

    if len(header_bytes) < HEADER_SIZE:
        raise IncompleteFrameError("Unexpected EOF while reading packet header")

    payload_len = struct.unpack(HEADER_FORMAT, header_bytes)[0]
    if payload_len > MAX_PAYLOAD_SIZE:
        raise FrameSizeExceededError(
            f"Received payload length {payload_len} exceeds maximum allowed {MAX_PAYLOAD_SIZE} bytes"
        )
    if payload_len < MIN_PAYLOAD_SIZE:
        raise ValueError(f"Invalid payload length received: {payload_len}")

    payload_bytes = read_exact(sock, payload_len)
    if len(payload_bytes) < payload_len:
        raise IncompleteFrameError("Unexpected EOF while reading packet payload")

    try:
        data = json.loads(payload_bytes.decode('utf-8'))
    except UnicodeDecodeError as err:
        raise MalformedJSONError(f"Payload contains invalid UTF-8 bytes: {err}") from err
    except json.JSONDecodeError as err:
        raise MalformedJSONError(f"Payload contains malformed JSON syntax: {err}") from err

    if not isinstance(data, dict):
        raise MalformedJSONError(f"Expected JSON object (dict), got {type(data).__name__}")

    return data


def send_packet(sock: socket.socket, data: Dict[str, Any]) -> None:
    """
    Encodes and transmits a dictionary packet over a socket using sendall().

    Args:
        sock: Connected socket instance.
        data: Packet dictionary to encode and send.

    Raises:
        TypeError, FrameSizeExceededError, MalformedJSONError: If data is invalid.
        OSError, ConnectionError: If socket send fails.
    """
    packet_bytes = encode_packet(data)
    sock.sendall(packet_bytes)


# ---------------------------------------------------------------------------
# Envelope Constructors and Validators
# ---------------------------------------------------------------------------

def create_request(
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs a valid client request envelope.

    Args:
        action: Route identifier string (e.g., 'AUTH_LOGIN').
        payload: Optional parameters dictionary (defaults to empty dict).
        request_id: Optional correlation ID (defaults to new UUID4 hex).

    Returns:
        dict: Standardized request envelope.
    """
    if not action or not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")

    if request_id is None:
        request_id = uuid.uuid4().hex
    elif not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a non-empty string")

    if payload is None:
        payload = {}
    elif not isinstance(payload, dict):
        raise TypeError(f"payload must be a dict, got {type(payload).__name__}")

    return {
        "action": action,
        "request_id": request_id,
        "payload": payload,
    }


def create_response(
    action: str,
    request_id: str,
    status: str = "SUCCESS",
    payload: Optional[Dict[str, Any]] = None,
    error: Optional[Union[Dict[str, Any], str]] = None
) -> Dict[str, Any]:
    """
    Constructs a valid server response envelope.

    Args:
        action: Originating action string.
        request_id: Originating request_id string.
        status: Status flag, either 'SUCCESS' or 'ERROR'.
        payload: Result dictionary (default {} on SUCCESS, typically None on ERROR).
        error: Error object or error message string (required on ERROR, None on SUCCESS).

    Returns:
        dict: Standardized response envelope.
    """
    if not action or not isinstance(action, str) or not action.strip():
        raise ValueError("action must be a non-empty string")
    if not request_id or not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id must be a non-empty string")

    status_upper = status.upper()
    if status_upper not in ("SUCCESS", "ERROR"):
        raise ValueError(f"status must be 'SUCCESS' or 'ERROR', got '{status}'")

    if status_upper == "SUCCESS":
        norm_payload = payload if payload is not None else {}
        norm_error = None
    else:  # ERROR
        norm_payload = payload if payload is not None else None
        if isinstance(error, str):
            norm_error = {"code": "GENERAL_ERROR", "message": error}
        elif isinstance(error, dict):
            norm_error = error
        elif error is None:
            norm_error = {"code": "UNKNOWN_ERROR", "message": "An error occurred"}
        else:
            norm_error = {"code": "GENERAL_ERROR", "message": str(error)}

    return {
        "action": action,
        "request_id": request_id,
        "status": status_upper,
        "payload": norm_payload,
        "error": norm_error,
    }


def validate_request_envelope(packet: Any) -> Tuple[bool, Optional[str]]:
    """
    Validates that a dictionary meets the client request schema.

    Returns:
        (True, None) if valid, or (False, reason) if invalid.
    """
    if not isinstance(packet, dict):
        return False, "Packet root is not a dictionary"
    if "action" not in packet or not isinstance(packet["action"], str) or not packet["action"].strip():
        return False, "Missing or invalid 'action' key"
    if "request_id" not in packet or not isinstance(packet["request_id"], str) or not packet["request_id"].strip():
        return False, "Missing or invalid 'request_id' key"
    if "payload" not in packet or not isinstance(packet["payload"], dict):
        return False, "Missing or invalid 'payload' key (must be dict)"
    return True, None


def validate_response_envelope(packet: Any) -> Tuple[bool, Optional[str]]:
    """
    Validates that a dictionary meets the server response schema.

    Returns:
        (True, None) if valid, or (False, reason) if invalid.
    """
    if not isinstance(packet, dict):
        return False, "Packet root is not a dictionary"
    if "action" not in packet or not isinstance(packet["action"], str) or not packet["action"].strip():
        return False, "Missing or invalid 'action' key"
    if "request_id" not in packet or not isinstance(packet["request_id"], str) or not packet["request_id"].strip():
        return False, "Missing or invalid 'request_id' key"
    if "status" not in packet or packet["status"] not in ("SUCCESS", "ERROR"):
        return False, "Missing or invalid 'status' key (must be 'SUCCESS' or 'ERROR')"
    if packet["status"] == "SUCCESS":
        if packet.get("error") is not None:
            return False, "Successful response should have error=None"
    elif packet["status"] == "ERROR":
        if packet.get("error") is None:
            return False, "Error response must provide error object/string"
    return True, None
