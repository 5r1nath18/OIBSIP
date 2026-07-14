

import os
import sqlite3
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_data.db")


class ChatDatabase:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    msg_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    filename TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (room_id) REFERENCES rooms(id)
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO rooms (name, created_at) VALUES ('general', ?)
            """, (datetime.now().isoformat(),))
            conn.commit()

    # ---- Users ---------------------------------------------------------- #

    def create_user(self, username: str, password_hash: str, salt: str):
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                    (username, password_hash, salt, datetime.now().isoformat()),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' is already taken.")
        except sqlite3.Error as exc:
            raise RuntimeError(f"Database error while creating user: {exc}")

    def get_user(self, username: str):
        """Return (id, username, password_hash, salt) or None."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id, username, password_hash, salt FROM users WHERE username = ?",
                    (username,),
                ).fetchone()
            return row
        except sqlite3.Error as exc:
            raise RuntimeError(f"Database error while fetching user: {exc}")

    # ---- Rooms ------------------------------------------------------------ #

    def create_room(self, name: str):
        name = name.strip()
        if not name:
            raise ValueError("Room name cannot be empty.")
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO rooms (name, created_at) VALUES (?, ?)",
                    (name, datetime.now().isoformat()),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            # Room already exists -- treat as a no-op (idempotent create-or-join)
            pass
        except sqlite3.Error as exc:
            raise RuntimeError(f"Database error while creating room: {exc}")

    def list_rooms(self):
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT name FROM rooms ORDER BY name").fetchall()
            return [r[0] for r in rows]
        except sqlite3.Error as exc:
            raise RuntimeError(f"Database error while listing rooms: {exc}")

    def get_room_id(self, name: str):
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT id FROM rooms WHERE name = ?", (name,)).fetchone()
            return row[0] if row else None
        except sqlite3.Error as exc:
            raise RuntimeError(f"Database error while fetching room: {exc}")

    # ---- Messages ----------------------------------------------------- #

    def add_message(self, room_name: str, sender: str, msg_type: str,
                     content: str, filename: str = None) -> str:
        timestamp = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                room_id = conn.execute(
                    "SELECT id FROM rooms WHERE name = ?", (room_name,)
                ).fetchone()
                if room_id is None:
                    raise ValueError(f"Room '{room_name}' does not exist.")
                conn.execute(
                    """INSERT INTO messages (room_id, sender, msg_type, content, filename, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (room_id[0], sender, msg_type, content, filename, timestamp),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Database error while saving message: {exc}")
        return timestamp

    def get_history(self, room_name: str, limit: int = 50):
        """Return the most recent `limit` messages for a room, oldest first."""
        try:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT m.sender, m.msg_type, m.content, m.filename, m.timestamp
                    FROM messages m
                    JOIN rooms r ON r.id = m.room_id
                    WHERE r.name = ?
                    ORDER BY m.id DESC
                    LIMIT ?
                """, (room_name, limit)).fetchall()
            return list(reversed(rows))
        except sqlite3.Error as exc:
            raise RuntimeError(f"Database error while fetching history: {exc}")
