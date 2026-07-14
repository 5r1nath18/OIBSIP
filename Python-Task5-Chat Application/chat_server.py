"""

Run:
    python chat_server.py [--host 0.0.0.0] [--port 5555]
"""

import argparse
import socket
import threading
import sys

from db import ChatDatabase
from protocol import send_msg, recv_msg, ConnectionClosed
import crypto_utils


class ClientHandler(threading.Thread):
    """One thread per connected client."""

    def __init__(self, conn: socket.socket, addr, server: "ChatServer"):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.server = server
        self.username = None
        self.room = None
        self.alive = True

    def run(self):
        try:
            while self.alive:
                try:
                    msg = recv_msg(self.conn)
                except ConnectionClosed:
                    break
                except (ValueError, OSError) as exc:
                    self._send_error(f"Malformed message: {exc}")
                    continue

                self._dispatch(msg)
        finally:
            self._cleanup()

    # ---- Dispatch ------------------------------------------------------- #

    def _dispatch(self, msg: dict):
        action = msg.get("action")
        handler = {
            "register": self._handle_register,
            "login": self._handle_login,
            "list_rooms": self._handle_list_rooms,
            "create_room": self._handle_create_room,
            "join_room": self._handle_join_room,
            "send_message": self._handle_send_message,
            "get_history": self._handle_get_history,
            "logout": self._handle_logout,
        }.get(action)

        if handler is None:
            self._send_error(f"Unknown action: {action}")
            return

        try:
            handler(msg)
        except (ValueError, RuntimeError) as exc:
            self._send_error(str(exc))

    # ---- Handlers ------------------------------------------------------- #

    def _handle_register(self, msg):
        username = (msg.get("username") or "").strip()
        password = msg.get("password") or ""
        if not username or not password:
            self._send_error("Username and password are required.")
            return
        if len(password) < 4:
            self._send_error("Password must be at least 4 characters.")
            return

        pw_hash, salt = crypto_utils.hash_password(password)
        self.server.db.create_user(username, pw_hash, salt)
        send_msg(self.conn, {"type": "auth_result", "status": "ok",
                              "message": "Registration successful. Please log in."})

    def _handle_login(self, msg):
        username = (msg.get("username") or "").strip()
        password = msg.get("password") or ""

        row = self.server.db.get_user(username)
        if row is None:
            self._send_error("Invalid username or password.")
            return

        _, _, pw_hash, salt = row
        if not crypto_utils.verify_password(password, pw_hash, salt):
            self._send_error("Invalid username or password.")
            return

        if self.server.is_online(username):
            self._send_error("This user is already logged in elsewhere.")
            return

        self.username = username
        self.server.register_connection(username, self)
        send_msg(self.conn, {"type": "auth_result", "status": "ok",
                              "message": f"Welcome, {username}!", "username": username})

    def _handle_list_rooms(self, _msg):
        rooms = self.server.db.list_rooms()
        send_msg(self.conn, {"type": "room_list", "rooms": rooms})

    def _handle_create_room(self, msg):
        self._require_auth()
        name = (msg.get("room") or "").strip()
        self.server.db.create_room(name)
        rooms = self.server.db.list_rooms()
        # Notify everyone so their room lists stay fresh
        self.server.broadcast_all({"type": "room_list", "rooms": rooms})

    def _handle_join_room(self, msg):
        self._require_auth()
        room = (msg.get("room") or "").strip()
        if self.server.db.get_room_id(room) is None:
            self._send_error(f"Room '{room}' does not exist.")
            return

        old_room = self.room
        self.room = room
        existing_members = self.server.join_room(self.username, room, old_room)

        send_msg(self.conn, {"type": "room_joined", "room": room})
        self.server.broadcast_to_members(
            existing_members,
            {"type": "notice", "room": room, "message": f"{self.username} joined the room."},
        )

    def _handle_send_message(self, msg):
        self._require_auth()
        room = msg.get("room")
        msg_type = msg.get("type", "text")
        content = msg.get("content")
        filename = msg.get("filename")

        if room != self.room:
            self._send_error("You must join the room before sending messages to it.")
            return
        if not content:
            self._send_error("Empty message content.")
            return
        if msg_type not in ("text", "image", "file"):
            self._send_error(f"Unsupported message type: {msg_type}")
            return

        timestamp = self.server.db.add_message(room, self.username, msg_type, content, filename)

        payload = {
            "type": "chat_message",
            "room": room,
            "sender": self.username,
            "msg_type": msg_type,
            "content": content,
            "filename": filename,
            "timestamp": timestamp,
        }
        self.server.broadcast_to_room(room, payload)

    def _handle_get_history(self, msg):
        self._require_auth()
        room = msg.get("room")
        limit = int(msg.get("limit", 50))
        rows = self.server.db.get_history(room, limit)
        history = [
            {"sender": r[0], "msg_type": r[1], "content": r[2], "filename": r[3], "timestamp": r[4]}
            for r in rows
        ]
        send_msg(self.conn, {"type": "history", "room": room, "messages": history})

    def _handle_logout(self, _msg):
        self.alive = False

    # ---- Helpers ------------------------------------------------------- #

    def _require_auth(self):
        if not self.username:
            raise ValueError("You must log in first.")

    def _send_error(self, message: str):
        try:
            send_msg(self.conn, {"type": "error", "message": message})
        except OSError:
            pass

    def _cleanup(self):
        if self.username:
            self.server.unregister_connection(self.username, self.room)
            if self.room:
                self.server.broadcast_to_room(
                    self.room,
                    {"type": "notice", "room": self.room, "message": f"{self.username} left the room."},
                    exclude=self.username,
                )
        try:
            self.conn.close()
        except OSError:
            pass


