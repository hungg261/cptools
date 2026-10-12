import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from cptools.lib import editor_registry
from cptools.lib import history as lib_history
from cptools.lib.open import open_file, open_folder, reveal_file

from store import (
    load_config, save_config, load_solution, save_solution,
    work_root, fails_dir, clear_fails, testlib_dir, DEFAULT_CONFIG,
)
from loop import StressRunner

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False


if sys.platform == "win32":
    MONO = ("Consolas", 10)
    UI_FONT = "Segoe UI"
elif sys.platform == "darwin":
    MONO = ("Menlo", 11)
    UI_FONT = "Helvetica"
else:
    MONO = ("Monospace", 10)
    UI_FONT = "DejaVu Sans"

UI = (UI_FONT, 10)
UI_BOLD = (UI_FONT, 10, "bold")
UI_SMALL = (UI_FONT, 9)

PAD = 3

BORDER = "#d0d0d0"
BORDER_FOCUS = "#0078d4"
FG_MUTED = "#666666"

OK_FG = "#1f7a1f"
WARN_FG = "#b8860b"
SLOW_FG = "#d2691e"
WA_FG = "#c02020"
TLE_FG = "#c02020"
RTE_FG = "#8e44ad"
SYS_FG = "#2980b9"
LOG_FG = "#666666"

DEFAULT_HOTKEYS = {
    "start":    "F5",
    "stop":     "Shift+F5",
    "open":     "Ctrl+O",
    "settings": "Ctrl+comma",
    "quit":     "Ctrl+Q",
}

HOTKEY_ACTIONS = [
    ("start",    "Start stress"),
    ("stop",     "Stop stress"),
    ("open",     "Open solution"),
    ("settings", "Settings"),
    ("quit",     "Quit"),
]

_KEY_DISPLAY = {
    "comma": ",", "period": ".", "slash": "/", "backslash": "\\",
    "semicolon": ";", "apostrophe": "'", "bracketleft": "[",
    "bracketright": "]", "minus": "-", "equal": "=", "grave": "`",
    "space": "Space", "Return": "Enter", "Escape": "Esc",
    "Tab": "Tab", "BackSpace": "Backspace", "Delete": "Delete",
    "Insert": "Insert", "Home": "Home", "End": "End",
    "Prior": "PageUp", "Next": "PageDown",
    "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right",
}

_DISPLAY_TO_KEY = {
    ",": "comma", ".": "period", "/": "slash", "\\": "backslash",
    ";": "semicolon", "'": "apostrophe", "[": "bracketleft",
    "]": "bracketright", "-": "minus", "=": "equal", "`": "grave",
    "Space": "space", "Enter": "Return", "Esc": "Escape",
}

_MOD_KEYSYM = {
    "Control_L": "Ctrl", "Control_R": "Ctrl",
    "Shift_L": "Shift", "Shift_R": "Shift",
    "Alt_L": "Alt", "Alt_R": "Alt",
    "Super_L": "Super", "Super_R": "Super",
    "Meta_L": "Super", "Meta_R": "Super",
}

_SHIFT_MAP = {
    "exclam": "1", "at": "2", "numbersign": "3", "dollar": "4",
    "percent": "5", "asciicircum": "6", "ampersand": "7",
    "asterisk": "8", "parenleft": "9", "parenright": "0",
    "underscore": "-", "plus": "=", "braceleft": "[",
    "braceright": "]", "bar": "\\", "colon": ";",
    "quotedbl": "'", "less": ",", "greater": ".",
    "question": "/", "asciitilde": "`",
}
_SHIFT_KEY_REVERSE = {v: k for k, v in _SHIFT_MAP.items()}


def _modifier_from_keysym(ks):
    return _MOD_KEYSYM.get(ks)


def _mod_order(mods):
    return [m for m in ("Ctrl", "Shift", "Alt", "Super") if m in mods]


def _key_display_and_shift(ks):
    if ks in _SHIFT_MAP:
        return _SHIFT_MAP[ks], True
    display = _KEY_DISPLAY.get(ks, ks)
    if len(display) == 1 and display.isalpha():
        display = display.upper()
    return display, False


def _parse_hotkey(s):
    if not s or not isinstance(s, str):
        return None
    parts = [p.strip() for p in s.split("+") if p.strip()]
    if not parts:
        return None
    mods = []
    key = parts[-1]
    for m in parts[:-1]:
        ml = m.lower()
        if ml in ("ctrl", "control"):
            mods.append("Control")
        elif ml == "shift":
            mods.append("Shift")
        elif ml == "alt":
            mods.append("Alt")
        elif ml in ("super", "cmd", "win", "meta"):
            mods.append("Super")
        else:
            return None
    key = _DISPLAY_TO_KEY.get(key, key)
    if "Shift" in mods and key in _SHIFT_KEY_REVERSE:
        key = _SHIFT_KEY_REVERSE[key]
        mods = [m for m in mods if m != "Shift"]
    if len(key) == 1 and key.isalpha():
        key = key.lower()
    tk_binding = "-".join(mods + [key])
    return f"<{tk_binding}>"


def _sanitize_flags_str(raw):
    """Return a clean space-separated string."""
    if raw is None:
        return ""
    if isinstance(raw, (list, tuple)):
        parts = []
        for item in raw:
            s = str(item)
            for ch in "[]'\",":
                s = s.replace(ch, " ")
            parts.append(s)
        raw = " ".join(parts)
    s = str(raw)
    for ch in "[]'\"":
        s = s.replace(ch, " ")
    return " ".join(s.split())


def _load_full_cfg():
    cfg = load_config()
    hk = dict(DEFAULT_HOTKEYS)
    user_hk = cfg.get("hotkeys") or {}
    if isinstance(user_hk, dict):
        for k, v in user_hk.items():
            if k in DEFAULT_HOTKEYS and isinstance(v, str):
                hk[k] = v
    cfg["hotkeys"] = hk
    return cfg


def _save_full_cfg(cfg):
    save_config(cfg)


# ---------------------------------------------------------------- CaptureDialog

