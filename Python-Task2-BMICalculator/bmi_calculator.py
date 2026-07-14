"""
BMI Calculator - A graphical application built with Tkinter.
"""

import os
import sqlite3
from datetime import datetime, date

import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bmi_data.db")

# (label, lower_bound_inclusive, upper_bound_exclusive, color)
BMI_CATEGORIES = [
    ("Underweight", 0.0, 18.5, "#3498db"),     # blue
    ("Normal weight", 18.5, 25.0, "#2ecc71"),  # green
    ("Overweight", 25.0, 30.0, "#f39c12"),     # orange
    ("Obese", 30.0, 100.0, "#e74c3c"),         # red
]

# Reasonable real-world input ranges (used for validation)
WEIGHT_KG_RANGE = (2.0, 500.0)
HEIGHT_CM_RANGE = (30.0, 280.0)
WEIGHT_LB_RANGE = (4.0, 1100.0)
HEIGHT_IN_RANGE = (12.0, 110.0)

KG_PER_LB = 0.45359237
CM_PER_IN = 2.54


# --------------------------------------------------------------------------- #
# BMI helper functions
# --------------------------------------------------------------------------- #

def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """Return BMI = weight (kg) / height (m)^2."""
    height_m = height_cm / 100.0
    return weight_kg / (height_m ** 2)


def categorize_bmi(bmi: float):
    """Return (category_label, color_hex) for a given BMI value."""
    for label, lower, upper, color in BMI_CATEGORIES:
        if lower <= bmi < upper:
            return label, color
    # Fallback for any extreme/edge values
    return "Obese", BMI_CATEGORIES[-1][3]


# --------------------------------------------------------------------------- #
# Data layer
# --------------------------------------------------------------------------- #

