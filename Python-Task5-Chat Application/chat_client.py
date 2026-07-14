"""
chat_client.py
----------------
Tkinter GUI client for the chat application.

Run:
    python chat_client.py [--host 127.0.0.1] [--port 5555]
"""

import argparse
import base64
import io
import os
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from protocol import send_msg, recv_msg, ConnectionClosed
import crypto_utils

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB cap for shared files/images

EMOJI_PALETTE = [
    "😀", "😂", "😍", "😎", "😢", "😡", "👍", "👎",
    "🙏", "🎉", "❤️", "🔥", "🤔", "👀", "🚀", "✅",
]


# --------------------------------------------------------------------------- #
# Networking layer -- runs the socket + background receive thread
# --------------------------------------------------------------------------- #

class ChatNetworkClient:
    """Owns the socket connection and a background thread that pushes
    incoming server messages onto a thread-safe queue for the GUI to poll."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: socket.socket = None
        self.incoming: "queue.Queue[dict]" = queue.Queue()
        self._recv_thread: threading.Thread = None
        self._running = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def _recv_loop(self):
        while self._running:
            try:
                msg = recv_msg(self.sock)
            except (ConnectionClosed, OSError, ValueError):
                self.incoming.put({"type": "_disconnected"})
                return
            self.incoming.put(msg)

    def send(self, obj: dict):
        if not self.sock:
            raise ConnectionError("Not connected.")
        send_msg(self.sock, obj)

    def close(self):
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass


# --------------------------------------------------------------------------- #
# Toast notification (simple in-app popup for background rooms)
# --------------------------------------------------------------------------- #

class Toast(tk.Toplevel):
    def __init__(self, parent, title: str, message: str, duration_ms=3500):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#2c3e50")

        frame = tk.Frame(self, bg="#2c3e50", padx=14, pady=10)
        frame.pack()
        tk.Label(frame, text=title, bg="#2c3e50", fg="#ecf0f1",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(frame, text=message, bg="#2c3e50", fg="#bdc3c7",
                  font=("Segoe UI", 9), wraplength=260, justify="left").pack(anchor="w")

        self.update_idletasks()
        # Position: bottom-right corner of the parent window's screen
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = self.winfo_width()
        h = self.winfo_height()
        x = sw - w - 24
        y = sh - h - 60
        self.geometry(f"+{x}+{y}")

        self.after(duration_ms, self.destroy)


# --------------------------------------------------------------------------- #
# Login / Registration window
# --------------------------------------------------------------------------- #

class LoginWindow(tk.Tk):
    def __init__(self, host, port):
        super().__init__()
        self.title("Chat App - Login")
        self.geometry("360x300")
        self.resizable(False, False)

        self.host = host
        self.port = port
        self.net: ChatNetworkClient = None
        self.pending_action = None  # "login" or "register"

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        tk.Label(self, text="💬 Chat App", font=("Segoe UI", 18, "bold")).pack(pady=(20, 10))

        form = ttk.Frame(self)
        form.pack(**pad)

        ttk.Label(form, text="Username:").grid(row=0, column=0, sticky="e", pady=4)
        self.username_entry = ttk.Entry(form, width=24)
        self.username_entry.grid(row=0, column=1, pady=4)

        ttk.Label(form, text="Password:").grid(row=1, column=0, sticky="e", pady=4)
        self.password_entry = ttk.Entry(form, width=24, show="*")
        self.password_entry.grid(row=1, column=1, pady=4)
        self.password_entry.bind("<Return>", lambda e: self._login())

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=14)
        ttk.Button(btn_frame, text="Log In", command=self._login).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Register", command=self._do_register).pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, foreground="#c0392b",
                  wraplength=320, justify="center").pack(pady=6)

        conn_frame = ttk.Frame(self)
        conn_frame.pack(side="bottom", pady=10)
        ttk.Label(conn_frame, text=f"Server: {self.host}:{self.port}",
                  font=("Segoe UI", 8), foreground="#7f8c8d").pack()

    def _ensure_connected(self) -> bool:
        if self.net is not None:
            return True
        try:
            self.net = ChatNetworkClient(self.host, self.port)
            self.net.connect()
            return True
        except OSError as exc:
            self.status_var.set(f"Could not connect to server: {exc}")
            self.net = None
            return False

    def _login(self):
        self._submit("login")

    def _do_register(self):
        self._submit("register")

    def _submit(self, action):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            self.status_var.set("Please enter both a username and password.")
            return

        if not self._ensure_connected():
            return

        self.status_var.set("Connecting...")
        self.pending_action = action
        self.net.send({"action": action, "username": username, "password": password})
        self.after(100, self._poll_auth_response)

    def _poll_auth_response(self):
        try:
            msg = self.net.incoming.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_auth_response)
            return

        if msg.get("type") == "_disconnected":
            self.status_var.set("Lost connection to server.")
            self.net = None
            return

        if msg.get("type") == "error":
            self.status_var.set(msg.get("message", "Unknown error."))
            return

        if msg.get("type") == "auth_result" and msg.get("status") == "ok":
            if self.pending_action == "register":
                self.status_var.set("Registered! You can now log in.")
                return
            # Logged in -- hand off to the main app window
            username = msg.get("username")
            self.withdraw()
            app = ChatApp(self, self.net, username)
            app.protocol("WM_DELETE_WINDOW", lambda: self._on_app_close(app))
            return

        # Unexpected message type while waiting -- keep polling
        self.after(100, self._poll_auth_response)

    def _on_app_close(self, app):
        app.shutdown()
        self.destroy()


# --------------------------------------------------------------------------- #
# Main application window (lobby + room switching)
# --------------------------------------------------------------------------- #

class ChatApp(tk.Toplevel):
    def __init__(self, parent, net: ChatNetworkClient, username: str):
        super().__init__(parent)
        self.title(f"Chat App - {username}")
        self.geometry("420x480")

        self.net = net
        self.username = username
        self.cipher = crypto_utils.MessageCipher()

        self.current_room = None
        self.room_frames = {}  # room_name -> RoomFrame
        self.unread_counts = {}  # room_name -> int

        self._build_lobby()
        self._poll_incoming()
        self.net.send({"action": "list_rooms"})

        self.deiconify()
        self.focus_force()

    # ---- UI ------------------------------------------------------------- #

    def _build_lobby(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text=f"Logged in as {self.username}",
                  font=("Segoe UI", 11, "bold")).pack(side="left")

        room_frame = ttk.LabelFrame(self, text="Rooms", padding=10)
        room_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.room_listbox = tk.Listbox(room_frame, height=12)
        self.room_listbox.pack(fill="both", expand=True)
        self.room_listbox.bind("<Double-Button-1>", lambda e: self._join_selected_room())

        btn_frame = ttk.Frame(room_frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_frame, text="Join Room", command=self._join_selected_room).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="New Room...", command=self._create_room).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_rooms).pack(side="left", padx=4)

    def _refresh_rooms(self):
        self.net.send({"action": "list_rooms"})

    def _create_room(self):
        name = simpledialog.askstring("New Room", "Room name:", parent=self)
        if name and name.strip():
            self.net.send({"action": "create_room", "room": name.strip()})

    def _join_selected_room(self):
        sel = self.room_listbox.curselection()
        if not sel:
            messagebox.showinfo("No Selection", "Please select a room to join.", parent=self)
            return
        room = self.room_listbox.get(sel[0])
        self._open_room(room)

    def _open_room(self, room: str):
        self.net.send({"action": "join_room", "room": room})
        # RoomFrame is created once the server confirms room_joined (see _poll_incoming)
        self._pending_join = room

    # ---- Incoming message pump ------------------------------------------- #

    def _poll_incoming(self):
        try:
            while True:
                msg = self.net.incoming.get_nowait()
                self._handle_incoming(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_incoming)

    def _handle_incoming(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == "_disconnected":
            messagebox.showerror("Disconnected", "Lost connection to the server.", parent=self)
            return

        if msg_type == "room_list":
            self.room_listbox.delete(0, tk.END)
            for room in msg.get("rooms", []):
                self.room_listbox.insert(tk.END, room)
            return

        if msg_type == "room_joined":
            room = msg["room"]
            if room not in self.room_frames:
                self._create_room_window(room)
            self.current_room = room
            self.net.send({"action": "get_history", "room": room, "limit": 50})
            return

        if msg_type == "history":
            room = msg["room"]
            frame = self.room_frames.get(room)
            if frame:
                frame.load_history(msg.get("messages", []))
            return

        if msg_type == "chat_message":
            room = msg["room"]
            frame = self.room_frames.get(room)
            if frame:
                frame.display_message(msg)
                if not frame.is_focused() and msg.get("sender") != self.username:
                    self._notify(room, msg)
            return

        if msg_type == "notice":
            room = msg["room"]
            frame = self.room_frames.get(room)
            if frame:
                frame.display_notice(msg.get("message", ""))
            return

        if msg_type == "error":
            messagebox.showerror("Error", msg.get("message", "Unknown error."), parent=self)
            return

    def _create_room_window(self, room: str):
        frame = RoomWindow(self, room)
        self.room_frames[room] = frame

    def _notify(self, room: str, msg: dict):
        sender = msg.get("sender", "Someone")
        msg_type = msg.get("msg_type", "text")
        if msg_type == "text":
            try:
                preview = self.cipher.decrypt(msg["content"])
            except ValueError:
                preview = "[unable to decrypt]"
        else:
            preview = f"sent a {msg_type}"
        try:
            Toast(self, f"#{room} - {sender}", preview[:120])
        except tk.TclError:
            pass
        self.bell()

    # ---- Shutdown --------------------------------------------------------- #

    def shutdown(self):
        try:
            self.net.send({"action": "logout"})
        except OSError:
            pass
        self.net.close()


# --------------------------------------------------------------------------- #
# Room window -- one per joined chat room
# --------------------------------------------------------------------------- #

class RoomWindow(tk.Toplevel):
    def __init__(self, app: ChatApp, room: str):
        super().__init__(app)
        self.app = app
        self.room = room
        self.title(f"#{room}")
        self.geometry("560x520")

        self._focused = True
        self.bind("<FocusIn>", lambda e: self._set_focused(True))
        self.bind("<FocusOut>", lambda e: self._set_focused(False))

        self._image_refs = []  # keep PhotoImage references alive
        self._build_ui()

    def _set_focused(self, value: bool):
        self._focused = value

    def is_focused(self) -> bool:
        try:
            return self._focused and bool(self.focus_displayof())
        except tk.TclError:
            return False

    def _build_ui(self):
        self.text = tk.Text(self, state="disabled", wrap="word", height=20)
        self.text.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.text.tag_configure("sender", font=("Segoe UI", 9, "bold"))
        self.text.tag_configure("meta", font=("Segoe UI", 8), foreground="#7f8c8d")
        self.text.tag_configure("notice", font=("Segoe UI", 8, "italic"), foreground="#95a5a6")
        self.text.tag_configure("body", font=("Segoe UI", 10))

        scrollbar = ttk.Scrollbar(self, command=self.text.yview)
        self.text["yscrollcommand"] = scrollbar.set

        entry_frame = ttk.Frame(self)
        entry_frame.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(entry_frame, text="😊", width=3, command=self._open_emoji_picker).pack(side="left")
        ttk.Button(entry_frame, text="📎", width=3, command=self._send_file).pack(side="left", padx=(4, 4))

        self.entry = ttk.Entry(entry_frame)
        self.entry.pack(side="left", fill="x", expand=True, padx=4)
        self.entry.bind("<Return>", lambda e: self._send_text())
        self.entry.focus_set()

        ttk.Button(entry_frame, text="Send", command=self._send_text).pack(side="left", padx=(4, 0))

    # ---- Sending ------------------------------------------------------- #

    def _send_text(self):
        text = self.entry.get().strip()
        if not text:
            return
        ciphertext = self.app.cipher.encrypt(text)
        self.app.net.send({
            "action": "send_message", "room": self.room, "type": "text", "content": ciphertext,
        })
        self.entry.delete(0, tk.END)

    def _open_emoji_picker(self):
        picker = tk.Toplevel(self)
        picker.title("Emoji")
        picker.resizable(False, False)
        for i, emoji in enumerate(EMOJI_PALETTE):
            b = tk.Button(picker, text=emoji, font=("Segoe UI", 14), width=3,
                          command=lambda e=emoji: self._insert_emoji(e, picker))
            b.grid(row=i // 8, column=i % 8, padx=2, pady=2)

    def _insert_emoji(self, emoji: str, picker: tk.Toplevel):
        self.entry.insert(tk.END, emoji)
        picker.destroy()
        self.entry.focus_set()

    def _send_file(self):
        path = filedialog.askopenfilename(title="Select a file to share")
        if not path:
            return
        try:
            size = os.path.getsize(path)
            if size > MAX_FILE_SIZE:
                messagebox.showerror(
                    "File Too Large",
                    f"File is {size / 1024 / 1024:.1f} MB. Max allowed is "
                    f"{MAX_FILE_SIZE / 1024 / 1024:.0f} MB.",
                    parent=self,
                )
                return
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as exc:
            messagebox.showerror("File Error", f"Could not read file: {exc}", parent=self)
            return

        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1].lower()
        msg_type = "image" if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp") else "file"

        b64_data = crypto_utils.encode_bytes(raw)
        ciphertext = self.app.cipher.encrypt(b64_data)

        self.app.net.send({
            "action": "send_message", "room": self.room, "type": msg_type,
            "content": ciphertext, "filename": filename,
        })

    # ---- Receiving / rendering ------------------------------------------ #

    def load_history(self, messages: list):
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.configure(state="disabled")
        self._image_refs.clear()
        for msg in messages:
            self.display_message({
                "sender": msg["sender"], "msg_type": msg["msg_type"],
                "content": msg["content"], "filename": msg.get("filename"),
                "timestamp": msg["timestamp"],
            })

    def display_notice(self, text: str):
        self.text.configure(state="normal")
        self.text.insert(tk.END, f"  * {text}\n", "notice")
        self.text.configure(state="disabled")
        self.text.see(tk.END)

    def display_message(self, msg: dict):
        sender = msg.get("sender", "?")
        msg_type = msg.get("msg_type", "text")
        timestamp = msg.get("timestamp", "")[:19].replace("T", " ")
        filename = msg.get("filename")

        try:
            plaintext_or_b64 = self.app.cipher.decrypt(msg["content"])
        except ValueError:
            plaintext_or_b64 = None

        self.text.configure(state="normal")
        self.text.insert(tk.END, f"{sender}  ", "sender")
        self.text.insert(tk.END, f"{timestamp}\n", "meta")

        if plaintext_or_b64 is None:
            self.text.insert(tk.END, "[unable to decrypt message]\n\n", "body")
        elif msg_type == "text":
            self.text.insert(tk.END, f"{plaintext_or_b64}\n\n", "body")
        elif msg_type in ("image", "file"):
            raw = crypto_utils.decode_bytes(plaintext_or_b64)
            if msg_type == "image" and PIL_AVAILABLE:
                self._insert_image_preview(raw, filename)
            else:
                self._insert_file_link(raw, filename)

        self.text.configure(state="disabled")
        self.text.see(tk.END)

    def _insert_image_preview(self, raw: bytes, filename: str):
        try:
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((320, 320))
            photo = ImageTk.PhotoImage(img)
            self._image_refs.append(photo)  # prevent garbage collection
            self.text.image_create(tk.END, image=photo)
            self.text.insert(tk.END, f"\n[{filename}]\n\n", "meta")
        except Exception:
            self._insert_file_link(raw, filename)

    def _insert_file_link(self, raw: bytes, filename: str):
        display_name = filename or "shared_file"

        def save_file():
            path = filedialog.asksaveasfilename(initialfile=display_name)
            if path:
                with open(path, "wb") as f:
                    f.write(raw)
                messagebox.showinfo("Saved", f"Saved to {path}", parent=self)

        btn = tk.Button(self.text, text=f"📎 {display_name} (click to save)",
                        fg="#2980b9", relief="flat", cursor="hand2", command=save_file)
        self.text.window_create(tk.END, window=btn)
        self.text.insert(tk.END, "\n\n")


# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Chat client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5555)
    args = parser.parse_args()

    app = LoginWindow(args.host, args.port)
    app.mainloop()


if __name__ == "__main__":
    main()