class CaptureDialog(tk.Toplevel):
    def __init__(self, parent, action_label, current_display):
        super().__init__(parent)
        self.result = None
        self._current = current_display or ""
        self._mods = set()

        self.title(f"Rebind: {action_label}")
        self.geometry("380x170")
        self.transient(parent)
        self.resizable(False, False)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=action_label, font=UI_BOLD).pack(anchor="w")
        ttk.Label(
            frame, text="Press a new key combination\u2026",
            font=UI_SMALL, foreground=FG_MUTED,
        ).pack(anchor="w", pady=(2, 8))

        info = ttk.Frame(frame)
        info.pack(fill="x", pady=(0, 8))
        info.columnconfigure(1, weight=1)
        ttk.Label(info, text="Current:", font=UI).grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Label(info, text=current_display or "(none)", font=UI).grid(row=0, column=1, sticky="w")
        ttk.Label(info, text="New:", font=UI).grid(row=1, column=0, sticky="w", padx=(0, 6))
        self.new_var = tk.StringVar(value="waiting\u2026")
        ttk.Label(info, textvariable=self.new_var, font=UI_BOLD).grid(row=1, column=1, sticky="w")

        btns = ttk.Frame(frame)
        btns.pack(fill="x", side="bottom")
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="right")
        self.confirm_btn = ttk.Button(btns, text="Confirm", command=self._confirm)
        self.confirm_btn.pack(side="right", padx=(0, 4))
        self.confirm_btn.configure(state="disabled")

        self.bind("<KeyPress>", self._on_press)
        self.bind("<KeyRelease>", self._on_release)
        self.after(50, self._focus)
        self.grab_set()

    def _focus(self):
        try:
            self.focus_force()
        except Exception:
            pass

    def _on_press(self, event):
        ks = event.keysym
        if ks == "Escape":
            self._cancel()
            return "break"
        if ks == "Return":
            if self._current:
                self._confirm()
            return "break"
        mod = _modifier_from_keysym(ks)
        if mod:
            self._mods.add(mod)
            self._update_display()
            return "break"
        display_key, force_shift = _key_display_and_shift(ks)
        if not display_key:
            return "break"
        mods = set(self._mods)
        if force_shift:
            mods.add("Shift")
        parts = _mod_order(mods) + [display_key]
        self._current = "+".join(parts)
        self.new_var.set(self._current)
        self.confirm_btn.configure(state="normal")
        return "break"

    def _on_release(self, event):
        mod = _modifier_from_keysym(event.keysym)
        if mod:
            self._mods.discard(mod)
        return "break"

    def _update_display(self):
        if self._mods:
            self.new_var.set("+".join(_mod_order(self._mods)) + "+\u2026")
        else:
            self.new_var.set("waiting\u2026")

    def _confirm(self):
        self.result = self._current
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# ---------------------------------------------------------------- ErrorDialog

class ErrorDialog(tk.Toplevel):
    def __init__(self, parent, title, body, app=None):
        super().__init__(parent)
        self.app = app
        self.title(title)
        self.geometry("640x420")
        self.transient(parent)

        frame = ttk.Frame(self, padding=6)
        frame.pack(fill="both", expand=True)

        txt = ScrolledText(frame, wrap="word", font=MONO)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", body)
        txt.configure(state="disabled")

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(
            btns, text="Copy",
            command=lambda: self._copy(txt.get("1.0", "end-1c")),
        ).pack(side="right", padx=(0, 4))

    def _copy(self, content):
        self.clipboard_clear()
        self.clipboard_append(content)
        if self.app:
            self.app.set_status("copied")


# ---------------------------------------------------------------- SettingsDialog

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Settings")
        self.geometry("520x580")
        self.transient(parent)
        self.minsize(460, 500)

        self.gcfg = dict(app.gcfg)
        self._hotkeys = dict(app.gcfg.get("hotkeys") or DEFAULT_HOTKEYS)

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        btns = ttk.Frame(outer)
        btns.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(btns, text="Reset", command=self._reset).pack(side="left")
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=(0, 4))

        t1 = ttk.LabelFrame(outer, text=" Timing ", padding=(8, 6))
        t1.pack(fill="x", pady=(0, 6))

        self.vars = {}

        def row(parent, label, key, width=12):
            f = ttk.Frame(parent)
            f.pack(fill="x", pady=1)
            ttk.Label(f, text=label, width=18, anchor="w").pack(side="left")
            raw = self.gcfg.get(key, DEFAULT_CONFIG.get(key, ""))
            if key == "compiler_flags":
                raw = _sanitize_flags_str(raw)
            elif isinstance(raw, (list, tuple)):
                raw = " ".join(str(x) for x in raw)
            v = tk.StringVar(value=str(raw))
            ttk.Entry(f, textvariable=v, width=width).pack(side="left")
            self.vars[key] = v

        row(t1, "Time limit (s)", "time_limit")
        row(t1, "Warn factor", "warn_factor")
        row(t1, "Slow factor", "slow_factor")
        row(t1, "Fail factor", "fail_factor")
        row(t1, "Gen timeout (s)", "gen_timeout")

        t2 = ttk.LabelFrame(outer, text=" Compiler ", padding=(8, 6))
        t2.pack(fill="x", pady=(0, 6))
        row(t2, "Executable", "compiler")
        row(t2, "Flags", "compiler_flags", width=30)
        row(t2, "Compile timeout (s)", "compile_timeout")

        t3 = ttk.LabelFrame(outer, text=" Defaults ", padding=(8, 6))
        t3.pack(fill="x", pady=(0, 6))

        f = ttk.Frame(t3)
        f.pack(fill="x", pady=1)
        ttk.Label(f, text="Match mode", width=18, anchor="w").pack(side="left")
        self.match_var = tk.StringVar(value=self.gcfg.get("match_mode", "token"))
        ttk.Combobox(
            f, textvariable=self.match_var,
            values=["token", "exact", "whitespace"],
            width=12, state="readonly",
        ).pack(side="left")

        row(t3, "Max fails", "max_fails")
        f = ttk.Frame(t3)
        f.pack(fill="x", pady=1)
        ttk.Label(f, text="Stop on first fail", width=18, anchor="w").pack(side="left")
        self.stop_var = tk.BooleanVar(value=bool(self.gcfg.get("stop_on_fail", True)))
        ttk.Checkbutton(f, variable=self.stop_var).pack(side="left")

        t4 = ttk.LabelFrame(outer, text=" Hotkeys ", padding=(8, 6))
        t4.pack(fill="both", expand=True, pady=(0, 6))

        hk_frame = ttk.Frame(t4)
        hk_frame.pack(fill="both", expand=True)
        self.hk_tree = ttk.Treeview(
            hk_frame, columns=("action", "binding"),
            show="headings", selectmode="browse", height=4,
        )
        self.hk_tree.heading("action", text="Action")
        self.hk_tree.heading("binding", text="Binding")
        self.hk_tree.column("action", width=200, anchor="w")
        self.hk_tree.column("binding", width=180, anchor="w")
        self.hk_tree.pack(fill="both", expand=True)
        self.hk_tree.bind("<Double-1>", lambda e: self._edit_hotkey())
        ttk.Label(
            t4, text="Double-click a row to rebind",
            font=UI_SMALL, foreground=FG_MUTED,
        ).pack(anchor="w", pady=(2, 0))
        self._populate_hotkeys()

    def _populate_hotkeys(self):
        self.hk_tree.delete(*self.hk_tree.get_children())
        for key, label in HOTKEY_ACTIONS:
            display = self._hotkeys.get(key, "")
            self.hk_tree.insert("", "end", iid=key, values=(label, display or "(none)"))

    def _edit_hotkey(self):
        sel = self.hk_tree.selection()
        if not sel:
            return
        key = sel[0]
        label = dict(HOTKEY_ACTIONS).get(key, key)
        current = self._hotkeys.get(key, "")
        dlg = CaptureDialog(self, label, current)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        new_binding = dlg.result
        if new_binding:
            for k, lbl in HOTKEY_ACTIONS:
                if k != key and self._hotkeys.get(k) == new_binding:
                    if not messagebox.askyesno(
                        "Hotkey conflict",
                        f"'{new_binding}' is already bound to '{lbl}'.\nReplace it?",
                        parent=self,
                    ):
                        return
                    self._hotkeys[k] = ""
        self._hotkeys[key] = new_binding
        self._populate_hotkeys()

    def _reset(self):
        if not messagebox.askyesno("Reset", "Reset settings to defaults?", parent=self):
            return
        for key, v in self.vars.items():
            raw = DEFAULT_CONFIG.get(key, "")
            if key == "compiler_flags":
                raw = _sanitize_flags_str(raw)
            elif isinstance(raw, (list, tuple)):
                raw = " ".join(str(x) for x in raw)
            v.set(str(raw))
        self.match_var.set(DEFAULT_CONFIG["match_mode"])
        self.stop_var.set(DEFAULT_CONFIG["stop_on_fail"])
        self._hotkeys = dict(DEFAULT_HOTKEYS)
        self._populate_hotkeys()

    def _save(self):
        for key, v in self.vars.items():
            val = v.get().strip()
            if key in ("time_limit", "warn_factor", "slow_factor",
                       "fail_factor", "gen_timeout"):
                try:
                    self.gcfg[key] = float(val)
                except ValueError:
                    messagebox.showerror("Invalid", f"{key} must be a number", parent=self)
                    return
            elif key in ("max_fails", "compile_timeout"):
                try:
                    self.gcfg[key] = int(val)
                except ValueError:
                    messagebox.showerror("Invalid", f"{key} must be int", parent=self)
                    return
            elif key == "compiler_flags":
                s = _sanitize_flags_str(val)
                self.gcfg[key] = s.split() if s else []
            else:
                self.gcfg[key] = val
        self.gcfg["match_mode"] = self.match_var.get()
        self.gcfg["stop_on_fail"] = self.stop_var.get()
        self.gcfg["hotkeys"] = dict(self._hotkeys)

        self.app.gcfg = dict(self.gcfg)
        _save_full_cfg(self.app.gcfg)
        self.app._apply_hotkeys()
        self.app.set_status("settings saved")
        self.destroy()


