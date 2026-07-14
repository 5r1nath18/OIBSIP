"""
Random Password Generator — Advanced Tier

Dependencies:
    pip install pyperclip

Run:
    python password_generator.py
"""

import secrets
import string
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

MIN_LENGTH = 8
MAX_LENGTH = 64
MAX_HISTORY = 5

# Characters that are easy to visually confuse with one another
AMBIGUOUS_CHARS = "0Ol1IB8S5G6"

CHAR_SETS = {
    "upper": string.ascii_uppercase,
    "lower": string.ascii_lowercase,
    "digits": string.digits,
    "symbols": "!@#$%^&*()-_=+[]{};:,.<>?/|~",
}


# --------------------------------------------------------------------------
# Core password logic (kept separate from GUI for clarity / testability)
# --------------------------------------------------------------------------

def build_charset(selected_types: dict, exclude_ambiguous: bool) -> dict:
    """Return {type_name: pool_string} for each selected type, after
    stripping ambiguous characters if requested."""
    pools = {}
    for type_name, is_selected in selected_types.items():
        if not is_selected:
            continue
        pool = CHAR_SETS[type_name]
        if exclude_ambiguous:
            pool = "".join(c for c in pool if c not in AMBIGUOUS_CHARS)
        if pool:  # guard against a pool becoming empty after exclusion
            pools[type_name] = pool
    return pools


