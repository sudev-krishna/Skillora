#!/usr/bin/env python3
"""
Category-Partition and Boundary Value Analysis (BVA) test suite for the
Skillora R2 wire framing and JSON protocol specification (common/protocol.py).

Features Covered:
- F1: 4-byte big-endian framing ('!I'), 16MB frame guard, chunked TCP accumulation.
- F2: JSON request/response envelope schemas, correlation IDs, malformed recovery.

Test Tiers:
- Tier 1: Functional Happy Path (roundtrip, unicode, nested structures, envelopes)
- Tier 2: Boundary Value Analysis (16MB threshold, 0-byte, sub-minimum, partial chunks)
- Tier 3: Error Recovery & Security (malformed JSON, invalid UTF-8, oversized headers)
- Tier 4: Socket Loopback & Network Fragmentation (mock chunked sockets, loopback pair)
"""

import json
import socket
import struct
import sys
import threading
import unittest
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Attempt import of common.protocol
try:
    import common.protocol as proto
    PROTOCOL_AVAILABLE = True
except ImportError:
    proto = None
    PROTOCOL_AVAILABLE = False


class MockChunkedSocket:
    """
    Deterministic mock socket simulating fragmented TCP stream arrivals
    and unexpected connection drops.
    """

    def __init__(self, chunks: List[bytes], drop_after_bytes: int = -1):
        self._chunks = list(chunks)
        self._total_read = 0
        self._drop_after_bytes = drop_after_bytes
        self.closed = False

    def recv(self, bufsize: int) -> bytes:
        if self.closed or not self._chunks:
            return b""

        chunk = self._chunks.pop(0)
        if len(chunk) > bufsize:
            # Re-queue excess
            self._chunks.insert(0, chunk[bufsize:])
            chunk = chunk[:bufsize]

        if self._drop_after_bytes >= 0:
            bytes_left = self._drop_after_bytes - self._total_read
            if bytes_left <= 0:
                self.closed = True
                self._chunks.clear()
                return b""
            if len(chunk) > bytes_left:
                chunk = chunk[:bytes_left]
                self.closed = True
                self._chunks.clear()

        self._total_read += len(chunk)
        return chunk

    def sendall(self, data: bytes) -> None:
        pass

    def close(self) -> None:
        self.closed = True


# ===========================================================================
# Category 1: Valid Packet Roundtrips (Happy Path & Data Integrity)
# ===========================================================================

