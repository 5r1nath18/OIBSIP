# 📊 BMI Calculator & Tracker

A desktop GUI application for calculating Body Mass Index (BMI), classifying it into standard health categories, and tracking BMI history over time — built with Python, `tkinter`, `sqlite3`, and `matplotlib`.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **GUI application** — no command line required, built entirely with `tkinter`
- **Metric or imperial units** — enter weight/height in kg & cm, or lb & in
- **Instant BMI calculation** — with a color-coded result and a visual gauge showing where the value falls
- **Standard classification** — Underweight (< 18.5), Normal (18.5–24.9), Overweight (25–29.9), Obese (≥ 30)
- **Multi-user support** — save and switch between BMI records for different named users
- **Persistent history** — all records stored in a local SQLite database (`bmi_data.db`)
- **History management** — view, review, and delete past records in a table view
- **Trend visualization** — a `matplotlib` line chart of BMI over time, shaded by category, plus summary statistics (average, min, max, and trend direction)
- **Robust error handling** — validates numeric input and ranges, and gracefully reports database read/write failures


## Requirements

- Python 3.8+
- `tkinter` (usually bundled with Python; see [Installing tkinter](#installing-tkinter) below if missing)
- `matplotlib`
- `sqlite3` (built into the Python standard library — no install needed)

## Installation

```bash
git clone https://github.com/5r1nath18/OIBSIP/Python-Task2-BMICalculator.git
cd Python-Task2-BMICalculator
pip install -r requirements.txt
```

## Usage

```bash
python bmi_calculator.py
```

1. Type a name in the **"New user name..."** field and click **Add / Switch User** (or pick an existing user from the dropdown).
2. Choose **Metric** or **Imperial** units.
3. Enter your weight and height, then click **Calculate BMI**.
4. Your BMI, category, and a visual gauge appear instantly, and the record is saved automatically.
5. Switch to the **History** tab to view or delete past records.
6. Switch to the **Trends** tab to see a chart of BMI over time along with summary statistics.

A SQLite database file, `bmi_data.db`, is created automatically in the project folder on first run to store all users and records.

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
Python-Task2-BMICalculator/
├── bmi_calculator.py   # Main application
├── requirements.txt    # Python dependencies
├── README.md
├── LICENSE
└── .gitignore
```

> Note: `bmi_data.db` is generated automatically at runtime and is excluded from version control via `.gitignore`, since it contains local user data.

## How it works

1. **Calculation** — BMI is computed with the standard formula `weight (kg) / height (m)²`. Imperial inputs are converted to metric internally before calculating.
2. **Validation** — inputs are checked for being non-empty, numeric, positive, and within realistic human ranges before any calculation runs.
3. **Classification** — the result is matched against WHO-standard BMI category boundaries and paired with a color for visual feedback.
4. **Persistence** — each calculation is saved to a local SQLite database, tied to the active user, with a timestamp.
5. **Trends** — the Trends tab pulls a user's full history, plots it with `matplotlib` against shaded category bands, and computes average/min/max/trend statistics.

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

## Contributing

Issues and pull requests are welcome. Ideas for future improvements include exporting history to CSV, adding a dark theme, or supporting additional body composition metrics (e.g. waist-to-hip ratio).
