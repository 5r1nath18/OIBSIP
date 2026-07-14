# 🔐 Secure Password Generator

A desktop GUI tool for generating strong, cryptographically secure passwords, built with Python's `tkinter` and `secrets` modules.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **GUI controls** — slider and spinbox for password length (8–64 characters), checkboxes for character type selection
- **Cryptographically secure** — uses Python's `secrets` module (not `random`) for all randomness
- **Guaranteed diversity** — the generated password always contains at least one character from every selected type
- **Strength indicator** — a live Weak / Medium / Strong label with a color-coded strength bar
- **Clipboard integration** — one-click "Copy to Clipboard," plus automatic copy on generation (via `pyperclip`)
- **Ambiguous character exclusion** — optional toggle to remove visually confusing characters (`0`, `O`, `l`, `1`, `I`, etc.)
- **Session history** — the last 5 generated passwords are shown in-app; nothing is ever written to disk


## Requirements

- Python 3.8+
- `tkinter` (usually bundled with Python; see [Installing tkinter](#installing-tkinter) below if missing)
- `pyperclip`

## Installation

```bash
git clone https://github.com/5r1nath18/OIBSIP_PythonProgramming_Task3.git
cd OIBSIP_PythonProgramming_Task3
pip install -r requirements.txt
```

## Usage

```bash
python password_generator.py
```

1. Set the desired password length using the slider or spinbox.
2. Select at least two character types (uppercase, lowercase, numbers, symbols).
3. Optionally enable "Exclude ambiguous characters."
4. Click **Generate Password** — the password is generated, displayed, auto-copied to your clipboard, and added to the session history.
5. Click **Copy to Clipboard** at any time to re-copy the current password.
6. Click any entry in the history list to reload it into the password field.

## Installing pyperclip

`pyperclip` is the only third-party dependency and handles clipboard copy/paste. Install it with pip:

```bash
pip install pyperclip
```

Or, if you're using the provided `requirements.txt` (installs all dependencies at once):

```bash
pip install -r requirements.txt
```

If `pip` isn't recognized, try `pip3` or `python -m pip install pyperclip` instead.

> **Note:** The app still runs without `pyperclip` — it just disables the clipboard button and skips auto-copy on generation, with an on-screen note explaining why.

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

## Clipboard support on Linux

`pyperclip` requires a system clipboard utility on Linux. If clipboard copy fails, install one of:

```bash
sudo apt-get install xclip
# or
sudo apt-get install xselect
# or, for Wayland
sudo apt-get install wl-clipboard
```

## Project Structure

```
secure-password-generator/
├── password_generator.py   # Main application
├── requirements.txt        # Python dependencies
├── README.md
├── LICENSE
└── .gitignore
```

## How password generation works

1. Character pools are built from the selected types (uppercase, lowercase, digits, symbols), with ambiguous characters optionally stripped out.
2. One character is drawn from each selected pool using `secrets.choice` to guarantee type diversity.
3. The remaining length is filled from the combined pool, also using `secrets.choice`.
4. The full character list is shuffled using a `secrets.randbelow`-driven Fisher–Yates shuffle to avoid predictable positioning.

This ensures the output is both diverse (guaranteed character types) and unpredictable (CSPRNG-backed), which is a stronger guarantee than using Python's `random` module.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

## Contributing

Issues and pull requests are welcome. If you spot a bug or have an idea for a feature (e.g. a passphrase mode, dark theme, or password export with encryption), feel free to open an issue.
