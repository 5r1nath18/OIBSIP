# 💬 Chat Application

A multi-user, multi-room chat application with a Tkinter GUI, built on a custom TCP client-server protocol. Messages are end-to-end encrypted before they ever leave the client, user accounts are password-protected, and the server persists history in SQLite.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Client-server architecture** — a multi-threaded TCP server (`chat_server.py`) handles any number of concurrent clients, each on its own thread
- **User authentication** — registration and login with PBKDF2-HMAC-SHA256 password hashing (random per-user salt, 200,000 iterations); duplicate logins are rejected
- **Multiple chat rooms** — create rooms on the fly, switch between them, each with its own live message feed and independent history
- **GUI client** — built with Tkinter: login screen, room lobby, and a dedicated window per open chat room
- **Multimedia sharing** — send images (rendered inline via Pillow) or arbitrary files (delivered as a click-to-save button), capped at 5 MB
- **Message history** — every room's messages are stored in SQLite and reloaded automatically when you join
- **Emoji support** — type Unicode emoji directly, or use the built-in emoji picker (😊 button)
- **Notifications** — an in-app toast notification pops up for new messages in rooms that aren't currently focused
- **Encryption** — all message content (text, images, files) is encrypted client-side with a shared Fernet (AES-128 + HMAC) key before transmission; the server only ever stores and relays ciphertext


## Requirements

- Python 3.8+
- `tkinter` (usually bundled with Python; see [Installing tkinter](#installing-tkinter) below if missing)
- `cryptography` (Fernet encryption)
- `Pillow` (inline image previews — optional but recommended)

## Installation

```bash
git clone https://github.com/5r1nath18/OIBSIP/Python-Task5-Chat Application.git
cd Python-Task5-Chat Application
pip install -r requirements.txt
```

## Usage

### 1. Start the server

```bash
python chat_server.py --host 0.0.0.0 --port 5555
```

On first run, the server generates `chat_data.db` (SQLite) and `secret.key` (the shared Fernet encryption key) in the project folder.

### 2. Share the encryption key

**Copy `secret.key` to every machine that will run the client.** All clients must use the same key to decrypt each other's messages — the server never has plaintext access to message content, so a mismatched key means undecryptable messages, not a server-side fix.

### 3. Start one or more clients

```bash
python chat_client.py --host <server-ip> --port 5555
```

- Register a username and password, then log in.
- Double-click a room in the lobby to join it (or select it and click **Join Room**).
- Click **New Room...** to create and join a new room.
- Type a message and press Enter or click **Send**.
- Click 😊 to open the emoji picker, or 📎 to share a file/image.
- If a message arrives in a room you're not currently focused on, a toast notification appears.

## Installing tkinter

`tkinter` ships with most Python installations, but on some Linux distributions it must be installed separately:

```bash
# Debian / Ubuntu
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

## Project Structure

```
Python-Task5-Chat Application/
├── chat_server.py      # TCP server: auth, rooms, message relay, persistence
├── chat_client.py      # Tkinter GUI client
├── db.py                # SQLite layer (users, rooms, messages)
├── protocol.py           # Length-prefixed JSON framing over sockets
├── crypto_utils.py       # Password hashing + Fernet message encryption
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```

> `chat_data.db` and `secret.key` are generated automatically at runtime and are excluded from version control via `.gitignore`. You are responsible for distributing `secret.key` to clients out-of-band (e.g. a secure file transfer) — it should never be committed to the repo.

## How it works

### Networking
The client and server communicate over raw TCP sockets using a simple length-prefixed JSON protocol (`protocol.py`): every message is a 4-byte big-endian length header followed by that many bytes of UTF-8 JSON. This avoids the classic problem of TCP being a byte stream rather than a sequence of discrete messages.

### Authentication
Passwords are hashed with PBKDF2-HMAC-SHA256 using a random 16-byte salt per user and 200,000 iterations, then compared in constant time on login to avoid timing attacks. Plaintext passwords are never stored.

### Encryption model
Message content is encrypted client-side using a single shared **Fernet** symmetric key (`secret.key`), distributed out-of-band to every client. This is a pre-shared-key (PSK) model appropriate for a private deployment — everyone with the key can read messages, but the server itself cannot, since it only stores and relays ciphertext. This is a deliberate simplification versus a full per-conversation public-key system like Signal, documented here so it's not mistaken for one.

### Rooms & broadcasting
The server tracks room membership in memory and persists messages to SQLite. When a client sends a message, the server stores it and broadcasts it live to every member of that room — including the sender, so all clients render purely from the same live broadcast channel rather than needing a separate "optimistic local echo" path.

### Multimedia
Images and files are read as raw bytes, base64-encoded, encrypted, and sent as a normal JSON message (capped at 5 MB to keep things responsive). On the receiving end, image files are decoded and rendered inline via Pillow; other files appear as a labeled button that saves the file to disk when clicked.

## Limitations & possible extensions

- The encryption model uses one shared key for the whole deployment, not per-room or per-conversation keys.
- No TLS on the socket itself — encryption is applied at the application layer to message *content* only; deploying behind a VPN or adding a TLS wrapper would harden metadata (who's talking to whom, timing) further.
- No read receipts, typing indicators, or offline push notifications (the toast notification only fires while the client app is running).
- Ideas for extension: per-room encryption keys, TLS transport, message search, read receipts, avatar/profile support.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

## Contributing

Issues and pull requests are welcome.
