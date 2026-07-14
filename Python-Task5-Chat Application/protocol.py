
import json
import socket
import struct

HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 25 * 1024 * 1024  # 25 MB safety cap (covers small media files)


class ConnectionClosed(Exception):
    """Raised when the peer closes the connection mid-read."""
    pass


def send_msg(sock: socket.socket, obj: dict) -> None:
    """Serialize `obj` to JSON and send it length-prefixed."""
    payload = json.dumps(obj).encode("utf-8")
    if len(payload) > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message too large: {len(payload)} bytes (max {MAX_MESSAGE_SIZE})")
    header = struct.pack(">I", len(payload))
    sock.sendall(header + payload)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from the socket, or raise ConnectionClosed."""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionClosed("Socket closed while reading data.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_msg(sock: socket.socket) -> dict:
    """Read one length-prefixed JSON message from the socket."""
    header = _recv_exact(sock, HEADER_SIZE)
    (length,) = struct.unpack(">I", header)
    if length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Incoming message too large: {length} bytes")
    payload = _recv_exact(sock, length)
    return json.loads(payload.decode("utf-8"))