def generate_password(length: int, selected_types: dict, exclude_ambiguous: bool) -> str:
    """Generate a cryptographically secure password guaranteeing at least
    one character from every selected character type."""
    if length < MIN_LENGTH:
        raise ValueError(f"Password length must be at least {MIN_LENGTH}.")

    active_types = [t for t, on in selected_types.items() if on]
    if len(active_types) < 2:
        raise ValueError("Select at least 2 character types.")

    pools = build_charset(selected_types, exclude_ambiguous)
    if len(pools) < 2:
        raise ValueError(
            "Not enough usable characters after excluding ambiguous "
            "characters. Deselect 'Exclude ambiguous' or choose more types."
        )

    if length < len(pools):
        raise ValueError(
            f"Length must be >= number of selected character types ({len(pools)})."
        )

    # Guarantee at least one char from each selected pool
    password_chars = [secrets.choice(pool) for pool in pools.values()]

    # Fill the rest from the combined pool
    combined_pool = "".join(pools.values())
    remaining = length - len(password_chars)
    password_chars += [secrets.choice(combined_pool) for _ in range(remaining)]

    # Shuffle securely (Fisher-Yates using secrets.randbelow)
    for i in range(len(password_chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password_chars[i], password_chars[j] = password_chars[j], password_chars[i]

    return "".join(password_chars)


def evaluate_strength(password: str, selected_types: dict) -> tuple[str, int]:
    """Return (label, score 0-100) for a password's strength.

    Heuristic combines length and character-type diversity — no external
    libraries required, deterministic and explainable.
    """
    length = len(password)
    diversity = sum(1 for v in selected_types.values() if v)

    score = 0
    # Length contributes up to 60 points
    score += min(length, 20) * 2          # up to 40 for first 20 chars
    if length > 20:
        score += min(length - 20, 10)     # up to +10 more
    if length >= 30:
        score += 10                       # bonus for very long

    # Diversity contributes up to 40 points
    score += diversity * 10

    score = min(score, 100)

    if score < 45:
        label = "Weak"
    elif score < 75:
        label = "Medium"
    else:
        label = "Strong"

    return label, score


# --------------------------------------------------------------------------
# GUI Application
# --------------------------------------------------------------------------

class PasswordGeneratorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Secure Password Generator")
        self.resizable(False, False)
        self.configure(padx=20, pady=16)

        self.history: list[str] = []

        self._build_widgets()
        self._on_length_change(str(self.length_var.get()))

    # ---------------------------------------------------------------- UI --
    def _build_widgets(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        title = ttk.Label(self, text="🔐 Password Generator", font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, columnspan=3, pady=(0, 12), sticky="w")

        # --- Length control -------------------------------------------------
        ttk.Label(self, text="Length:").grid(row=1, column=0, sticky="w")
        self.length_var = tk.IntVar(value=16)

        self.length_slider = ttk.Scale(
            self, from_=MIN_LENGTH, to=MAX_LENGTH, orient="horizontal",
            variable=self.length_var, command=self._on_length_change, length=220
        )
        self.length_slider.grid(row=1, column=1, sticky="we", padx=8)

        self.length_spin = ttk.Spinbox(
            self, from_=MIN_LENGTH, to=MAX_LENGTH, width=5,
            textvariable=self.length_var, command=self._sync_from_spinbox
        )
        self.length_spin.grid(row=1, column=2, sticky="w")

        # --- Character type checkboxes --------------------------------------
        ttk.Label(self, text="Character types:").grid(row=2, column=0, sticky="nw", pady=(12, 0))

        self.type_vars = {
            "upper": tk.BooleanVar(value=True),
            "lower": tk.BooleanVar(value=True),
            "digits": tk.BooleanVar(value=True),
            "symbols": tk.BooleanVar(value=False),
        }
        labels = {
            "upper": "Uppercase (A-Z)",
            "lower": "Lowercase (a-z)",
            "digits": "Numbers (0-9)",
            "symbols": "Symbols (!@#$...)",
        }

        cb_frame = ttk.Frame(self)
        cb_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=(12, 0))
        for i, key in enumerate(["upper", "lower", "digits", "symbols"]):
            ttk.Checkbutton(cb_frame, text=labels[key], variable=self.type_vars[key]).grid(
                row=i // 2, column=i % 2, sticky="w", padx=(0, 12), pady=2
            )

        # --- Exclude ambiguous ----------------------------------------------
        self.exclude_ambig_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self, text="Exclude ambiguous characters (0, O, l, 1, I, ...)",
            variable=self.exclude_ambig_var
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        # --- Generate button --------------------------------------------------
        gen_btn = ttk.Button(self, text="Generate Password", command=self._on_generate)
        gen_btn.grid(row=4, column=0, columnspan=3, sticky="we", pady=(14, 6))

        # --- Password display --------------------------------------------------
        self.password_var = tk.StringVar(value="")
        pw_entry = ttk.Entry(self, textvariable=self.password_var, font=("Consolas", 14), justify="center")
        pw_entry.grid(row=5, column=0, columnspan=3, sticky="we", ipady=4)
        self.pw_entry = pw_entry

        # --- Copy button ---------------------------------------------------
        self.copy_btn = ttk.Button(self, text="📋 Copy to Clipboard", command=self._copy_to_clipboard)
        self.copy_btn.grid(row=6, column=0, columnspan=3, sticky="we", pady=(8, 6))
        if not CLIPBOARD_AVAILABLE:
            self.copy_btn.state(["disabled"])

        # --- Strength indicator ----------------------------------------------
        ttk.Label(self, text="Strength:").grid(row=7, column=0, sticky="w", pady=(10, 0))
        self.strength_label = ttk.Label(self, text="—", font=("Segoe UI", 10, "bold"))
        self.strength_label.grid(row=7, column=1, sticky="w", pady=(10, 0))

        self.strength_canvas = tk.Canvas(self, width=220, height=14, bg="#e0e0e0", highlightthickness=0)
        self.strength_canvas.grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.strength_bar = self.strength_canvas.create_rectangle(0, 0, 0, 14, fill="#cccccc", width=0)

        # --- History ------------------------------------------------------
        ttk.Label(self, text="History (this session, last 5):").grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(14, 2)
        )
        self.history_box = tk.Listbox(self, height=5, width=42, font=("Consolas", 10))
        self.history_box.grid(row=10, column=0, columnspan=3, sticky="we")
        self.history_box.bind("<<ListboxSelect>>", self._on_history_select)

        if not CLIPBOARD_AVAILABLE:
            note = ttk.Label(
                self,
                text="Note: pyperclip not installed — clipboard disabled.\nRun: pip install pyperclip",
                foreground="#b00020",
            )
            note.grid(row=11, column=0, columnspan=3, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------ helpers --
    def _on_length_change(self, _value):
        # Keep spinbox and slider in sync, force integer display
        self.length_var.set(int(float(self.length_var.get())))

    def _sync_from_spinbox(self):
        self._on_length_change(None)

    def _copy_to_clipboard(self):
        pw = self.password_var.get()
        if not pw:
            messagebox.showinfo("Nothing to copy", "Generate a password first.")
            return
        if not CLIPBOARD_AVAILABLE:
            messagebox.showwarning("Clipboard unavailable", "Install pyperclip to enable clipboard copy.")
            return
        try:
            pyperclip.copy(pw)
        except Exception as e:
            messagebox.showwarning(
                "Clipboard unavailable",
                f"Could not access the system clipboard.\n"
                f"On Linux, try: sudo apt-get install xclip\n\nDetails: {e}"
            )

    def _on_history_select(self, _event):
        sel = self.history_box.curselection()
        if not sel:
            return
        item = self.history_box.get(sel[0])
        # Strip the leading index label, e.g. "1. abc123" -> "abc123"
        pw = item.split(". ", 1)[-1]
        self.password_var.set(pw)

    def _update_strength_ui(self, password: str):
        selected = {k: v.get() for k, v in self.type_vars.items()}
        label, score = evaluate_strength(password, selected)

        colors = {"Weak": "#e53935", "Medium": "#fb8c00", "Strong": "#43a047"}
        self.strength_label.config(text=f"{label}  ({score}/100)", foreground=colors[label])

        width = int(220 * score / 100)
        self.strength_canvas.coords(self.strength_bar, 0, 0, width, 14)
        self.strength_canvas.itemconfig(self.strength_bar, fill=colors[label])

    def _push_history(self, password: str):
        self.history.insert(0, password)
        self.history = self.history[:MAX_HISTORY]
        self.history_box.delete(0, tk.END)
        for i, pw in enumerate(self.history, start=1):
            self.history_box.insert(tk.END, f"{i}. {pw}")

    # ------------------------------------------------------------- action --
    def _on_generate(self):
        selected = {k: v.get() for k, v in self.type_vars.items()}
        length = int(self.length_var.get())
        exclude_ambiguous = self.exclude_ambig_var.get()

        try:
            password = generate_password(length, selected, exclude_ambiguous)
        except ValueError as e:
            messagebox.showerror("Invalid selection", str(e))
            return

        self.password_var.set(password)
        self._update_strength_ui(password)
        self._push_history(password)

        # Auto-copy on generation (best-effort — never let clipboard issues
        # prevent the password from being generated/displayed)
        if CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(password)
            except Exception:
                pass


# --------------------------------------------------------------------------
if __name__ == "__main__":
    app = PasswordGeneratorApp()
    app.mainloop()