@unittest.skipUnless(PROTOCOL_AVAILABLE, "common.protocol is not yet implemented")
class TestWireFramingRoundtrip(unittest.TestCase):
    """Verifies complete encode/decode roundtrips across various data types."""

    def test_roundtrip_basic_dictionary(self):
        """Encodes and decodes flat dictionary with string, int, float, bool, null."""
        data = {
            "action": "AUTH_LOGIN",
            "request_id": "req-001",
            "count": 42,
            "score": 98.75,
            "active": True,
            "notes": None,
        }
        encoded = proto.encode_packet(data)
        decoded, remainder = proto.decode_packet(encoded)
        self.assertEqual(decoded, data)
        self.assertEqual(remainder, b"")

    def test_roundtrip_nested_data_structures(self):
        """Encodes and decodes complex nested dictionaries and arrays."""
        data = {
            "action": "SOLVE_RECURRENCE",
            "request_id": "req-002",
            "payload": {
                "equation": "T(n) = 2*T(n/2) + n",
                "base_cases": {"1": 1},
                "proof_steps": [
                    {"step": 1, "desc": "Identify a=2, b=2, f(n)=n"},
                    {"step": 2, "desc": "Compare f(n) with n^(log_b a)"},
                    {"step": 3, "desc": "Master Theorem Case 2 applies"},
                ],
                "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            },
        }
        encoded = proto.encode_packet(data)
        decoded, remainder = proto.decode_packet(encoded)
        self.assertEqual(decoded, data)
        self.assertEqual(remainder, b"")

    def test_roundtrip_unicode_devanagari_and_math_symbols(self):
        """Verifies full fidelity for Hindi/Devanagari text and mathematical glyphs."""
        data = {
            "candidate_name": "राहुल शर्मा",
            "college": "आईआईटी दिल्ली",
            "branch": "कंप्यूटर विज्ञान",
            "asymptotic_complexity": "O(N log N)",
            "symbols": "Θ(g(n)) ≤ c₁·g(n) ∧ Ω(h(n)) ≥ c₂·h(n) ∧ ∑(i=1..n) i = n(n+1)/2",
            "special_chars": 'Quotes: "hello", Newlines: \n\t\r, Escapes: \\ / \b \f',
        }
        encoded = proto.encode_packet(data)
        decoded, remainder = proto.decode_packet(encoded)
        self.assertEqual(decoded, data)
        self.assertEqual(decoded["candidate_name"], "राहुल शर्मा")
        self.assertIn("Θ(g(n))", decoded["symbols"])
        self.assertEqual(remainder, b"")

    def test_roundtrip_minimal_empty_dictionary(self):
        """Minimal valid JSON payload '{}' (2 bytes) roundtrips correctly."""
        data = {}
        encoded = proto.encode_packet(data)
        # Header is 4 bytes, payload '{}' is 2 bytes -> 6 bytes total
        self.assertEqual(len(encoded), 6)
        decoded, remainder = proto.decode_packet(encoded)
        self.assertEqual(decoded, {})
        self.assertEqual(remainder, b"")

    def test_roundtrip_compact_serialization(self):
        """Verifies wire encoding uses compact separators without extraneous whitespace."""
        data = {"a": 1, "b": 2}
        encoded = proto.encode_packet(data)
        payload = encoded[proto.HEADER_SIZE:]
        # Compact format should be b'{"a":1,"b":2}' (13 bytes)
        self.assertEqual(payload, b'{"a":1,"b":2}')
        self.assertNotIn(b": ", payload)
        self.assertNotIn(b", ", payload)

    def test_roundtrip_large_payload(self):
        """Verifies roundtrip with a realistic large 500 KB payload."""
        large_list = [{"id": i, "val": f"token_value_{i}" * 5} for i in range(6000)]
        data = {"action": "BATCH_DATA", "items": large_list}
        encoded = proto.encode_packet(data)
        self.assertGreater(len(encoded), 500 * 1024)
        decoded, remainder = proto.decode_packet(encoded)
        self.assertEqual(len(decoded["items"]), 6000)
        self.assertEqual(decoded["items"][42]["id"], 42)
        self.assertEqual(remainder, b"")


# ===========================================================================
# Category 2: 4-Byte Big-Endian Framing Verification (Binary Protocol Rules)
# ===========================================================================

@unittest.skipUnless(PROTOCOL_AVAILABLE, "common.protocol is not yet implemented")
class TestBigEndianHeaderVerification(unittest.TestCase):
    """Verifies binary header endianness, format constants, and length accounting."""

    def test_header_constants(self):
        """Verifies protocol constants match architectural specification."""
        self.assertEqual(proto.HEADER_FORMAT, '!I')
        self.assertEqual(proto.HEADER_SIZE, 4)
        self.assertEqual(proto.MAX_PAYLOAD_SIZE, 16 * 1024 * 1024)

    def test_big_endian_byte_ordering(self):
        """Verifies most significant byte (MSB) is transmitted first."""
        # Test synthetic payload lengths
        test_cases = [
            (1, b"\x00\x00\x00\x01"),
            (2, b"\x00\x00\x00\x02"),
            (256, b"\x00\x00\x01\x00"),
            (65536, b"\x00\x01\x00\x00"),
            (16777216, b"\x01\x00\x00\x00"),
        ]
        for length, expected_header in test_cases:
            packed = struct.pack(proto.HEADER_FORMAT, length)
            self.assertEqual(packed, expected_header, f"Mismatch for length {length}")
            unpacked = struct.unpack(proto.HEADER_FORMAT, packed)[0]
            self.assertEqual(unpacked, length)

    def test_header_length_matches_payload_byte_count(self):
        """Header length value must strictly equal UTF-8 byte count, not string length."""
        # '₹' is 3 bytes in UTF-8: 0xE2 0x82 0xB9
        data = {"currency": "₹₹₹"}
        encoded = proto.encode_packet(data)
        header = encoded[:proto.HEADER_SIZE]
        payload = encoded[proto.HEADER_SIZE:]

        header_len = struct.unpack(proto.HEADER_FORMAT, header)[0]
        self.assertEqual(header_len, len(payload))
        # len(payload) is greater than len(json_str) due to multi-byte unicode
        json_str = payload.decode('utf-8')
        self.assertGreater(len(payload), len(json_str))

    def test_decode_packet_manual_unpack_symmetry(self):
        """Direct struct unpacking matches decode_packet framing calculation."""
        payload_bytes = b'{"status":"PING"}'
        header = struct.pack('!I', len(payload_bytes))
        stream = header + payload_bytes

        decoded, remainder = proto.decode_packet(stream)
        self.assertEqual(decoded, {"status": "PING"})
        self.assertEqual(remainder, b"")


# ===========================================================================
# Category 3: 16 MB Limit Protection & Boundary Value Analysis (BVA)
# ===========================================================================

@unittest.skipUnless(PROTOCOL_AVAILABLE, "common.protocol is not yet implemented")
class TestPayloadSizeBoundariesAndProtection(unittest.TestCase):
    """Verifies strict 16MB DoS threshold and minimum size boundaries."""

    def test_boundary_exact_16mb_limit_encode(self):
        """Verifies encoding at exact 16 MB limit boundary."""
        # Construct payload with exact serialized size of MAX_PAYLOAD_SIZE
        # '{"k":"' + ('A'*padding) + '"}'
        base_overhead = len(b'{"k":""}')
        padding_needed = proto.MAX_PAYLOAD_SIZE - base_overhead
        data = {"k": "A" * padding_needed}

        encoded = proto.encode_packet(data)
        header_len = struct.unpack(proto.HEADER_FORMAT, encoded[:4])[0]
        self.assertEqual(header_len, proto.MAX_PAYLOAD_SIZE)
        self.assertEqual(len(encoded), proto.MAX_PAYLOAD_SIZE + proto.HEADER_SIZE)

    def test_boundary_exceeded_16mb_limit_encode(self):
        """Payload exceeding 16 MB by 1 byte must raise an exception."""
        base_overhead = len(b'{"k":""}')
        padding_needed = (proto.MAX_PAYLOAD_SIZE - base_overhead) + 1
        data = {"k": "A" * padding_needed}

        expected_errors = (ValueError,)
        if hasattr(proto, "FrameSizeExceededError"):
            expected_errors = (proto.FrameSizeExceededError, ValueError)

        with self.assertRaises(expected_errors):
            proto.encode_packet(data)

    def test_boundary_exceeded_16mb_limit_decode_header(self):
        """Unpacking a header claiming > 16 MB raises error without allocating memory."""
        oversized_lengths = [
            proto.MAX_PAYLOAD_SIZE + 1,
            32 * 1024 * 1024,
            0xFFFFFFFF,  # 4 GB max uint32
        ]
        expected_errors = (ValueError,)
        if hasattr(proto, "FrameSizeExceededError"):
            expected_errors = (proto.FrameSizeExceededError, ValueError)

        for size in oversized_lengths:
            header = struct.pack(proto.HEADER_FORMAT, size)
            buffer = header + b'{"fake":"payload"}'
            with self.assertRaises(expected_errors):
                proto.decode_packet(buffer)

    def test_boundary_zero_payload_length_header(self):
        """Header claiming length 0 must raise ValueError."""
        header = struct.pack(proto.HEADER_FORMAT, 0)
        with self.assertRaises(ValueError):
            proto.decode_packet(header)

    def test_boundary_below_minimum_json_length_header(self):
        """Header claiming length 1 (too small for valid JSON '{}') raises ValueError."""
        header = struct.pack(proto.HEADER_FORMAT, 1)
        buffer = header + b"{"
        with self.assertRaises(ValueError):
            proto.decode_packet(buffer)


# ===========================================================================
# Category 4: Stream Chunking & TCP Fragmentation Accumulation
# ===========================================================================

@unittest.skipUnless(PROTOCOL_AVAILABLE, "common.protocol is not yet implemented")
class TestStreamChunkingAndAccumulation(unittest.TestCase):
    """Verifies packet recovery across fragmented TCP chunks and stream buffers."""

    def test_decode_empty_buffer(self):
        """Empty buffer returns (None, b'') without raising exception."""
        decoded, remainder = proto.decode_packet(b"")
        self.assertIsNone(decoded)
        self.assertEqual(remainder, b"")

    def test_decode_partial_header(self):
        """Buffers with 1, 2, or 3 bytes return (None, buffer) untouched."""
        full_header = struct.pack('!I', 10)
        for i in (1, 2, 3):
            partial = full_header[:i]
            decoded, remainder = proto.decode_packet(partial)
            self.assertIsNone(decoded)
            self.assertEqual(remainder, partial)

    def test_decode_complete_header_partial_payload(self):
        """Buffer with 4-byte header but only partial payload returns (None, buffer)."""
        data = {"action": "TEST", "payload": "abcdefghijk"}
        encoded = proto.encode_packet(data)
        # Cut buffer in half
        cutoff = len(encoded) // 2
        partial_buffer = encoded[:cutoff]

        decoded, remainder = proto.decode_packet(partial_buffer)
        self.assertIsNone(decoded)
        self.assertEqual(remainder, partial_buffer)

    def test_decode_exact_single_frame(self):
        """Buffer with exactly one full frame returns (data, b'')."""
        data = {"action": "PING"}
        encoded = proto.encode_packet(data)

        decoded, remainder = proto.decode_packet(encoded)
        self.assertEqual(decoded, data)
        self.assertEqual(remainder, b"")

    def test_decode_coalesced_multiple_frames(self):
        """Multiple packets arriving in a single coalesced buffer are decoded sequentially."""
        packets = [
            {"id": 1, "type": "FIRST"},
            {"id": 2, "type": "SECOND"},
            {"id": 3, "type": "THIRD"},
        ]
        combined_stream = b"".join(proto.encode_packet(p) for p in packets)

        recovered = []
        buf = combined_stream
        while True:
            pkt, buf = proto.decode_packet(buf)
            if pkt is None:
                break
            recovered.append(pkt)

        self.assertEqual(recovered, packets)
        self.assertEqual(buf, b"")

    def test_decode_frame_with_trailing_partial_frame(self):
        """Buffer with complete packet followed by incomplete next packet."""
        pkt1 = {"id": 1, "msg": "full"}
        pkt2 = {"id": 2, "msg": "fragmented"}
        encoded1 = proto.encode_packet(pkt1)
        encoded2 = proto.encode_packet(pkt2)

        # Buffer contains all of pkt1 and first 6 bytes of pkt2
        partial_stream = encoded1 + encoded2[:6]

        decoded, remainder = proto.decode_packet(partial_stream)
        self.assertEqual(decoded, pkt1)
        self.assertEqual(remainder, encoded2[:6])

        # Provide the rest of pkt2
        final_stream = remainder + encoded2[6:]
        decoded2, remainder2 = proto.decode_packet(final_stream)
        self.assertEqual(decoded2, pkt2)
        self.assertEqual(remainder2, b"")

    def test_read_exact_single_byte_fragmentation(self):
        """read_exact accumulates stream when socket delivers only 1 byte per recv()."""
        raw_data = b"Hello, Skillora Socket Protocol!"
        one_byte_chunks = [raw_data[i:i + 1] for i in range(len(raw_data))]
        mock_sock = MockChunkedSocket(one_byte_chunks)

        accumulated = proto.read_exact(mock_sock, len(raw_data))
        self.assertEqual(accumulated, raw_data)

    def test_read_exact_arbitrary_chunk_sizes(self):
        """read_exact accumulates stream across varying chunk sizes."""
        raw_data = b"Skillora Distributed Campus Placement Platform 2026"
        # Split into chunks of sizes 7, 13, 23, and rest
        chunks = [raw_data[:7], raw_data[7:20], raw_data[20:43], raw_data[43:]]
        mock_sock = MockChunkedSocket(chunks)

        accumulated = proto.read_exact(mock_sock, len(raw_data))
        self.assertEqual(accumulated, raw_data)

    def test_read_exact_clean_eof_at_boundary(self):
        """read_exact returns b'' if socket is closed cleanly before reading any bytes."""
        mock_sock = MockChunkedSocket([])
        result = proto.read_exact(mock_sock, 100)
        self.assertEqual(result, b"")

    def test_read_exact_premature_eof_mid_frame(self):
        """read_exact raises error if socket drops mid-packet."""
        mock_sock = MockChunkedSocket([b"12345"], drop_after_bytes=5)

        expected_errors = (ConnectionError,)
        if hasattr(proto, "IncompleteFrameError"):
            expected_errors = (proto.IncompleteFrameError, ConnectionError)

        with self.assertRaises(expected_errors):
            proto.read_exact(mock_sock, 10)

    def test_read_exact_zero_bytes_requested(self):
        """read_exact(sock, 0) returns b'' immediately."""
        mock_sock = MockChunkedSocket([b"should_not_be_read"])
        result = proto.read_exact(mock_sock, 0)
        self.assertEqual(result, b"")
        self.assertEqual(mock_sock._total_read, 0)

    def test_read_exact_negative_bytes_raises_value_error(self):
        """read_exact(sock, -1) raises ValueError."""
        mock_sock = MockChunkedSocket([])
        with self.assertRaises(ValueError):
            proto.read_exact(mock_sock, -5)


# ===========================================================================
# Category 5: Malformed JSON Recovery & Input Validation
# ===========================================================================

@unittest.skipUnless(PROTOCOL_AVAILABLE, "common.protocol is not yet implemented")
class TestMalformedPayloadsAndRecovery(unittest.TestCase):
    """Verifies protocol error handling when receiving corrupted or malformed payloads."""

    def test_malformed_json_syntax(self):
        """Malformed JSON string in payload raises protocol error."""
        corrupted_payload = b'{"action": "TEST", "broken": '
        header = struct.pack('!I', len(corrupted_payload))
        stream = header + corrupted_payload

        expected_errors = (ValueError,)
        if hasattr(proto, "MalformedJSONError"):
            expected_errors = (proto.MalformedJSONError, ValueError)

        with self.assertRaises(expected_errors):
            proto.decode_packet(stream)

    def test_malformed_json_root_not_dict(self):
        """JSON payloads where root is an array, int, or string raise error."""
        invalid_roots = [
            b'[1, 2, 3]',
            b'"a standalone string"',
            b'12345',
            b'true',
            b'null',
        ]
        expected_errors = (ValueError,)
        if hasattr(proto, "MalformedJSONError"):
            expected_errors = (proto.MalformedJSONError, ValueError)

        for payload in invalid_roots:
            header = struct.pack('!I', len(payload))
            stream = header + payload
            with self.assertRaises(expected_errors):
                proto.decode_packet(stream)

    def test_malformed_utf8_invalid_byte_sequence(self):
        """Payload containing invalid UTF-8 bytes raises protocol error."""
        # \xFF\xFE are invalid in UTF-8
        invalid_utf8 = b'{"key": "\xff\xfe"}'
        header = struct.pack('!I', len(invalid_utf8))
        stream = header + invalid_utf8

        expected_errors = (ValueError,)
        if hasattr(proto, "MalformedJSONError"):
            expected_errors = (proto.MalformedJSONError, ValueError)

        with self.assertRaises(expected_errors):
            proto.decode_packet(stream)

    def test_encode_packet_non_dict_input_rejected(self):
        """encode_packet must reject non-dictionary arguments with TypeError."""
        for invalid_input in [["list"], "string", 123, None, True]:
            with self.assertRaises(TypeError):
                proto.encode_packet(invalid_input)

    def test_encode_packet_unserializable_object_rejected(self):
        """encode_packet must reject dictionaries containing non-JSON serializable objects."""
        data = {"key": object(), "set": {1, 2, 3}}
        expected_errors = (TypeError, ValueError)
        if hasattr(proto, "MalformedJSONError"):
            expected_errors = (proto.MalformedJSONError, TypeError, ValueError)

        with self.assertRaises(expected_errors):
            proto.encode_packet(data)


# ===========================================================================
# Category 6: Standard Request/Response Envelopes (Schema Contracts)
# ===========================================================================

@unittest.skipUnless(PROTOCOL_AVAILABLE, "common.protocol is not yet implemented")
class TestRequestResponseEnvelopeContract(unittest.TestCase):
    """Verifies request/response schema creation and validation helpers."""

    def test_create_request_defaults(self):
        """create_request generates valid action, UUID4 request_id, and empty payload."""
        req = proto.create_request("PING")
        self.assertEqual(req["action"], "PING")
        self.assertIsInstance(req["request_id"], str)
        self.assertEqual(len(req["request_id"]), 32)  # UUID4 hex length
        self.assertEqual(req["payload"], {})

    def test_create_request_custom_values(self):
        """create_request preserves explicit request_id and payload dict."""
        payload = {"user_id": 10, "filter": "Tier 1"}
        req = proto.create_request("GET_COMPANIES", payload=payload, request_id="custom-req-123")
        self.assertEqual(req["action"], "GET_COMPANIES")
        self.assertEqual(req["request_id"], "custom-req-123")
        self.assertEqual(req["payload"], payload)

    def test_create_request_invalid_inputs(self):
        """create_request rejects empty action or invalid payload type."""
        with self.assertRaises(ValueError):
            proto.create_request("")
        with self.assertRaises(TypeError):
            proto.create_request("ACTION", payload="not_a_dict")

    def test_create_response_success(self):
        """create_response creates valid SUCCESS envelope with error=None."""
        payload = {"result": "success", "count": 5}
        resp = proto.create_response("AUTH_LOGIN", "req-01", status="SUCCESS", payload=payload)
        self.assertEqual(resp["action"], "AUTH_LOGIN")
        self.assertEqual(resp["request_id"], "req-01")
        self.assertEqual(resp["status"], "SUCCESS")
        self.assertEqual(resp["payload"], payload)
        self.assertIsNone(resp["error"])

    def test_create_response_error_string(self):
        """create_response converts error string to structured error dict."""
        resp = proto.create_response(
            "AUTH_LOGIN",
            "req-02",
            status="ERROR",
            error="Invalid username or password"
        )
        self.assertEqual(resp["status"], "ERROR")
        self.assertIsInstance(resp["error"], dict)
        self.assertIn("message", resp["error"])
        self.assertEqual(resp["error"]["message"], "Invalid username or password")

    def test_create_response_error_dict(self):
        """create_response preserves structured error dictionary."""
        error_dict = {"code": "AUTH_FAILED", "message": "Invalid password", "attempts_left": 2}
        resp = proto.create_response(
            "AUTH_LOGIN",
            "req-03",
            status="ERROR",
            error=error_dict
        )
        self.assertEqual(resp["error"], error_dict)

    def test_create_response_invalid_status(self):
        """create_response rejects status other than SUCCESS or ERROR."""
        with self.assertRaises(ValueError):
            proto.create_response("ACTION", "req-01", status="INVALID_STATUS")

    def test_validate_request_envelope(self):
        """validate_request_envelope checks schema compliance."""
        valid_req = {"action": "PING", "request_id": "req-01", "payload": {}}
        valid, reason = proto.validate_request_envelope(valid_req)
        self.assertTrue(valid)
        self.assertIsNone(reason)

        invalid_cases = [
            ("not_a_dict", "root is not a dictionary"),
            ({"request_id": "r1", "payload": {}}, "missing action"),
            ({"action": "", "request_id": "r1", "payload": {}}, "empty action"),
            ({"action": "PING", "payload": {}}, "missing request_id"),
            ({"action": "PING", "request_id": "r1", "payload": "not_dict"}, "payload not dict"),
        ]
        for bad_req, desc in invalid_cases:
            valid, reason = proto.validate_request_envelope(bad_req)
            self.assertFalse(valid, f"Expected invalid for: {desc}")
            self.assertIsNotNone(reason)

    def test_validate_response_envelope(self):
        """validate_response_envelope checks response schema compliance."""
        valid_succ = {
            "action": "PING",
            "request_id": "r1",
            "status": "SUCCESS",
            "payload": {"ack": True},
            "error": None,
        }
        valid, reason = proto.validate_response_envelope(valid_succ)
        self.assertTrue(valid)
        self.assertIsNone(reason)

        valid_err = {
            "action": "PING",
            "request_id": "r1",
            "status": "ERROR",
            "payload": None,
            "error": {"code": "ERR", "message": "Failed"},
        }
        valid, reason = proto.validate_response_envelope(valid_err)
        self.assertTrue(valid)
        self.assertIsNone(reason)


# ===========================================================================
# Category 7: Socket Loopback Round-Trip (Real OS Socket Pair)
# ===========================================================================

@unittest.skipUnless(PROTOCOL_AVAILABLE, "common.protocol is not yet implemented")
class TestSocketIoLoopback(unittest.TestCase):
    """Verifies send_packet and receive_packet over connected OS sockets."""

    def setUp(self):
        """Create connected socket pair using localhost loopback."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        self.client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_sock.connect(('127.0.0.1', port))
        self.server_sock, _ = listener.accept()
        listener.close()

    def tearDown(self):
        """Clean up socket pair."""
        try:
            self.client_sock.close()
        except Exception:
            pass
        try:
            self.server_sock.close()
        except Exception:
            pass

    def test_socket_send_and_receive_single_packet(self):
        """Sends a packet from client and receives it on server."""
        message = {"action": "PING", "request_id": "sock-01", "payload": {"val": 123}}
        proto.send_packet(self.client_sock, message)
        received = proto.receive_packet(self.server_sock)
        self.assertEqual(received, message)

    def test_socket_bidirectional_roundtrip(self):
        """Sends request from client to server, server replies with response."""
        req = proto.create_request("EVAL_CODE", {"code": "print(1)"}, request_id="req-99")
        proto.send_packet(self.client_sock, req)

        server_rx = proto.receive_packet(self.server_sock)
        self.assertEqual(server_rx, req)

        resp = proto.create_response(server_rx["action"], server_rx["request_id"], "SUCCESS", {"out": "1"})
        proto.send_packet(self.server_sock, resp)

        client_rx = proto.receive_packet(self.client_sock)
        self.assertEqual(client_rx, resp)

    def test_socket_receive_packet_clean_disconnect(self):
        """When client closes socket cleanly, server receive_packet returns None."""
        self.client_sock.close()
        result = proto.receive_packet(self.server_sock)
        self.assertIsNone(result)

    def test_socket_receive_packet_oversized_header_rejected(self):
        """Sending an oversized header claims length > 16 MB, rejected with error."""
        oversized_header = struct.pack('!I', proto.MAX_PAYLOAD_SIZE + 100)
        self.client_sock.sendall(oversized_header)

        expected_errors = (ValueError,)
        if hasattr(proto, "FrameSizeExceededError"):
            expected_errors = (proto.FrameSizeExceededError, ValueError)

        with self.assertRaises(expected_errors):
            proto.receive_packet(self.server_sock)


if __name__ == "__main__":
    unittest.main()