class BMIDatabase:
    """Handles all persistence (SQLite) for users and BMI records."""

    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        # check_same_thread=False so it plays nicely with Tkinter callbacks
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        try:
            with self._connect() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        record_date TEXT NOT NULL,
                        weight_kg REAL NOT NULL,
                        height_cm REAL NOT NULL,
                        bmi REAL NOT NULL,
                        category TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                conn.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Could not initialize database: {exc}")

    # ---- Users ------------------------------------------------------- #

    def get_users(self):
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT id, name FROM users ORDER BY name").fetchall()
            return rows
        except sqlite3.Error as exc:
            raise RuntimeError(f"Could not load users: {exc}")

    def get_or_create_user(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("User name cannot be empty.")
        try:
            with self._connect() as conn:
                cur = conn.execute("SELECT id FROM users WHERE name = ?", (name,))
                row = cur.fetchone()
                if row:
                    return row[0]
                cur = conn.execute("INSERT INTO users (name) VALUES (?)", (name,))
                conn.commit()
                return cur.lastrowid
        except sqlite3.Error as exc:
            raise RuntimeError(f"Could not create/find user: {exc}")

    # ---- Records ------------------------------------------------------ #

    def add_record(self, user_id: int, weight_kg: float, height_cm: float,
                    bmi: float, category: str, record_date: str = None):
        record_date = record_date or datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO records (user_id, record_date, weight_kg, height_cm, bmi, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, record_date, weight_kg, height_cm, bmi, category))
                conn.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Could not save record: {exc}")

    def get_history(self, user_id: int):
        try:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT id, record_date, weight_kg, height_cm, bmi, category
                    FROM records WHERE user_id = ?
                    ORDER BY record_date ASC
                """, (user_id,)).fetchall()
            return rows
        except sqlite3.Error as exc:
            raise RuntimeError(f"Could not load history: {exc}")

    def delete_record(self, record_id: int):
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
                conn.commit()
        except sqlite3.Error as exc:
            raise RuntimeError(f"Could not delete record: {exc}")


# --------------------------------------------------------------------------- #
# Main Application
# --------------------------------------------------------------------------- #

class BMIApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("BMI Calculator & Tracker")
        self.geometry("760x640")
        self.minsize(680, 560)

        # Database
        try:
            self.db = BMIDatabase()
        except RuntimeError as exc:
            messagebox.showerror("Database Error", str(exc))
            self.destroy()
            return

        # Shared state
        self.unit_var = tk.StringVar(value="metric")  # "metric" or "imperial"
        self.current_user_id = None

        self._build_user_bar()
        self._build_notebook()

        self._refresh_user_list()

    # ------------------------------------------------------------------ #
    # Top bar: user selection
    # ------------------------------------------------------------------ #

    def _build_user_bar(self):
        bar = ttk.Frame(self, padding=10)
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="Active user:", font=("Segoe UI", 10, "bold")).pack(side="left")

        self.user_combo = ttk.Combobox(bar, state="readonly", width=25)
        self.user_combo.pack(side="left", padx=8)
        self.user_combo.bind("<<ComboboxSelected>>", self._on_user_selected)

        self.new_user_entry = ttk.Entry(bar, width=20)
        self.new_user_entry.pack(side="left", padx=(20, 5))
        self.new_user_entry.insert(0, "New user name...")
        self.new_user_entry.bind("<FocusIn>", self._clear_placeholder)

        ttk.Button(bar, text="Add / Switch User", command=self._add_or_switch_user).pack(side="left")

    def _clear_placeholder(self, _event):
        if self.new_user_entry.get() == "New user name...":
            self.new_user_entry.delete(0, tk.END)

    def _refresh_user_list(self, select_id=None):
        try:
            users = self.db.get_users()
        except RuntimeError as exc:
            messagebox.showerror("Database Error", str(exc))
            users = []

        self._user_lookup = {name: uid for uid, name in users}
        self.user_combo["values"] = list(self._user_lookup.keys())

        if not users:
            self.current_user_id = None
            self.user_combo.set("")
            return

        if select_id is not None:
            for name, uid in self._user_lookup.items():
                if uid == select_id:
                    self.user_combo.set(name)
                    self.current_user_id = uid
                    break
        elif self.current_user_id is None:
            self.user_combo.current(0)
            self.current_user_id = self._user_lookup[self.user_combo.get()]

        self._on_user_changed()

    def _add_or_switch_user(self):
        name = self.new_user_entry.get().strip()
        if not name or name == "New user name...":
            messagebox.showwarning("Missing Name", "Please type a user name first.")
            return
        try:
            uid = self.db.get_or_create_user(name)
        except (RuntimeError, ValueError) as exc:
            messagebox.showerror("Error", str(exc))
            return

        self.new_user_entry.delete(0, tk.END)
        self.new_user_entry.insert(0, "New user name...")
        self._refresh_user_list(select_id=uid)

    def _on_user_selected(self, _event=None):
        name = self.user_combo.get()
        self.current_user_id = self._user_lookup.get(name)
        self._on_user_changed()

    def _on_user_changed(self):
        """Called whenever the active user changes; refresh dependent tabs."""
        self._reset_result_display()
        self.refresh_history()
        self.refresh_trends()

    # ------------------------------------------------------------------ #
    # Notebook (tabs)
    # ------------------------------------------------------------------ #

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tab_calc = ttk.Frame(self.notebook, padding=15)
        self.tab_history = ttk.Frame(self.notebook, padding=15)
        self.tab_trends = ttk.Frame(self.notebook, padding=15)

        self.notebook.add(self.tab_calc, text="Calculator")
        self.notebook.add(self.tab_history, text="History")
        self.notebook.add(self.tab_trends, text="Trends")

        self._build_calculator_tab()
        self._build_history_tab()
        self._build_trends_tab()

    # ------------------------------------------------------------------ #
    # Tab 1: Calculator
    # ------------------------------------------------------------------ #

    def _build_calculator_tab(self):
        frame = self.tab_calc

        # --- Units ---
        units_frame = ttk.LabelFrame(frame, text="Units", padding=10)
        units_frame.pack(fill="x", pady=(0, 12))

        ttk.Radiobutton(units_frame, text="Metric (kg / cm)", variable=self.unit_var,
                        value="metric", command=self._update_unit_labels).pack(side="left", padx=10)
        ttk.Radiobutton(units_frame, text="Imperial (lb / in)", variable=self.unit_var,
                        value="imperial", command=self._update_unit_labels).pack(side="left", padx=10)

        # --- Inputs ---
        input_frame = ttk.LabelFrame(frame, text="Your Measurements", padding=12)
        input_frame.pack(fill="x", pady=(0, 12))

        self.weight_label_var = tk.StringVar()
        self.height_label_var = tk.StringVar()

        ttk.Label(input_frame, textvariable=self.weight_label_var, width=14).grid(
            row=0, column=0, sticky="w", pady=6)
        self.weight_entry = ttk.Entry(input_frame, width=15)
        self.weight_entry.grid(row=0, column=1, padx=10, pady=6)

        ttk.Label(input_frame, textvariable=self.height_label_var, width=14).grid(
            row=1, column=0, sticky="w", pady=6)
        self.height_entry = ttk.Entry(input_frame, width=15)
        self.height_entry.grid(row=1, column=1, padx=10, pady=6)

        self._update_unit_labels()

        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(button_frame, text="Calculate BMI", command=self.calculate).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Clear", command=self._clear_inputs).pack(side="left", padx=5)

        # --- Results ---
        result_frame = ttk.LabelFrame(frame, text="Result", padding=12)
        result_frame.pack(fill="x", pady=(0, 12))

        self.bmi_value_var = tk.StringVar(value="--")
        self.bmi_category_var = tk.StringVar(value="Enter your details and press Calculate")

        ttk.Label(result_frame, text="BMI:", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(result_frame, textvariable=self.bmi_value_var,
                  font=("Segoe UI", 18, "bold")).grid(row=0, column=1, sticky="w")

        self.category_label = ttk.Label(result_frame, textvariable=self.bmi_category_var,
                                         font=("Segoe UI", 12))
        self.category_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # Gauge canvas showing where BMI falls across categories
        self.gauge_canvas = tk.Canvas(result_frame, width=620, height=70, highlightthickness=0)
        self.gauge_canvas.grid(row=2, column=0, columnspan=2, pady=(15, 0))
        self._draw_gauge(None)

        # --- Reference table ---
        ref_frame = ttk.LabelFrame(frame, text="BMI Category Reference", padding=10)
        ref_frame.pack(fill="x")

        ref_text = (
            "Underweight: below 18.5     |     Normal weight: 18.5 - 24.9     |     "
            "Overweight: 25.0 - 29.9     |     Obese: 30.0 and above"
        )
        ttk.Label(ref_frame, text=ref_text, wraplength=680, justify="left").pack(anchor="w")

    def _update_unit_labels(self):
        if self.unit_var.get() == "metric":
            self.weight_label_var.set("Weight (kg):")
            self.height_label_var.set("Height (cm):")
        else:
            self.weight_label_var.set("Weight (lb):")
            self.height_label_var.set("Height (in):")

    def _clear_inputs(self):
        self.weight_entry.delete(0, tk.END)
        self.height_entry.delete(0, tk.END)
        self._reset_result_display()

    def _reset_result_display(self):
        self.bmi_value_var.set("--")
        self.bmi_category_var.set("Enter your details and press Calculate")
        self.category_label.configure(foreground="black")
        self._draw_gauge(None)

    def _draw_gauge(self, bmi):
        """Draw a horizontal colored gauge with a marker at the given BMI."""
        c = self.gauge_canvas
        c.delete("all")
        width, height = 620, 70
        bar_top, bar_bottom = 25, 45

        # Scale: 10 to 40 BMI mapped across the bar width
        bmi_min, bmi_max = 10, 40
        # Category boundaries within the visible scale
        bounds = [bmi_min, 18.5, 25.0, 30.0, bmi_max]
        colors = [cat[3] for cat in BMI_CATEGORIES]

        for i in range(len(bounds) - 1):
            x1 = self._scale_to_x(bounds[i], bmi_min, bmi_max, width)
            x2 = self._scale_to_x(bounds[i + 1], bmi_min, bmi_max, width)
            c.create_rectangle(x1, bar_top, x2, bar_bottom, fill=colors[i], outline="")

        # Scale labels
        for value in [10, 18.5, 25, 30, 40]:
            x = self._scale_to_x(value, bmi_min, bmi_max, width)
            c.create_text(x, bar_bottom + 12, text=str(value), font=("Segoe UI", 8))

        # Marker for current BMI
        if bmi is not None:
            clamped = max(bmi_min, min(bmi_max, bmi))
            x = self._scale_to_x(clamped, bmi_min, bmi_max, width)
            c.create_polygon(x - 6, bar_top - 12, x + 6, bar_top - 12, x, bar_top - 2,
                              fill="black")
            c.create_text(x, bar_top - 18, text=f"{bmi:.1f}", font=("Segoe UI", 9, "bold"))

    @staticmethod
    def _scale_to_x(value, vmin, vmax, width, margin=10):
        usable = width - 2 * margin
        ratio = (value - vmin) / (vmax - vmin)
        ratio = max(0.0, min(1.0, ratio))
        return margin + ratio * usable

    # --- Input validation & calculation -------------------------------- #

    def _validate_and_convert(self):
        """Validate entries; return (weight_kg, height_cm) or raise ValueError."""
        weight_raw = self.weight_entry.get().strip()
        height_raw = self.height_entry.get().strip()

        if not weight_raw or not height_raw:
            raise ValueError("Please enter both weight and height.")

        try:
            weight_val = float(weight_raw)
            height_val = float(height_raw)
        except ValueError:
            raise ValueError("Weight and height must be numeric values.")

        if weight_val <= 0 or height_val <= 0:
            raise ValueError("Weight and height must be positive numbers.")

        if self.unit_var.get() == "metric":
            if not (WEIGHT_KG_RANGE[0] <= weight_val <= WEIGHT_KG_RANGE[1]):
                raise ValueError(
                    f"Weight should be between {WEIGHT_KG_RANGE[0]} and {WEIGHT_KG_RANGE[1]} kg.")
            if not (HEIGHT_CM_RANGE[0] <= height_val <= HEIGHT_CM_RANGE[1]):
                raise ValueError(
                    f"Height should be between {HEIGHT_CM_RANGE[0]} and {HEIGHT_CM_RANGE[1]} cm.")
            weight_kg, height_cm = weight_val, height_val
        else:
            if not (WEIGHT_LB_RANGE[0] <= weight_val <= WEIGHT_LB_RANGE[1]):
                raise ValueError(
                    f"Weight should be between {WEIGHT_LB_RANGE[0]} and {WEIGHT_LB_RANGE[1]} lb.")
            if not (HEIGHT_IN_RANGE[0] <= height_val <= HEIGHT_IN_RANGE[1]):
                raise ValueError(
                    f"Height should be between {HEIGHT_IN_RANGE[0]} and {HEIGHT_IN_RANGE[1]} in.")
            weight_kg = weight_val * KG_PER_LB
            height_cm = height_val * CM_PER_IN

        return weight_kg, height_cm

    def calculate(self):
        if self.current_user_id is None:
            messagebox.showwarning("No User Selected",
                                    "Please add or select a user before calculating.")
            return

        try:
            weight_kg, height_cm = self._validate_and_convert()
        except ValueError as exc:
            messagebox.showerror("Invalid Input", str(exc))
            return

        bmi = calculate_bmi(weight_kg, height_cm)
        category, color = categorize_bmi(bmi)

        self.bmi_value_var.set(f"{bmi:.1f}")
        self.bmi_category_var.set(f"Category: {category}")
        self.category_label.configure(foreground=color)
        self._draw_gauge(bmi)

        try:
            self.db.add_record(self.current_user_id, weight_kg, height_cm, bmi, category)
        except RuntimeError as exc:
            messagebox.showerror("Database Error", f"Result calculated, but could not be saved.\n{exc}")
            return

        self.refresh_history()
        self.refresh_trends()

    # ------------------------------------------------------------------ #
    # Tab 2: History
    # ------------------------------------------------------------------ #

    def _build_history_tab(self):
        frame = self.tab_history

        ttk.Label(frame, text="Recorded BMI history for the active user",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))

        columns = ("date", "weight", "height", "bmi", "category")
        self.history_tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)

        headings = {
            "date": ("Date", 140),
            "weight": ("Weight (kg)", 100),
            "height": ("Height (cm)", 100),
            "bmi": ("BMI", 80),
            "category": ("Category", 140),
        }
        for col, (text, width) in headings.items():
            self.history_tree.heading(col, text=text)
            self.history_tree.column(col, width=width, anchor="center")

        self.history_tree.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_history).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self._delete_selected_record).pack(
            side="left", padx=5)

    def refresh_history(self):
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)

        if self.current_user_id is None:
            return

        try:
            records = self.db.get_history(self.current_user_id)
        except RuntimeError as exc:
            messagebox.showerror("Database Error", str(exc))
            return

        for rec_id, rec_date, weight_kg, height_cm, bmi, category in records:
            self.history_tree.insert(
                "", "end", iid=str(rec_id),
                values=(rec_date, f"{weight_kg:.1f}", f"{height_cm:.1f}", f"{bmi:.1f}", category)
            )

    def _delete_selected_record(self):
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a record to delete.")
            return

        if not messagebox.askyesno("Confirm Delete", "Delete the selected record(s)?"):
            return

        try:
            for item_id in selected:
                self.db.delete_record(int(item_id))
        except RuntimeError as exc:
            messagebox.showerror("Database Error", str(exc))

        self.refresh_history()
        self.refresh_trends()

    # ------------------------------------------------------------------ #
    # Tab 3: Trends
    # ------------------------------------------------------------------ #

    def _build_trends_tab(self):
        frame = self.tab_trends

        ttk.Label(frame, text="BMI trend over time", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(0, 8))

        self.stats_var = tk.StringVar(value="No data yet.")
        ttk.Label(frame, textvariable=self.stats_var, justify="left").pack(anchor="w", pady=(0, 10))

        self.fig = Figure(figsize=(6.5, 4.2), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        ttk.Button(frame, text="Refresh Chart", command=self.refresh_trends).pack(pady=8)

    def refresh_trends(self):
        self.ax.clear()

        if self.current_user_id is None:
            self.stats_var.set("No user selected.")
            self.ax.set_title("No data available")
            self.canvas.draw()
            return

        try:
            records = self.db.get_history(self.current_user_id)
        except RuntimeError as exc:
            messagebox.showerror("Database Error", str(exc))
            return

        if not records:
            self.stats_var.set("No records yet for this user. Calculate a BMI to get started!")
            self.ax.set_title("No data available")
            self.ax.set_xlabel("Date")
            self.ax.set_ylabel("BMI")
            self.canvas.draw()
            return

        dates = [rec[1] for rec in records]
        bmis = [rec[4] for rec in records]
        x = list(range(len(bmis)))

        # Shaded background bands for each category
        for label, lower, upper, color in BMI_CATEGORIES:
            self.ax.axhspan(lower, min(upper, 50), color=color, alpha=0.12)

        self.ax.plot(x, bmis, marker="o", color="#34495e", linewidth=2)
        self.ax.set_title("BMI History")
        self.ax.set_xlabel("Record #")
        self.ax.set_ylabel("BMI")
        self.ax.set_xticks(x)
        self.ax.set_xticklabels([d.split(" ")[0] for d in dates], rotation=45, ha="right", fontsize=8)
        self.ax.set_ylim(min(min(bmis) - 2, 15), max(max(bmis) + 2, 35))
        self.fig.tight_layout()
        self.canvas.draw()

        # Stats summary
        avg_bmi = sum(bmis) / len(bmis)
        min_bmi, max_bmi = min(bmis), max(bmis)
        latest_bmi = bmis[-1]
        latest_category, _ = categorize_bmi(latest_bmi)

        if len(bmis) >= 2:
            diff = bmis[-1] - bmis[-2]
            if diff > 0.05:
                trend = f"increased by {diff:.1f} since last record"
            elif diff < -0.05:
                trend = f"decreased by {abs(diff):.1f} since last record"
            else:
                trend = "stable since last record"
        else:
            trend = "not enough data for a trend yet"

        self.stats_var.set(
            f"Records: {len(bmis)}   |   Latest BMI: {latest_bmi:.1f} ({latest_category})   |   "
            f"Average: {avg_bmi:.1f}   |   Min: {min_bmi:.1f}   |   Max: {max_bmi:.1f}   |   "
            f"Trend: {trend}"
        )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    app = BMIApp()
    app.mainloop()