class ChatServer:
    def __init__(self, host="0.0.0.0", port=5555):
        self.host = host
        self.port = port
        self.db = ChatDatabase()
        self.lock = threading.Lock()
        # username -> ClientHandler
        self.connections: dict[str, ClientHandler] = {}
        # room -> set of usernames currently in that room
        self.room_members: dict[str, set] = {}
        self._sock = None

    def is_online(self, username: str) -> bool:
        with self.lock:
            return username in self.connections

    def register_connection(self, username: str, handler: ClientHandler):
        with self.lock:
            self.connections[username] = handler

    def unregister_connection(self, username: str, room: str):
        with self.lock:
            self.connections.pop(username, None)
            if room and room in self.room_members:
                self.room_members[room].discard(username)

    def join_room(self, username: str, room: str, old_room: str = None):
        """Add `username` to `room`'s membership. Returns the set of members
        that were already in the room *before* this join (a snapshot), so
        callers can broadcast a 'joined' notice without racing a
        concurrently-joining user into seeing a notice about themselves."""
        with self.lock:
            if old_room and old_room in self.room_members:
                self.room_members[old_room].discard(username)
            existing = set(self.room_members.get(room, set()))
            self.room_members.setdefault(room, set()).add(username)
            return existing

    def broadcast_to_room(self, room: str, payload: dict, exclude: str = None):
        with self.lock:
            members = list(self.room_members.get(room, set()))
        for uname in members:
            if uname == exclude:
                continue
            handler = self.connections.get(uname)
            if handler:
                try:
                    send_msg(handler.conn, payload)
                except OSError:
                    pass

    def broadcast_to_members(self, usernames, payload: dict):
        """Send `payload` to an explicit, already-decided set of usernames
        (used when the caller needs a fixed snapshot rather than the live
        room membership, to avoid notification races)."""
        with self.lock:
            handlers = [self.connections[u] for u in usernames if u in self.connections]
        for handler in handlers:
            try:
                send_msg(handler.conn, payload)
            except OSError:
                pass

    def broadcast_all(self, payload: dict):
        with self.lock:
            handlers = list(self.connections.values())
        for handler in handlers:
            try:
                send_msg(handler.conn, payload)
            except OSError:
                pass

    def serve_forever(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(20)
        print(f"[chat_server] Listening on {self.host}:{self.port}")

        try:
            while True:
                conn, addr = self._sock.accept()
                handler = ClientHandler(conn, addr, self)
                handler.start()
        except KeyboardInterrupt:
            print("\n[chat_server] Shutting down.")
        finally:
            self._sock.close()

    def stop(self):
        if self._sock:
            self._sock.close()


def main():
    parser = argparse.ArgumentParser(description="Chat server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    server = ChatServer(args.host, args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