# ---------------------------------------------------------------- FailViewDialog

class FailViewDialog(tk.Toplevel):
    def __init__(self, parent, fail_info, source, app):
        super().__init__(parent)
        self.title(f"Fail #{fail_info.get('index', '?')}  seed={fail_info.get('seed','?')}  {fail_info.get('status','?')}")
        self.geometry("900x600")
        self.transient(parent)
        self.fail_info = fail_info
        self.source = source
        self.app = app

        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(1, weight=1)

        status = fail_info.get("status", "?")
        elapsed = fail_info.get("elapsed", 0)
        ttk.Label(
            outer,
            text=f"Status: {status}    Time: {elapsed:.3f}s",
            font=UI_BOLD,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        left = ttk.LabelFrame(outer, text=" Input ")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.input_txt = ScrolledText(left, wrap="none", font=MONO)
        self.input_txt.pack(fill="both", expand=True)

        right = ttk.Frame(outer)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        exp_frame = ttk.LabelFrame(right, text=" Expected ")
        exp_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        exp_frame.columnconfigure(0, weight=1)
        exp_frame.rowconfigure(0, weight=1)
        self.expected_txt = ScrolledText(exp_frame, wrap="none", font=MONO)
        self.expected_txt.pack(fill="both", expand=True)

        got_frame = ttk.LabelFrame(right, text=" Got ")
        got_frame.grid(row=1, column=0, sticky="nsew")
        got_frame.columnconfigure(0, weight=1)
        got_frame.rowconfigure(0, weight=1)
        self.got_txt = ScrolledText(got_frame, wrap="none", font=MONO)
        self.got_txt.pack(fill="both", expand=True)

        btns = ttk.Frame(outer)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(
            btns, text="Add to runner tests",
            command=self._add_to_runner,
        ).pack(side="right", padx=(0, 4))
        ttk.Button(btns, text="Copy input", command=self._copy_input).pack(side="left")
        ttk.Button(btns, text="Copy expected", command=self._copy_expected).pack(side="left", padx=(4, 0))

        self._load()

    def _load(self):
        d = Path(self.fail_info.get("dir", ""))
        if not d.is_dir():
            self.input_txt.insert("1.0", "<fail directory not found>")
            return
        for name, widget in (
            ("input.txt", self.input_txt),
            ("expected.txt", self.expected_txt),
            ("got.txt", self.got_txt),
        ):
            p = d / name
            if p.is_file():
                try:
                    widget.insert("1.0", p.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    pass
        log = d / "interaction_log.txt"
        if log.is_file():
            self.expected_txt.delete("1.0", "end")
            self.expected_txt.insert("1.0", "[interaction log]\n")
            self.expected_txt.insert("end", log.read_text(encoding="utf-8", errors="replace"))
        err = d / "stderr.txt"
        if err.is_file():
            self.got_txt.insert("end", "\n[stderr]\n")
            self.got_txt.insert("end", err.read_text(encoding="utf-8", errors="replace"))

    def _copy_input(self):
        self.clipboard_clear()
        self.clipboard_append(self.input_txt.get("1.0", "end-1c"))
        self.app.set_status("copied input")

    def _copy_expected(self):
        self.clipboard_clear()
        self.clipboard_append(self.expected_txt.get("1.0", "end-1c"))
        self.app.set_status("copied expected")

    def _add_to_runner(self):
        d = Path(self.fail_info.get("dir", ""))
        inp = d / "input.txt"
        exp = d / "expected.txt"
        if not inp.is_file() or not exp.is_file():
            messagebox.showerror("Error", "input or expected file missing", parent=self)
            return
        import subprocess
        try:
            r = subprocess.run(
                ["cpt", "run", "test", "add", str(self.source), str(inp), str(exp)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                self.app.set_status("added to runner tests")
            else:
                messagebox.showerror("Error", r.stderr or r.stdout, parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)


# ---------------------------------------------------------------- StressApp

class StressApp:
    def __init__(self, root, initial_source=None):
        self.root = root
        self.gcfg = _load_full_cfg()
        self.scfg = None
        self.source = None
        self.fails = []
        self.busy = False
        self.queue = queue.Queue()
        self.runner = None
        self.cancel_event = threading.Event()
        self._bound = {}
        self._start_time = 0.0
        self._iter = 0

        self.root.title("Stress Test")
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            w = min(660, int(sw * 0.9))
            h = min(660, int(sh * 0.8))
            x = max(20, (sw - w) // 2)
            y = max(20, (sh - h) // 8)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.root.geometry("660x660")
        self.root.minsize(520, 500)

        self._setup_style()
        self._build_menubar()
        self._build_ui()
        self._setup_dnd()
        self._apply_hotkeys()

        if initial_source and Path(initial_source).is_file():
            self.load_solution(Path(initial_source))
        else:
            self._set_no_solution()

        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.after(40, self._poll_queue)

    def _setup_style(self):
        style = ttk.Style()
        try:
            if sys.platform == "win32":
                style.theme_use("vista")
            elif sys.platform == "darwin":
                style.theme_use("aqua")
            else:
                style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", font=UI, padding=(4, 3))
        style.configure("TEntry", font=UI, padding=3)
        style.configure("TLabel", font=UI)
        style.configure("TLabelframe", font=UI)
        style.configure("TLabelframe.Label", font=UI_SMALL, foreground=FG_MUTED)
        style.configure("TNotebook", padding=0)
        style.configure("TNotebook.Tab", font=UI, padding=(10, 5))
        style.configure("Treeview", font=UI, rowheight=21)
        style.configure("Treeview.Heading", font=(UI_FONT, 9))
        style.configure("Status.TLabel", font=UI_SMALL, padding=(4, 2),
                        foreground=FG_MUTED)

    # ------------------------------------------------------ menu

    def _build_menubar(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Open solution\u2026", accelerator="Ctrl+O",
            command=self._browse_solution,
        )
        file_menu.add_separator()
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Recent solutions", menu=self.recent_menu)
        self._rebuild_recent_menu()
        file_menu.add_separator()
        file_menu.add_command(
            label="Settings\u2026", accelerator="Ctrl+,",
            command=self._open_settings,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit", accelerator="Ctrl+Q", command=self._quit,
        )
        menubar.add_cascade(label="File", menu=file_menu, underline=-1)

        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(
            label="Start", accelerator="F5", command=self._start_stress,
        )
        run_menu.add_command(
            label="Stop", accelerator="Shift+F5", command=self._stop_stress,
        )
        menubar.add_cascade(label="Run", menu=run_menu, underline=-1)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(
            label="Log", command=lambda: self._bottom_select("log"),
        )
        view_menu.add_command(
            label="Failures", command=lambda: self._bottom_select("fails"),
        )
        view_menu.add_command(
            label="Preview", command=lambda: self._bottom_select("preview"),
        )
        menubar.add_cascade(label="View", menu=view_menu, underline=-1)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(
            label="Download testlib.h\u2026",
            command=self._download_testlib,
        )
        tools_menu.add_command(
            label="Open testlib folder",
            command=self._open_testlib_folder,
        )
        menubar.add_cascade(label="Tools", menu=tools_menu, underline=-1)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu, underline=-1)

        self.root.config(menu=menubar)
        self._menubar = menubar

    def _rebuild_recent_menu(self):
        self.recent_menu.delete(0, "end")
        items = lib_history.load()
        if not items:
            self.recent_menu.add_command(label="(no recent files)", state="disabled")
            return
        for it in items:
            path = it.get("path", "")
            exists = Path(path).exists()
            label = Path(path).name or path
            if not exists:
                label += "  (missing)"
            self.recent_menu.add_command(
                label=label,
                state="normal" if exists else "disabled",
                command=(lambda p=path: self._open_recent(p)) if exists else None,
            )
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="Clear recent", command=self._clear_recent)

    def _clear_recent(self):
        if not messagebox.askyesno("Clear", "Clear recent solutions?", parent=self.root):
            return
        lib_history.clear()
        self._rebuild_recent_menu()

    def _open_recent(self, path):
        if not Path(path).is_file():
            messagebox.showerror("Open", f"File not found:\n{path}", parent=self.root)
            self._rebuild_recent_menu()
            return
        self.load_solution(Path(path))

    def _show_about(self):
        messagebox.showinfo(
            "About Stress Test",
            "Stress Test\n\nAuto stress-test competitive programming solutions.\nPart of cptools.",
            parent=self.root,
        )

    # ------------------------------------------------------ ui

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=0)
        self.root.rowconfigure(4, weight=1)

        top = ttk.Frame(self.root, padding=(6, 6, 6, 0))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Solution", width=10).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.sol_var = tk.StringVar()
        self.sol_entry = ttk.Entry(top, textvariable=self.sol_var)
        self.sol_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(top, text="\u2026", width=2, command=self._browse_solution).grid(row=0, column=2)
        ttk.Button(top, text="\u25be", width=2, command=lambda: self._path_menu(self.sol_var, "solution")).grid(row=0, column=3, padx=(2, 0))

        ttk.Label(top, text="Generator", width=10).grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.gen_var = tk.StringVar()
        self.gen_entry = ttk.Entry(top, textvariable=self.gen_var)
        self.gen_entry.grid(row=1, column=1, sticky="ew", padx=(0, 4), pady=(4, 0))
        ttk.Button(top, text="\u2026", width=2, command=self._browse_generator).grid(row=1, column=2, pady=(4, 0))
        ttk.Button(top, text="\u25be", width=2, command=lambda: self._path_menu(self.gen_var, "generator")).grid(row=1, column=3, padx=(2, 0), pady=(4, 0))

        mode_wrap = ttk.Frame(self.root, padding=(6, 6, 6, 0))
        mode_wrap.grid(row=1, column=0, sticky="ew")
        mode_wrap.columnconfigure(0, weight=1)

        self.mode_nb = ttk.Notebook(mode_wrap)
        self.mode_nb.grid(row=0, column=0, sticky="ew")
        self.mode_nb.bind("<<NotebookTabChanged>>", self._on_mode_change)

        self._build_std_tab()
        self._build_checker_tab()
        self._build_interactive_tab()

        opts = ttk.Frame(self.root, padding=(6, 6, 6, 0))
        opts.grid(row=2, column=0, sticky="ew")
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="Seed", width=10).grid(row=0, column=0, sticky="w")
        seed_frame = ttk.Frame(opts)
        seed_frame.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        seed_frame.columnconfigure(0, weight=1)
        self.seed_var = tk.StringVar(value="0")
        ttk.Entry(seed_frame, textvariable=self.seed_var, width=10).grid(row=0, column=0, sticky="ew")
        ttk.Button(seed_frame, text="\U0001F3B2", width=3, command=self._randomize_seed).grid(row=0, column=1, padx=(2, 0))

        self.randomize_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts, text="Randomize per iteration", variable=self.randomize_var,
        ).grid(row=0, column=2, columnspan=2, sticky="w", padx=(8, 0))

        ttk.Label(opts, text="Gen args", width=10).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.gen_args_var = tk.StringVar()
        ttk.Entry(opts, textvariable=self.gen_args_var).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=(0, 4), pady=(4, 0),
        )

        row2 = ttk.Frame(opts)
        row2.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Label(row2, text="Max fails", width=10).pack(side="left")
        self.max_fails_var = tk.StringVar(value=str(self.gcfg.get("max_fails", 50)))
        ttk.Entry(row2, textvariable=self.max_fails_var, width=6).pack(side="left")

        self.stop_var = tk.BooleanVar(value=bool(self.gcfg.get("stop_on_fail", True)))
        ttk.Checkbutton(
            row2, text="Stop on first fail", variable=self.stop_var,
        ).pack(side="left", padx=(12, 0))

        self.no_compile_var = tk.BooleanVar(
            value=bool(self.gcfg.get("no_compile", False))
        )
        ttk.Checkbutton(
            row2, text="Skip compile", variable=self.no_compile_var,
        ).pack(side="left", padx=(12, 0))

        action = ttk.Frame(self.root, padding=(6, 6, 6, 0))
        action.grid(row=3, column=0, sticky="ew")
        action.columnconfigure(2, weight=1)

        self.btn_start = ttk.Button(action, text="\u25b6 Start", width=10, command=self._start_stress)
        self.btn_start.grid(row=0, column=0, padx=(0, 4))

        self.btn_stop = ttk.Button(action, text="\u25a0 Stop", width=10, command=self._stop_stress, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=(0, 4))

        self.progress_var = tk.StringVar(value="ready")
        ttk.Label(action, textvariable=self.progress_var, font=UI_SMALL).grid(row=0, column=2, sticky="w")

        bottom = ttk.Frame(self.root, padding=(6, 6, 6, 6))
        bottom.grid(row=4, column=0, sticky="nsew")
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=1)

        self.bottom_nb = ttk.Notebook(bottom)
        self.bottom_nb.grid(row=0, column=0, sticky="nsew")

        log_frame = ttk.Frame(self.bottom_nb)
        self.bottom_nb.add(log_frame, text="Log")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = ScrolledText(
            log_frame, wrap="none", font=MONO, state="disabled", height=5,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.tag_configure("OK", foreground=OK_FG)
        self.log_text.tag_configure("WARN", foreground=WARN_FG)
        self.log_text.tag_configure("SLOW", foreground=SLOW_FG)
        self.log_text.tag_configure("WA", foreground=WA_FG)
        self.log_text.tag_configure("TLE", foreground=TLE_FG)
        self.log_text.tag_configure("RTE", foreground=RTE_FG)
        self.log_text.tag_configure("SYS", foreground=SYS_FG)
        self.log_text.tag_configure("LOG", foreground=LOG_FG)

        fails_frame = ttk.Frame(self.bottom_nb)
        self.bottom_nb.add(fails_frame, text="Failures")
        fails_frame.columnconfigure(0, weight=1)
        fails_frame.rowconfigure(2, weight=1)

        self.fails_tree = ttk.Treeview(
            fails_frame, columns=("id", "seed", "status", "time"),
            show="headings", selectmode="browse", height=4,
        )
        self.fails_tree.heading("id", text="#")
        self.fails_tree.heading("seed", text="Seed")
        self.fails_tree.heading("status", text="Status")
        self.fails_tree.heading("time", text="Time")
        self.fails_tree.column("id", width=40, anchor="center")
        self.fails_tree.column("seed", width=120, anchor="w")
        self.fails_tree.column("status", width=80, anchor="w")
        self.fails_tree.column("time", width=100, anchor="e")
        self.fails_tree.grid(row=0, column=0, sticky="ew")
        self.fails_tree.tag_configure("WA", foreground=WA_FG)
        self.fails_tree.tag_configure("TLE", foreground=TLE_FG)
        self.fails_tree.tag_configure("RTE", foreground=RTE_FG)
        self.fails_tree.bind("<<TreeviewSelect>>", lambda e: self._update_fail_preview())
        self.fails_tree.bind("<Double-1>", lambda e: self._view_selected_fail())

        fbar = ttk.Frame(fails_frame)
        fbar.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        ttk.Button(fbar, text="View", command=self._view_selected_fail).pack(side="left")
        ttk.Button(fbar, text="Add to runner", command=self._add_selected_to_runner).pack(side="left", padx=(4, 0))
        ttk.Button(fbar, text="Add all to runner", command=self._add_all_fails_to_runner).pack(side="left", padx=(4, 0))
        ttk.Button(fbar, text="Open folder", command=self._open_fails_folder).pack(side="left", padx=(4, 0))
        ttk.Button(fbar, text="Clear", command=self._clear_fails).pack(side="right")

        self.fail_preview_nb = ttk.Notebook(fails_frame)
        self.fail_preview_nb.grid(row=2, column=0, sticky="nsew", pady=(2, 0))

        self.fail_preview_widgets = {}
        for label in ("Input", "Expected", "Got"):
            t = ScrolledText(self.fail_preview_nb, wrap="none", font=MONO, height=4)
            t.configure(state="disabled")
            self.fail_preview_nb.add(t, text=label)
            self.fail_preview_widgets[label.lower()] = t

        prev_frame = ttk.Frame(self.bottom_nb)
        self.bottom_nb.add(prev_frame, text="Preview")
        prev_frame.columnconfigure(0, weight=1)
        prev_frame.rowconfigure(1, weight=1)

        pbar = ttk.Frame(prev_frame)
        pbar.grid(row=0, column=0, sticky="ew")
        self.preview_var = tk.StringVar()
        self.preview_combo = ttk.Combobox(
            pbar, textvariable=self.preview_var,
            values=[], state="readonly", width=40,
        )
        self.preview_combo.pack(side="left")
        self.preview_combo.bind("<<ComboboxSelected>>", lambda e: self._reload_preview())
        ttk.Button(pbar, text="Reload", width=8, command=self._reload_preview).pack(side="left", padx=(4, 0))
        ttk.Button(pbar, text="Open with \u25be", command=self._preview_open_menu).pack(side="right")

        self.preview_text = ScrolledText(prev_frame, wrap="none", font=MONO, state="disabled", height=5)
        self.preview_text.grid(row=1, column=0, sticky="nsew", pady=(2, 0))

        self.status_var = tk.StringVar(value="ready")
        status = ttk.Label(
            self.root, textvariable=self.status_var,
            style="Status.TLabel", anchor="w",
        )
        status.grid(row=5, column=0, sticky="ew")

    def _build_std_tab(self):
        f = ttk.Frame(self.mode_nb, padding=6)
        self.mode_nb.add(f, text="Standard")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Brute", width=10).grid(row=0, column=0, sticky="w")
        self.std_brute_var = tk.StringVar()
        self.std_brute_entry = ttk.Entry(f, textvariable=self.std_brute_var)
        self.std_brute_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(f, text="\u2026", width=2, command=lambda: self._browse_into(self.std_brute_var, "brute")).grid(row=0, column=2)
        ttk.Button(f, text="\u25be", width=2, command=lambda: self._path_menu(self.std_brute_var, "brute")).grid(row=0, column=3, padx=(2, 0))

        ttk.Label(f, text="Match", width=10).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.match_var = tk.StringVar(value="token")
        mf = ttk.Frame(f)
        mf.grid(row=1, column=1, columnspan=3, sticky="w", pady=(4, 0))
        for val in ("token", "exact", "whitespace"):
            ttk.Radiobutton(mf, text=val, value=val, variable=self.match_var).pack(side="left", padx=(0, 8))

    def _build_checker_tab(self):
        f = ttk.Frame(self.mode_nb, padding=6)
        self.mode_nb.add(f, text="Checker")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Brute", width=10).grid(row=0, column=0, sticky="w")
        self.ck_brute_var = tk.StringVar()
        self.ck_brute_entry = ttk.Entry(f, textvariable=self.ck_brute_var)
        self.ck_brute_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(f, text="\u2026", width=2, command=lambda: self._browse_into(self.ck_brute_var, "brute")).grid(row=0, column=2)
        ttk.Button(f, text="\u25be", width=2, command=lambda: self._path_menu(self.ck_brute_var, "brute")).grid(row=0, column=3, padx=(2, 0))

        ttk.Label(f, text="Checker", width=10).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.ck_checker_var = tk.StringVar()
        self.ck_checker_entry = ttk.Entry(f, textvariable=self.ck_checker_var)
        self.ck_checker_entry.grid(row=1, column=1, sticky="ew", padx=(0, 4), pady=(4, 0))
        ttk.Button(f, text="\u2026", width=2, command=lambda: self._browse_into(self.ck_checker_var, "checker")).grid(row=1, column=2, pady=(4, 0))
        ttk.Button(f, text="\u25be", width=2, command=lambda: self._path_menu(self.ck_checker_var, "checker")).grid(row=1, column=3, padx=(2, 0), pady=(4, 0))

    def _build_interactive_tab(self):
        f = ttk.Frame(self.mode_nb, padding=6)
        self.mode_nb.add(f, text="Interactive")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Interactor", width=10).grid(row=0, column=0, sticky="w")
        self.int_var = tk.StringVar()
        self.int_entry = ttk.Entry(f, textvariable=self.int_var)
        self.int_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        ttk.Button(f, text="\u2026", width=2, command=lambda: self._browse_into(self.int_var, "interactor")).grid(row=0, column=2)
        ttk.Button(f, text="\u25be", width=2, command=lambda: self._path_menu(self.int_var, "interactor")).grid(row=0, column=3, padx=(2, 0))

    # ------------------------------------------------------ drag & drop

    def _setup_dnd(self):
        if not HAS_DND:
            return
        pairs = [
            (self.sol_entry, self._drop_solution),
            (self.gen_entry, self._drop_generator),
            (self.std_brute_entry, self._drop_std_brute),
            (self.ck_brute_entry, self._drop_ck_brute),
            (self.ck_checker_entry, self._drop_ck_checker),
            (self.int_entry, self._drop_int),
        ]
        for widget, cb in pairs:
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", cb)
            except Exception:
                pass

    def _parse_drop(self, data):
        try:
            return self.root.tk.splitlist(data)
        except Exception:
            return [data.strip("{}")]

    def _drop_solution(self, event):
        paths = self._parse_drop(event.data)
        if paths:
            self.load_solution(Path(paths[0]))
        return "break"

    def _drop_generator(self, event):
        paths = self._parse_drop(event.data)
        if paths:
            self.gen_var.set(paths[0])
            self._save_solution_now()
            self._refresh_preview_dropdown()
        return "break"

    def _drop_std_brute(self, event):
        paths = self._parse_drop(event.data)
        if paths:
            self.std_brute_var.set(paths[0])
            self._save_solution_now()
            self._refresh_preview_dropdown()
        return "break"

    def _drop_ck_brute(self, event):
        paths = self._parse_drop(event.data)
        if paths:
            self.ck_brute_var.set(paths[0])
            self._save_solution_now()
            self._refresh_preview_dropdown()
        return "break"

    def _drop_ck_checker(self, event):
        paths = self._parse_drop(event.data)
        if paths:
            self.ck_checker_var.set(paths[0])
            self._save_solution_now()
            self._refresh_preview_dropdown()
        return "break"

    def _drop_int(self, event):
        paths = self._parse_drop(event.data)
        if paths:
            self.int_var.set(paths[0])
            self._save_solution_now()
            self._refresh_preview_dropdown()
        return "break"

    # ------------------------------------------------------ solution load/save

    def _set_no_solution(self):
        self.source = None
        self.scfg = None
        self.sol_var.set("")
        self.gen_var.set("")
        self._refresh_preview_dropdown()
        self._set_running(False)

    def load_solution(self, path):
        p = Path(path).resolve()
        self.source = p
        self.scfg = load_solution(p)
        self.sol_var.set(str(p))
        self.gen_var.set(self.scfg.get("generator", ""))
        self.std_brute_var.set(self.scfg["standard"].get("extra", ""))
        self.match_var.set(self.scfg["standard"].get("match_mode", "token"))
        self.ck_brute_var.set(self.scfg["checker"].get("extra", ""))
        self.ck_checker_var.set(self.scfg["checker"].get("checker", ""))
        self.int_var.set(self.scfg["interactive"].get("extra", ""))
        self.seed_var.set(str(self.scfg.get("seed", 0)))
        self.randomize_var.set(bool(self.scfg.get("randomize_per_iter", False)))
        self.gen_args_var.set(self.scfg.get("gen_args", ""))

        mode = self.scfg.get("mode", "standard")
        idx = {"standard": 0, "checker": 1, "interactive": 2}.get(mode, 0)
        self.mode_nb.select(idx)

        self.fails = []
        self.fails_tree.delete(*self.fails_tree.get_children())
        for w in self.fail_preview_widgets.values():
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")
        self._refresh_preview_dropdown()
        self._reload_preview()
        self._rebuild_recent_menu()
        lib_history.add(p)

        self.set_status(f"loaded {p.name}")

    def _save_solution_now(self):
        if not self.source or not self.scfg:
            return
        self.scfg["generator"] = self.gen_var.get().strip()
        self.scfg["standard"]["extra"] = self.std_brute_var.get().strip()
        self.scfg["standard"]["match_mode"] = self.match_var.get()
        self.scfg["checker"]["extra"] = self.ck_brute_var.get().strip()
        self.scfg["checker"]["checker"] = self.ck_checker_var.get().strip()
        self.scfg["interactive"]["extra"] = self.int_var.get().strip()
        try:
            self.scfg["seed"] = int(self.seed_var.get())
        except ValueError:
            self.scfg["seed"] = 0
        self.scfg["randomize_per_iter"] = self.randomize_var.get()
        self.scfg["gen_args"] = self.gen_args_var.get().strip()
        save_solution(self.scfg)

    def _on_mode_change(self, event=None):
        if not self.scfg:
            return
        idx = self.mode_nb.index(self.mode_nb.select())
        self.scfg["mode"] = ["standard", "checker", "interactive"][idx]
        self._save_solution_now()

    # ------------------------------------------------------ browsing

    def _browse_solution(self):
        p = filedialog.askopenfilename(
            parent=self.root, title="Select solution",
            filetypes=[("C/C++", "*.cpp *.cc *.cxx *.c"), ("All files", "*.*")],
        )
        if p:
            self.load_solution(Path(p))

    def _browse_generator(self):
        p = filedialog.askopenfilename(
            parent=self.root, title="Select generator",
            filetypes=[("C/C++", "*.cpp *.cc *.cxx *.c"), ("All files", "*.*")],
        )
        if p:
            self.gen_var.set(p)
            self._save_solution_now()
            self._refresh_preview_dropdown()

    def _browse_into(self, var, kind):
        p = filedialog.askopenfilename(
            parent=self.root, title=f"Select {kind}",
            filetypes=[("C/C++", "*.cpp *.cc *.cxx *.c"), ("All files", "*.*")],
        )
        if p:
            var.set(p)
            self._save_solution_now()
            self._refresh_preview_dropdown()

    def _path_menu(self, var, kind):
        path = var.get().strip()
        menu = tk.Menu(self.root, tearoff=0)

        if path:
            menu.add_command(label="Preview", command=lambda: self._preview_path(path))
            menu.add_separator()
            editors = editor_registry.list_editors()
            if editors:
                ow = tk.Menu(menu, tearoff=0)
                default = editor_registry.get_default()
                keys = editor_registry.ordered_keys(editors)
                if default and default in editors:
                    keys = [default] + [k for k in keys if k != default]
                for k in keys:
                    label = editor_registry.label_for(k)
                    if k == default:
                        label = f"\u2605 {label}"
                    ow.add_command(
                        label=label,
                        command=lambda k=k: self._open_with(path, k),
                    )
                ow.add_separator()
                ow.add_command(
                    label="System default",
                    command=lambda: open_file(path),
                )
                menu.add_cascade(label="Open with", menu=ow)
            else:
                menu.add_command(
                    label="Open with system default",
                    command=lambda: open_file(path),
                )
            menu.add_command(label="Reveal in folder", command=lambda: reveal_file(path))
            menu.add_command(
                label="Copy path",
                command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(path), self.set_status("copied path")),
            )
            menu.add_separator()
        menu.add_command(label="Clear", command=lambda: var.set(""))

        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def _open_with(self, path, editor_key):
        exe = editor_registry.list_editors().get(editor_key)
        if not exe:
            messagebox.showerror("Error", f"Editor '{editor_key}' not configured", parent=self.root)
            return
        import subprocess
        try:
            subprocess.Popen([exe, path])
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _preview_path(self, path):
        self.bottom_nb.select(2)
        values = self.preview_combo.cget("values")
        for i, v in enumerate(values):
            if path in v:
                self.preview_combo.current(i)
                self._reload_preview()
                return

    def _randomize_seed(self):
        import random
        self.seed_var.set(str(random.randint(1, 10 ** 9)))

    # ------------------------------------------------------ testlib

    def _download_testlib(self):
        target = testlib_dir() / "testlib.h"
        if target.exists():
            msg = (
                f"testlib.h already exists at:\n{target}\n\n"
                "Re-download and overwrite?"
            )
        else:
            msg = (
                "Download testlib.h from GitHub?\n\n"
                "Source: github.com/MikeMirzayanov/testlib\n"
                "It will be saved to the plugin data directory and "
                "automatically added to compiler include paths."
            )
        if not messagebox.askyesno("Download testlib.h", msg, parent=self.root):
            return

        from tools import download_testlib
        path, err = download_testlib()
        if err:
            messagebox.showerror(
                "Download failed",
                f"Could not download testlib.h:\n{err}",
                parent=self.root,
            )
            return
        messagebox.showinfo(
            "Success", f"Saved to:\n{path}", parent=self.root,
        )
        self.set_status("testlib.h downloaded")

    def _open_testlib_folder(self):
        p = testlib_dir()
        open_folder(p)

    # ------------------------------------------------------ preview

    def _refresh_preview_dropdown(self):
        items = []
        if self.source:
            items.append(f"Solution: {self.source.name}")
        g = self.gen_var.get().strip()
        if g:
            items.append(f"Generator: {Path(g).name}")
        b = self.std_brute_var.get().strip() or self.ck_brute_var.get().strip()
        if b:
            items.append(f"Brute: {Path(b).name}")
        ck = self.ck_checker_var.get().strip()
        if ck:
            items.append(f"Checker: {Path(ck).name}")
        it = self.int_var.get().strip()
        if it:
            items.append(f"Interactor: {Path(it).name}")
        self.preview_combo.configure(values=items)
        if items and not self.preview_combo.get():
            self.preview_combo.current(0)

    def _reload_preview(self):
        label = self.preview_combo.get()
        if not label:
            self.preview_text.configure(state="normal")
            self.preview_text.delete("1.0", "end")
            self.preview_text.configure(state="disabled")
            return
        kind, _, name = label.partition(": ")
        path = None
        if kind == "Solution" and self.source:
            path = self.source
        elif kind == "Generator":
            path = Path(self.gen_var.get().strip() or "")
        elif kind == "Brute":
            p = self.std_brute_var.get().strip() or self.ck_brute_var.get().strip()
            path = Path(p) if p else None
        elif kind == "Checker":
            p = self.ck_checker_var.get().strip()
            path = Path(p) if p else None
        elif kind == "Interactor":
            p = self.int_var.get().strip()
            path = Path(p) if p else None
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        if path and path.is_file():
            try:
                self.preview_text.insert("1.0", path.read_text(encoding="utf-8", errors="replace"))
            except Exception as e:
                self.preview_text.insert("1.0", f"<cannot read: {e}>")
        else:
            self.preview_text.insert("1.0", "<file not found>")
        self.preview_text.configure(state="disabled")

    def _preview_open_menu(self):
        label = self.preview_combo.get()
        if not label:
            return
        kind, _, _ = label.partition(": ")
        if kind == "Solution":
            self._path_menu(self.sol_var, "solution")
        elif kind == "Generator":
            self._path_menu(self.gen_var, "generator")
        elif kind == "Brute":
            v = self.std_brute_var if self.std_brute_var.get() else self.ck_brute_var
            self._path_menu(v, "brute")
        elif kind == "Checker":
            self._path_menu(self.ck_checker_var, "checker")
        elif kind == "Interactor":
            self._path_menu(self.int_var, "interactor")

    def _bottom_select(self, which):
        idx = {"log": 0, "fails": 1, "preview": 2}.get(which, 0)
        self.bottom_nb.select(idx)

    # ------------------------------------------------------ run

    def _start_stress(self):
        if self.busy:
            return
        if not self.source or not self.source.is_file():
            messagebox.showerror("Error", "Select a solution first", parent=self.root)
            return
        g = self.gen_var.get().strip()
        if not g or not Path(g).is_file():
            messagebox.showerror("Error", "Select a generator", parent=self.root)
            return

        idx = self.mode_nb.index(self.mode_nb.select())
        mode = ["standard", "checker", "interactive"][idx]
        self.scfg["mode"] = mode

        if mode == "standard":
            b = self.std_brute_var.get().strip()
            if not b or not Path(b).is_file():
                messagebox.showerror("Error", "Standard mode needs a brute force", parent=self.root)
                return
        elif mode == "checker":
            b = self.ck_brute_var.get().strip()
            ck = self.ck_checker_var.get().strip()
            if not b or not Path(b).is_file():
                messagebox.showerror("Error", "Checker mode needs a brute force", parent=self.root)
                return
            if not ck or not Path(ck).is_file():
                messagebox.showerror("Error", "Checker mode needs a checker", parent=self.root)
                return
        else:
            it = self.int_var.get().strip()
            if not it or not Path(it).is_file():
                messagebox.showerror("Error", "Interactive mode needs an interactor", parent=self.root)
                return

        self._save_solution_now()

        try:
            self.gcfg["max_fails"] = int(self.max_fails_var.get())
        except ValueError:
            self.gcfg["max_fails"] = 50
        self.gcfg["stop_on_fail"] = self.stop_var.get()
        self.gcfg["no_compile"] = self.no_compile_var.get()
        _save_full_cfg(self.gcfg)

        self.fails = []
        self.fails_tree.delete(*self.fails_tree.get_children())
        for w in self.fail_preview_widgets.values():
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")
        self._clear_log()
        self.bottom_nb.select(0)
        self._iter = 0
        self._start_time = time.monotonic()

        self.cancel_event = threading.Event()
        self.runner = StressRunner(
            self.gcfg, self.scfg, self.source,
            on_log=self._cb_log,
            on_fail=self._cb_fail,
            on_progress=self._cb_progress,
            on_done=self._cb_done,
            on_error=self._cb_error,
            on_compile=self._cb_compile,
            cancel_event=self.cancel_event,
        )

        self._set_running(True)
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        try:
            self.runner.run()
        except Exception as e:
            self.queue.put(("error", str(e)))
            self.queue.put(("done", ("exception", 0, 0, 0.0)))

    def _stop_stress(self):
        if self.runner:
            self.runner.cancel()
            self.set_status("stopping\u2026")

    def _cb_log(self, iter_n, seed, status, elapsed):
        self.queue.put(("log", (iter_n, seed, status, elapsed)))

    def _cb_fail(self, idx, seed, status, elapsed, fail_dir):
        self.queue.put(("fail", (idx, seed, status, elapsed, fail_dir)))

    def _cb_progress(self, iter_n, fails, elapsed):
        self.queue.put(("progress", (iter_n, fails, elapsed)))

    def _cb_done(self, reason, iter_n, fails, elapsed):
        self.queue.put(("done", (reason, iter_n, fails, elapsed)))

    def _cb_error(self, msg):
        self.queue.put(("error", msg))

    def _cb_compile(self, key, status, src):
        self.queue.put(("compile", (key, status, src)))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._apply_log(payload)
                elif kind == "fail":
                    self._apply_fail(payload)
                elif kind == "progress":
                    self._apply_progress(payload)
                elif kind == "done":
                    self._apply_done(payload)
                elif kind == "error":
                    self._apply_error(payload)
                elif kind == "compile":
                    self._apply_compile(payload)
        except queue.Empty:
            pass
        self.root.after(40, self._poll_queue)

    def _log_sys(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n", "SYS")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _apply_compile(self, payload):
        key, status, src = payload
        if status == "compiling":
            name = Path(src).name if src else key
            self._log_sys(f"compiling {key}: {name}")
        elif status == "done":
            self._log_sys(f"  {key} OK")
        elif status == "failed":
            self._log_sys(f"  {key} FAILED")
        elif status == "cancelled":
            self._log_sys(f"  {key} cancelled")
        elif status == "skipped":
            self._log_sys("skip compile (using existing binaries)")

    def _apply_log(self, payload):
        iter_n, seed, status, elapsed = payload
        line = f"{iter_n:>7}  seed={seed:<11}  [{status:>4}]  {elapsed:.3f}s\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line, status)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self._iter = iter_n

    def _apply_fail(self, payload):
        idx, seed, status, elapsed, fail_dir = payload
        info = {
            "index": idx, "seed": seed, "status": status,
            "elapsed": elapsed, "dir": fail_dir,
        }
        self.fails.append(info)
        self.fails_tree.insert(
            "", "end", iid=str(idx),
            values=(idx, seed, status, f"{elapsed:.3f}s"),
            tags=(status,),
        )

    def _apply_progress(self, payload):
        iter_n, fails, elapsed = payload
        rate = iter_n / elapsed if elapsed > 0 else 0
        self.progress_var.set(
            f"Running \u00b7 {iter_n} iters \u00b7 {fails} fails \u00b7 "
            f"{self._fmt_time(elapsed)} \u00b7 {rate:.1f}/s"
        )

    def _apply_done(self, payload):
        reason, iter_n, fails, elapsed = payload
        rate = iter_n / elapsed if elapsed > 0 else 0
        self.progress_var.set(
            f"Stopped ({reason}) \u00b7 {iter_n} iters \u00b7 {fails} fails \u00b7 "
            f"{self._fmt_time(elapsed)} \u00b7 {rate:.1f}/s"
        )
        self._set_running(False)

    def _apply_error(self, msg):
        first_line = msg.split("\n", 1)[0].strip()
        self.set_status(f"error: {first_line}")
        self._log_sys(f"ERROR: {first_line}")
        if "compile failed" in msg or "compile timed out" in msg:
            ErrorDialog(self.root, "Compile error", msg, app=self)

    def _fmt_time(self, s):
        s = int(s)
        if s < 60:
            return f"{s}s"
        return f"{s // 60}m{s % 60:02d}s"

    def _set_running(self, running):
        self.busy = running
        state = "disabled" if running else "normal"
        self.btn_start.configure(state=state)
        self.btn_stop.configure(state=("normal" if running else "disabled"))
        for w in (self.sol_entry, self.gen_entry):
            w.configure(state=state)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------ fails actions

    def _update_fail_preview(self):
        sel = self.fails_tree.selection()
        for w in self.fail_preview_widgets.values():
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")
        if not sel:
            return
        idx = int(sel[0])
        info = next((f for f in self.fails if f["index"] == idx), None)
        if not info:
            return
        d = Path(info.get("dir", ""))
        if not d.is_dir():
            return
        for name, key in (
            ("input.txt", "input"),
            ("expected.txt", "expected"),
            ("got.txt", "got"),
        ):
            p = d / name
            w = self.fail_preview_widgets[key]
            if p.is_file():
                try:
                    w.configure(state="normal")
                    w.insert("1.0", p.read_text(encoding="utf-8", errors="replace"))
                    w.configure(state="disabled")
                except Exception:
                    pass
        log = d / "interaction_log.txt"
        if log.is_file():
            w = self.fail_preview_widgets["expected"]
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.insert("1.0", "[interaction log]\n" + log.read_text(encoding="utf-8", errors="replace"))
            w.configure(state="disabled")

    def _add_selected_to_runner(self):
        sel = self.fails_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        info = next((f for f in self.fails if f["index"] == idx), None)
        if not info:
            return
        self._add_fail_to_runner(info)
        self.set_status(f"added fail #{idx} to runner tests")

    def _add_all_fails_to_runner(self):
        if not self.source or not self.fails:
            self.set_status("no fails to add")
            return
        if not messagebox.askyesno(
            "Add all fails",
            f"Add all {len(self.fails)} fails to runner tests?\n"
            "Each will be inserted as a new test (no overwrite).",
            parent=self.root,
        ):
            return

        ok = 0
        fail = 0
        for info in self.fails:
            if self._add_fail_to_runner(info, silent=True):
                ok += 1
            else:
                fail += 1

        self.set_status(f"added {ok} fails to runner ({fail} failed)")

    def _add_fail_to_runner(self, info, silent=False):
        d = Path(info.get("dir", ""))
        inp = d / "input.txt"
        exp = d / "expected.txt"
        if not inp.is_file() or not exp.is_file():
            if not silent:
                messagebox.showerror("Error", "input or expected file missing", parent=self.root)
            return False
        import subprocess
        try:
            r = subprocess.run(
                ["cpt", "run", "test", "add", str(self.source), str(inp), str(exp)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return True
            if not silent:
                messagebox.showerror("Error", r.stderr or r.stdout, parent=self.root)
            return False
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", str(e), parent=self.root)
            return False

    def _view_selected_fail(self):
        sel = self.fails_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        info = next((f for f in self.fails if f["index"] == idx), None)
        if not info:
            return
        FailViewDialog(self.root, info, self.source, self)

    def _open_fails_folder(self):
        if not self.source:
            return
        p = fails_dir(self.source)
        open_folder(p)

    def _clear_fails(self):
        if not self.source:
            return
        if not messagebox.askyesno("Clear", "Clear all fails?", parent=self.root):
            return
        clear_fails(self.source)
        self.fails = []
        self.fails_tree.delete(*self.fails_tree.get_children())
        for w in self.fail_preview_widgets.values():
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")
        self.set_status("fails cleared")

    # ------------------------------------------------------ hotkeys

    def _apply_hotkeys(self):
        for binding in list(self._bound.values()):
            try:
                self.root.unbind(binding)
            except Exception:
                pass
        self._bound.clear()
        hk = self.gcfg.get("hotkeys") or DEFAULT_HOTKEYS
        for action, display in hk.items():
            if not display:
                continue
            tk_b = _parse_hotkey(display)
            if not tk_b:
                continue
            cb = self._hotkey_cb(action)
            if not cb:
                continue
            try:
                self.root.bind(tk_b, cb)
                self._bound[action] = tk_b
            except Exception:
                pass

    def _hotkey_cb(self, action):
        return {
            "start":    lambda e: self._hk(self._start_stress),
            "stop":     lambda e: self._hk(self._stop_stress),
            "open":     lambda e: self._hk(self._browse_solution),
            "settings": lambda e: self._hk(self._open_settings),
            "quit":     lambda e: self._hk(self._quit),
        }.get(action)

    def _hk(self, fn):
        fn()
        return "break"

    # ------------------------------------------------------ misc

    def _open_settings(self):
        SettingsDialog(self.root, self)

    def set_status(self, msg):
        self.status_var.set(msg)

    def _quit(self):
        if self.busy:
            if not messagebox.askyesno(
                "Quit", "Stress is running. Stop and quit?", parent=self.root,
            ):
                return
            if self.runner:
                self.runner.cancel()
            time.sleep(0.2)
        self.root.destroy()


def launch(initial_source=None):
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.15)
    except Exception:
        pass
    StressApp(root, initial_source=initial_source)
    root.mainloop()
    return 0