import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from compile import compile_source, default_output, find_compiler, is_stale
from run import run_binary, compare
from store import (
    DEFAULT_IO, load, save, add_test, remove_test, work_root_for,
    load_history, add_to_history, clear_history, MAX_HISTORY,
)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False


CONFIG_DIR = Path(os.environ["CPTOOLS_PLUGIN_CONFIG_DIR"])
CACHE_DIR = Path(os.environ["CPTOOLS_PLUGIN_CACHE_DIR"])
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "compiler": "g++",
    "compiler_flags": ["-O2", "-std=c++17"],
    "timeout": 5,
    "compile_timeout": 60,
    "bin_dir": "",
    "rebuild": "auto",
}

DEFAULT_HOTKEYS = {
    "new_tab":     "Ctrl+T",
    "open_file":   "Ctrl+O",
    "close_tab":   "Ctrl+W",
    "next_tab":    "Ctrl+Tab",
    "prev_tab":    "Ctrl+Shift+Tab",
    "build":       "Ctrl+B",
    "run_all":     "F5",
    "add_test":    "Ctrl+N",
    "delete_test": "Delete",
    "focus_next":  "Ctrl+Return",
    "settings":    "Ctrl+comma",
    "quit":        "Ctrl+Q",
}

HOTKEY_ACTIONS = [
    ("new_tab",     "New tab"),
    ("open_file",   "Open file"),
    ("close_tab",   "Close tab"),
    ("next_tab",    "Next tab"),
    ("prev_tab",    "Previous tab"),
    ("build",       "Build"),
    ("run_all",     "Run all"),
    ("add_test",    "Add test"),
    ("delete_test", "Delete test"),
    ("focus_next",  "Focus next"),
    ("settings",    "Settings"),
    ("quit",        "Quit"),
]

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

BG_DISABLED = "#ececec"
BG_NORMAL = "#ffffff"

PASS_FG = "#1f7a1f"
FAIL_FG = "#c02020"
TIMEOUT_FG = "#b06000"

AUTO_SAVE_MS = 400


# =================================================================== helpers

def _load_full_cfg():
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    cfg = dict(DEFAULTS)
    for k, v in data.items():
        if k == "hotkeys":
            continue
        cfg[k] = v
    if not isinstance(cfg.get("compiler_flags"), list):
        cfg["compiler_flags"] = list(DEFAULTS["compiler_flags"])
    hk = dict(DEFAULT_HOTKEYS)
    user_hk = data.get("hotkeys") or {}
    if isinstance(user_hk, dict):
        for k, v in user_hk.items():
            if k in DEFAULT_HOTKEYS and isinstance(v, str):
                hk[k] = v
    cfg["hotkeys"] = hk
    return cfg


def _save_full_cfg(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in cfg.items() if k != "hotkeys"}
    data["hotkeys"] = cfg.get("hotkeys", {})
    CONFIG_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _set_readonly(widget, text):
    state = str(widget.cget("state"))
    if state == "disabled":
        widget.configure(state="normal")
    widget.delete("1.0", "end")
    if text:
        widget.insert("1.0", text)
    widget.configure(state="disabled")


def _set_editor_enabled(widget, enabled):
    if enabled:
        widget.configure(state="normal", background=BG_NORMAL)
    else:
        widget.configure(state="disabled", background=BG_DISABLED)


def _copy_to_clipboard(widget, app):
    content = widget.get("1.0", "end-1c")
    if not content:
        return
    widget.clipboard_clear()
    widget.clipboard_append(content)
    app.set_status("copied")


# =================================================================== hotkey parse

_DISPLAY_ALIASES = {
    "comma": ",",
    "period": ".",
    "slash": "/",
    "backslash": "\\",
    "semicolon": ";",
    "apostrophe": "'",
    "bracketleft": "[",
    "bracketright": "]",
    "minus": "-",
    "equal": "=",
    "grave": "`",
    "space": "Space",
    "Return": "Enter",
    "Escape": "Esc",
}

# canonical keysym → display form (user-facing)
_KEY_DISPLAY = {
    "comma": ",",
    "period": ".",
    "slash": "/",
    "backslash": "\\",
    "semicolon": ";",
    "apostrophe": "'",
    "bracketleft": "[",
    "bracketright": "]",
    "minus": "-",
    "equal": "=",
    "grave": "`",
    "space": "Space",
    "Return": "Enter",
    "Escape": "Esc",
    "Tab": "Tab",
    "BackSpace": "Backspace",
    "Delete": "Delete",
    "Insert": "Insert",
    "Home": "Home",
    "End": "End",
    "Prior": "PageUp",
    "Next": "PageDown",
    "Up": "Up",
    "Down": "Down",
    "Left": "Left",
    "Right": "Right",
}

# display → keysym for parsing back
_DISPLAY_TO_KEY = {
    ",": "comma",
    ".": "period",
    "/": "slash",
    "\\": "backslash",
    ";": "semicolon",
    "'": "apostrophe",
    "[": "bracketleft",
    "]": "bracketright",
    "-": "minus",
    "=": "equal",
    "`": "grave",
    "Space": "space",
    "Enter": "Return",
    "Esc": "Escape",
}

_MOD_KEYSYM = {
    "Control_L": "Ctrl", "Control_R": "Ctrl",
    "Shift_L": "Shift", "Shift_R": "Shift",
    "Alt_L": "Alt", "Alt_R": "Alt",
    "Super_L": "Super", "Super_R": "Super",
    "Meta_L": "Super", "Meta_R": "Super",
}

_SHIFT_MAP = {
    "exclam": "1",
    "at": "2",
    "numbersign": "3",
    "dollar": "4",
    "percent": "5",
    "asciicircum": "6",
    "ampersand": "7",
    "asterisk": "8",
    "parenleft": "9",
    "parenright": "0",
    "underscore": "-",
    "plus": "=",
    "braceleft": "[",
    "braceright": "]",
    "bar": "\\",
    "colon": ";",
    "quotedbl": "'",
    "less": ",",
    "greater": ".",
    "question": "/",
    "asciitilde": "`",
}

_SHIFT_KEY_REVERSE = {v: k for k, v in _SHIFT_MAP.items()}


def _modifier_from_keysym(ks):
    return _MOD_KEYSYM.get(ks)


def _mod_order(mods):
    order = ["Ctrl", "Shift", "Alt", "Super"]
    return [m for m in order if m in mods]


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


def _event_to_display(event):
    state = event.state
    parts = []
    if state & 0x4:
        parts.append("Ctrl")
    if state & 0x1:
        parts.append("Shift")
    if state & 0x8:
        parts.append("Alt")
    if state & 0x40:
        parts.append("Super")

    ks = event.keysym
    if ks in ("Control_L", "Control_R", "Shift_L", "Shift_R",
              "Alt_L", "Alt_R", "Super_L", "Super_R", "Meta_L", "Meta_R",
              "Caps_Lock", "Num_Lock", "Scroll_Lock"):
        return None

    display_key = _KEY_DISPLAY.get(ks, ks)
    if len(display_key) == 1 and display_key.isalpha():
        display_key = display_key.upper()

    if not parts:
        return display_key
    return "+".join(parts + [display_key])


# =================================================================== CaptureDialog

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
            frame, text="Press a new key combination…",
            font=UI_SMALL, foreground=FG_MUTED,
        ).pack(anchor="w", pady=(2, 8))

        info = ttk.Frame(frame)
        info.pack(fill="x", pady=(0, 8))
        info.columnconfigure(1, weight=1)

        ttk.Label(info, text="Current:", font=UI).grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Label(info, text=current_display or "(none)", font=UI).grid(row=0, column=1, sticky="w")

        ttk.Label(info, text="New:", font=UI).grid(row=1, column=0, sticky="w", padx=(0, 6))
        self.new_var = tk.StringVar(value="waiting…")
        ttk.Label(info, textvariable=self.new_var, font=UI_BOLD).grid(
            row=1, column=1, sticky="w"
        )

        btns = ttk.Frame(frame)
        btns.pack(fill="x", side="bottom")
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="right")
        self.confirm_btn = ttk.Button(btns, text="Confirm", command=self._confirm)
        self.confirm_btn.pack(side="right", padx=(0, 4))
        self.confirm_btn.configure(state="disabled")

        self.bind("<KeyPress>", self._on_press)
        self.bind("<KeyRelease>", self._on_release)
        self.bind("<FocusOut>", self._on_focus_out)
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

    def _on_focus_out(self, event):
        self._mods.clear()

    def _update_display(self):
        if self._mods:
            self.new_var.set("+".join(_mod_order(self._mods)) + "+…")
        else:
            self.new_var.set("waiting…")

    def _confirm(self):
        self.result = self._current
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

# =================================================================== SettingsDialog

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Settings")
        self.geometry("460x480")
        self.transient(parent)
        self.minsize(400, 380)

        self._hotkeys = dict(app.cfg.get("hotkeys") or DEFAULT_HOTKEYS)

        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Hotkeys", font=UI_BOLD).pack(anchor="w", pady=(0, 6))

        list_frame = ttk.Frame(outer)
        list_frame.pack(fill="both", expand=True)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            list_frame, columns=("action", "binding"),
            show="headings", selectmode="browse",
        )
        self.tree.heading("action", text="Action")
        self.tree.heading("binding", text="Binding")
        self.tree.column("action", width=200, anchor="w")
        self.tree.column("binding", width=180, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        hint = ttk.Label(
            outer, text="Double-click a row to rebind",
            font=UI_SMALL, foreground=FG_MUTED,
        )
        hint.pack(anchor="w", pady=(4, 6))

        btns = ttk.Frame(outer)
        btns.pack(fill="x")
        ttk.Button(btns, text="Reset all", command=self._reset_all).pack(side="left")
        ttk.Button(btns, text="Close", command=self._close).pack(side="right")
        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=(0, 4))

        self._populate()
        self.grab_set()

    def _populate(self):
        self.tree.delete(*self.tree.get_children())
        for key, label in HOTKEY_ACTIONS:
            display = self._hotkeys.get(key, "")
            self.tree.insert("", "end", iid=key, values=(label, display or "(none)"))

    def _edit_selected(self):
        sel = self.tree.selection()
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
            conflicts = [
                (k, lbl) for k, lbl in HOTKEY_ACTIONS
                if k != key and self._hotkeys.get(k) == new_binding
            ]
            if conflicts:
                other_label = conflicts[0][1]
                if not messagebox.askyesno(
                    "Hotkey conflict",
                    f"'{new_binding}' is already bound to '{other_label}'.\n"
                    f"Replace it?",
                    parent=self,
                ):
                    return
                for k, _ in conflicts:
                    self._hotkeys[k] = ""
        self._hotkeys[key] = new_binding
        self._populate()

    def _reset_all(self):
        if not messagebox.askyesno(
            "Reset hotkeys",
            "Reset all hotkeys to defaults?",
            parent=self,
        ):
            return
        self._hotkeys = dict(DEFAULT_HOTKEYS)
        self._populate()

    def _save(self):
        self.app.cfg["hotkeys"] = dict(self._hotkeys)
        _save_full_cfg(self.app.cfg)
        self.app._apply_hotkeys()
        self.app.set_status("hotkeys saved")
        self.destroy()

    def _close(self):
        self.destroy()


# =================================================================== SessionTab

class SessionTab(ttk.Frame):
    def __init__(self, parent, app, source=None):
        super().__init__(parent, padding=4)
        self.app = app
        self.cfg = app.cfg
        self.source = None
        self.tests_data = None
        self.binary = None
        self.current_test_id = None
        self.busy = False
        self.queue = queue.Queue()
        self._save_timer = None
        self._suppress_change = False
        self._suppress_io = False
        self.test_outputs = {}

        self._build_ui()
        self._bind_dnd()
        self.set_source(source)
        self.after(40, self._poll_queue)

    @property
    def title(self):
        return self.source.stem if self.source else "New"

    # -------------------------------------------------------- ui

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        row0 = ttk.Frame(self)
        row0.grid(row=0, column=0, sticky="ew")
        row0.columnconfigure(1, weight=1)

        ttk.Label(row0, text="Source", font=UI).grid(row=0, column=0, padx=(0, 4))

        self.source_var = tk.StringVar()
        self.source_entry = ttk.Entry(row0, textvariable=self.source_var, font=UI)
        self.source_entry.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.source_entry.bind("<Return>", lambda e: self._on_source_enter())

        ttk.Button(row0, text="\u2026", width=2,
                   command=self._browse_source).grid(row=0, column=2)

        row1 = ttk.Frame(self)
        row1.grid(row=1, column=0, sticky="ew", pady=(PAD, PAD))
        row1.columnconfigure(2, weight=1)

        self.btn_build = ttk.Button(row1, text="Build", width=6,
                                    command=self._build)
        self.btn_build.grid(row=0, column=0, padx=(0, 2))

        self.btn_run = ttk.Button(row1, text="Run", width=6,
                                  command=self._run_all)
        self.btn_run.grid(row=0, column=1, padx=2)

        self.btn_close = ttk.Button(row1, text="\u2715 Close tab", width=11,
                                    command=self._close_self)
        self.btn_close.grid(row=0, column=4)

        main = ttk.Frame(self)
        main.grid(row=2, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, width=90)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 4))
        left.grid_propagate(False)
        left.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            left, columns=("id", "st"),
            show="headings", selectmode="extended",
        )
        self.tree.heading("id", text="#")
        self.tree.heading("st", text="")
        self.tree.column("id", width=26, anchor="center", stretch=False)
        self.tree.column("st", width=54, anchor="w", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("pass", foreground=PASS_FG)
        self.tree.tag_configure("fail", foreground=FAIL_FG)
        self.tree.tag_configure("timeout", foreground=TIMEOUT_FG)
        self.tree.bind("<<TreeviewSelect>>", self._on_test_select)

        lb = ttk.Frame(left)
        lb.grid(row=1, column=0, sticky="ew", pady=(PAD, 0))
        lb.columnconfigure((0, 1), weight=1)
        ttk.Button(lb, text="+", width=2,
                   command=self._new_test).grid(row=0, column=0, sticky="ew", padx=(0, 1))
        ttk.Button(lb, text="\u2715", width=2,
                   command=self._delete_tests).grid(row=0, column=1, sticky="ew", padx=(1, 0))

        self.inner = ttk.Notebook(main)
        self.inner.grid(row=0, column=1, sticky="nsew")
        self.inner.bind("<<NotebookTabChanged>>", self._on_inner_tab_change)

        self._build_io_tab()
        self._build_source_tab()

    def _build_io_tab(self):
        io = ttk.Frame(self.inner, padding=4)
        self.inner.add(io, text="I/O")

        io.columnconfigure(0, weight=1)
        io.rowconfigure(2, weight=2)
        io.rowconfigure(4, weight=2)
        io.rowconfigure(6, weight=3)

        mode_box = ttk.LabelFrame(io, text=" I/O mode ", padding=(6, 4))
        mode_box.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        mode_box.columnconfigure(2, weight=1)

        ttk.Label(mode_box, text="Input", font=UI, anchor="w", width=7).grid(
            row=0, column=0, sticky="w", pady=(0, 2)
        )

        self.input_mode_var = tk.StringVar(value="stdin")
        in_cb = ttk.Combobox(
            mode_box, textvariable=self.input_mode_var,
            values=["stdin", "file"], width=8,
            state="readonly", font=UI,
        )
        in_cb.grid(row=0, column=1, padx=(6, 6), pady=(0, 2))
        in_cb.bind("<<ComboboxSelected>>", self._on_io_change)

        self.input_file_var = tk.StringVar(value="input.txt")
        self.input_file_entry = ttk.Entry(
            mode_box, textvariable=self.input_file_var, font=UI,
        )
        self.input_file_entry.grid(row=0, column=2, sticky="ew", pady=(0, 2))
        self.input_file_var.trace_add("write", self._on_io_change)

        ttk.Label(mode_box, text="Output", font=UI, anchor="w", width=7).grid(
            row=1, column=0, sticky="w"
        )

        self.output_mode_var = tk.StringVar(value="stdout")
        out_cb = ttk.Combobox(
            mode_box, textvariable=self.output_mode_var,
            values=["stdout", "file"], width=8,
            state="readonly", font=UI,
        )
        out_cb.grid(row=1, column=1, padx=(6, 6))
        out_cb.bind("<<ComboboxSelected>>", self._on_io_change)

        self.output_file_var = tk.StringVar(value="output.txt")
        self.output_file_entry = ttk.Entry(
            mode_box, textvariable=self.output_file_var, font=UI,
        )
        self.output_file_entry.grid(row=1, column=2, sticky="ew")
        self.output_file_var.trace_add("write", self._on_io_change)

        h1 = ttk.Frame(io)
        h1.grid(row=1, column=0, sticky="ew")
        ttk.Label(h1, text="Input", font=UI_BOLD).pack(side="left")
        ttk.Button(h1, text="Load", width=5,
                   command=lambda: self._load_into(self.input_text)
                   ).pack(side="right", padx=(2, 0))
        ttk.Button(h1, text="Clear", width=5,
                   command=lambda: self._clear(self.input_text)
                   ).pack(side="right", padx=2)

        self.input_text = self._mk_text(io, height=4)
        self.input_text.grid(row=2, column=0, sticky="nsew", pady=(1, 4))

        h2 = ttk.Frame(io)
        h2.grid(row=3, column=0, sticky="ew")
        ttk.Label(h2, text="Expected", font=UI_BOLD).pack(side="left")
        ttk.Button(h2, text="Load", width=5,
                   command=lambda: self._load_into(self.expected_text)
                   ).pack(side="right", padx=(2, 0))
        ttk.Button(h2, text="Clear", width=5,
                   command=lambda: self._clear(self.expected_text)
                   ).pack(side="right", padx=2)

        self.expected_text = self._mk_text(io, height=4)
        self.expected_text.grid(row=4, column=0, sticky="nsew", pady=(1, 4))

        h3 = ttk.Frame(io)
        h3.grid(row=5, column=0, sticky="ew")
        ttk.Label(h3, text="Output", font=UI_BOLD).pack(side="left")
        self.match_label = ttk.Label(h3, text="", font=UI_SMALL, foreground=FG_MUTED)
        self.match_label.pack(side="left", padx=(6, 0))
        ttk.Button(h3, text="Clear", width=5,
                   command=self._clear_output).pack(side="right", padx=(2, 0))
        ttk.Button(h3, text="Save", width=5,
                   command=self._save_output).pack(side="right", padx=2)
        ttk.Button(h3, text="Copy", width=5,
                   command=lambda: _copy_to_clipboard(self.got_text, self.app)
                   ).pack(side="right", padx=2)

        self.got_text = self._mk_text(io, height=5, readonly=True)
        self.got_text.grid(row=6, column=0, sticky="nsew", pady=(1, 0))

    def _build_source_tab(self):
        src = ttk.Frame(self.inner, padding=3)
        self.inner.add(src, text="Source")

        src.columnconfigure(0, weight=1)
        src.rowconfigure(1, weight=1)

        h = ttk.Frame(src)
        h.grid(row=0, column=0, sticky="ew")
        ttk.Label(h, text="Preview", font=UI_BOLD).pack(side="left")
        ttk.Button(h, text="Reload", width=6,
                   command=self._reload_preview).pack(side="right")

        self.source_view = self._mk_text(src, height=10, readonly=True)
        self.source_view.grid(row=1, column=0, sticky="nsew", pady=(1, 0))

    def _mk_text(self, parent, height=4, readonly=False):
        t = ScrolledText(
            parent, wrap="none", font=MONO, height=height,
            undo=not readonly, maxundo=200,
            borderwidth=0, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BORDER_FOCUS,
            background=BG_NORMAL if not readonly else "#f6f6f6",
            padx=4, pady=3,
        )
        if readonly:
            t.configure(state="disabled")
        else:
            t.bind("<<Modified>>", self._on_editor_change)
        return t

    # -------------------------------------------------------- io mode

    def _on_io_change(self, *_):
        if self._suppress_io or not self.tests_data:
            self._update_io_entry_state()
            return
        self.tests_data["io"] = {
            "input": self.input_mode_var.get(),
            "output": self.output_mode_var.get(),
            "input_file": self.input_file_var.get().strip() or "input.txt",
            "output_file": self.output_file_var.get().strip() or "output.txt",
        }
        save(self.tests_data)
        self._update_io_entry_state()

    def _update_io_entry_state(self):
        in_state = "normal" if self.input_mode_var.get() == "file" else "disabled"
        out_state = "normal" if self.output_mode_var.get() == "file" else "disabled"
        try:
            self.input_file_entry.configure(state=in_state)
            self.output_file_entry.configure(state=out_state)
        except tk.TclError:
            pass

    def _load_io_config(self):
        self._suppress_io = True
        try:
            io = (self.tests_data or {}).get("io") or dict(DEFAULT_IO)
            self.input_mode_var.set(io.get("input", "stdin"))
            self.output_mode_var.set(io.get("output", "stdout"))
            self.input_file_var.set(io.get("input_file", "input.txt"))
            self.output_file_var.set(io.get("output_file", "output.txt"))
        finally:
            self._suppress_io = False
        self._update_io_entry_state()

    # -------------------------------------------------------- dnd

    def _bind_dnd(self):
        if not HAS_DND:
            return
        try:
            self.source_entry.drop_target_register(DND_FILES)
            self.source_entry.dnd_bind("<<Drop>>", self._on_drop_source)
            for w in (self.input_text, self.expected_text):
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop_io)
        except Exception:
            pass

    def _parse_drop(self, data):
        try:
            return self.winfo_toplevel().tk.splitlist(data)
        except Exception:
            return [data.strip("{}")]

    def _on_drop_source(self, event):
        paths = self._parse_drop(event.data)
        if paths:
            self.set_source(Path(paths[0]))

    def _on_drop_io(self, event):
        paths = self._parse_drop(event.data)
        if not paths:
            return
        try:
            text = Path(paths[0]).read_text(encoding="utf-8")
        except OSError as e:
            self.app.set_status(f"cannot read {paths[0]}: {e}")
            return
        target = event.widget
        if str(target.cget("state")) == "disabled":
            return
        target.delete("1.0", "end")
        target.insert("1.0", text)

    # -------------------------------------------------------- source

    def set_source(self, path):
        if self._save_timer:
            self.after_cancel(self._save_timer)
            self._save_timer = None
        self._do_auto_save()

        if path is None:
            self.source = None
            self.tests_data = None
            self.binary = None
            self.source_var.set("")
        else:
            path = Path(path).resolve()
            self.source = path
            self.source_var.set(str(path))
            self.tests_data = load(path)
            self.binary = None

        self.test_outputs = {}
        self._load_io_config()
        self._refresh_tree()
        self._clear_editors()
        self._clear_output()
        self._reload_preview()
        self.app.update_tab_title(self)
        if path is None:
            self.app.set_status("no source")
        else:
            self.app.set_status(f"loaded {path.name}")
            self.app._on_source_opened(path)

    def _reload_preview(self):
        if self.source and self.source.is_file():
            try:
                content = self.source.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                content = f"<cannot read: {e}>"
        else:
            content = ""
        _set_readonly(self.source_view, content)

    def _on_source_enter(self):
        p = self.source_var.get().strip()
        if p:
            self.set_source(Path(p))

    def _browse_source(self):
        p = filedialog.askopenfilename(
            parent=self,
            title="Select source",
            filetypes=[("C/C++", "*.cpp *.cc *.cxx *.c"), ("All files", "*.*")],
        )
        if p:
            self.set_source(Path(p))

    def _on_inner_tab_change(self, event):
        try:
            idx = self.inner.index(self.inner.select())
        except tk.TclError:
            return
        if self.inner.tab(idx, "text") == "Source":
            self._reload_preview()

    # -------------------------------------------------------- tests

    def _refresh_tree(self, select_index=None):
        self.tree.delete(*self.tree.get_children())
        if not self.tests_data:
            return
        for t in self.tests_data["tests"]:
            self.tree.insert("", "end", iid=str(t["id"]), values=(t["id"], ""))

        if select_index is not None and self.tests_data["tests"]:
            i = max(0, min(select_index, len(self.tests_data["tests"]) - 1))
            self.tree.selection_set(str(self.tests_data["tests"][i]["id"]))

    def _disable_editors(self):
        _set_editor_enabled(self.input_text, False)
        _set_editor_enabled(self.expected_text, False)

    def _enable_editors(self):
        _set_editor_enabled(self.input_text, True)
        _set_editor_enabled(self.expected_text, True)

    def _clear_editors(self):
        self._suppress_change = True
        try:
            for w in (self.input_text, self.expected_text):
                w.configure(state="normal")
                w.delete("1.0", "end")
                w.edit_modified(False)
            self._disable_editors()
        finally:
            self._suppress_change = False
        self.match_label.configure(text="no test selected")
        self.current_test_id = None

    def _clear_output(self):
        _set_readonly(self.got_text, "")
        self.match_label.configure(text="")

    def _on_test_select(self, event=None):
        if self._save_timer:
            self.after_cancel(self._save_timer)
            self._save_timer = None
        self._do_auto_save()

        sel = self.tree.selection()
        n = len(sel)

        if n == 0:
            self._suppress_change = True
            try:
                for w in (self.input_text, self.expected_text):
                    w.configure(state="normal")
                    w.delete("1.0", "end")
                    w.edit_modified(False)
                self._disable_editors()
            finally:
                self._suppress_change = False
            self.current_test_id = None
            self.match_label.configure(text="no test selected")
            return

        if n > 1:
            self.current_test_id = None
            self._disable_editors()
            self.match_label.configure(text=f"{n} selected")
            return

        self._enable_editors()

        tid = int(sel[0])
        t = next((x for x in self.tests_data["tests"] if x["id"] == tid), None)
        if not t:
            return

        self.current_test_id = tid
        self._suppress_change = True
        try:
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", t["input"])
            self.input_text.edit_modified(False)
            self.expected_text.delete("1.0", "end")
            self.expected_text.insert("1.0", t["expected"])
            self.expected_text.edit_modified(False)
        finally:
            self._suppress_change = False

        cached = self.test_outputs.get(tid)
        if cached:
            self._show_output(cached)
            if cached.get("timeout"):
                self.match_label.configure(text="TIMEOUT")
            elif cached.get("passed"):
                self.match_label.configure(text="PASS")
            else:
                self.match_label.configure(text="FAIL")
        else:
            _set_readonly(self.got_text, "")
            self.match_label.configure(text="")

    def _on_editor_change(self, event=None):
        if self._suppress_change:
            return
        if not (self.input_text.edit_modified() or self.expected_text.edit_modified()):
            return
        self._suppress_change = True
        try:
            self.input_text.edit_modified(False)
            self.expected_text.edit_modified(False)
        finally:
            self._suppress_change = False
        self._schedule_save()

    def _schedule_save(self):
        if self._save_timer:
            self.after_cancel(self._save_timer)
        self._save_timer = self.after(AUTO_SAVE_MS, self._do_auto_save)

    def _do_auto_save(self):
        self._save_timer = None
        if self.current_test_id is None or not self.tests_data:
            return
        t = next((x for x in self.tests_data["tests"]
                  if x["id"] == self.current_test_id), None)
        if not t:
            return
        try:
            new_in = self.input_text.get("1.0", "end-1c")
            new_exp = self.expected_text.get("1.0", "end-1c")
        except tk.TclError:
            return
        if new_in == t["input"] and new_exp == t["expected"]:
            return
        t["input"] = new_in
        t["expected"] = new_exp
        save(self.tests_data)
        self.test_outputs.pop(self.current_test_id, None)

    def _new_test(self):
        if not self.tests_data:
            self.app.set_status("select a source first")
            return
        tid = add_test(self.tests_data, "", "")
        save(self.tests_data)
        idx = len(self.tests_data["tests"]) - 1
        self._refresh_tree(select_index=idx)
        self._on_test_select()
        self.app.set_status(f"new test {tid}")

    def _delete_tests(self):
        if not self.tests_data:
            return
        sel = self.tree.selection()
        if not sel:
            self.app.set_status("no test selected")
            return
        ids = {int(s) for s in sel}
        if len(ids) == 1:
            msg = f"Delete test {list(ids)[0]}?"
        else:
            msg = f"Delete {len(ids)} tests?"
        if not messagebox.askyesno("Delete", msg, parent=self):
            return

        first_idx = next(
            (i for i, t in enumerate(self.tests_data["tests"]) if t["id"] in ids),
            0,
        )
        self.tests_data["tests"] = [
            t for t in self.tests_data["tests"] if t["id"] not in ids
        ]
        for i, t in enumerate(self.tests_data["tests"], start=1):
            t["id"] = i
        save(self.tests_data)

        self.test_outputs = {}
        self._refresh_tree(select_index=first_idx)
        if self.tests_data["tests"]:
            self._on_test_select()
        else:
            self._clear_editors()
        self.app.set_status(f"deleted {len(ids)} test(s)")

    def _load_into(self, text_widget):
        if str(text_widget.cget("state")) == "disabled":
            self.app.set_status("select a test first")
            return
        p = filedialog.askopenfilename(
            parent=self,
            title="Load file",
            filetypes=[("Text", "*.txt *.in *.out *.ans"), ("All files", "*.*")],
        )
        if not p:
            return
        try:
            content = Path(p).read_text(encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Error", str(e), parent=self)
            return
        text_widget.delete("1.0", "end")
        text_widget.insert("1.0", content)

    def _clear(self, text_widget):
        if str(text_widget.cget("state")) == "disabled":
            self.app.set_status("select a test first")
            return
        if text_widget.get("1.0", "end-1c").strip():
            if not messagebox.askyesno("Clear", "Clear this field?", parent=self):
                return
        text_widget.delete("1.0", "end")

    def _save_output(self):
        content = self.got_text.get("1.0", "end-1c")
        if not content:
            return
        p = filedialog.asksaveasfilename(
            parent=self,
            title="Save output",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if not p:
            return
        try:
            Path(p).write_text(content, encoding="utf-8")
            self.app.set_status(f"saved: {p}")
        except OSError as e:
            messagebox.showerror("Error", str(e), parent=self)

    # -------------------------------------------------------- build & run

    def _prepare_binary(self, force=False):
        if not self.source or not self.source.is_file():
            return None, "no source file"

        compiler = self.cfg.get("compiler") or "g++"
        if not find_compiler(compiler):
            return None, f"compiler not found in PATH: {compiler}"

        bin_dir = (Path(self.cfg["bin_dir"]).expanduser()
                   if self.cfg.get("bin_dir") else CACHE_DIR / "bin")
        output = default_output(self.source, bin_dir)

        mode = self.cfg.get("rebuild", "auto")
        need = force or mode == "always"
        if mode == "auto" and is_stale(self.source, output):
            need = True
        if mode == "never" and not output.is_file():
            return None, (
                f"no compiled binary at {output}\n"
                "rebuild is set to 'never' — build manually or change config"
            )

        if need:
            r = compile_source(
                self.source, output,
                compiler=compiler,
                flags=self.cfg.get("compiler_flags"),
                timeout=int(self.cfg.get("compile_timeout", 60)),
            )
            if not r["ok"]:
                return None, {"compile_error": r}

        return output, None

    def _run_async(self, fn, on_done):
        if self.busy:
            self.app.set_status("busy...")
            return
        self.busy = True
        self._set_buttons(False)

        def worker():
            try:
                r = fn()
                self.queue.put(("ok", on_done, r))
            except Exception as e:
                self.queue.put(("err", on_done, e))

        threading.Thread(target=worker, daemon=True).start()

    def _set_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        for b in (self.btn_build, self.btn_run):
            b.configure(state=state)

    def _poll_queue(self):
        try:
            while True:
                kind, cb, payload = self.queue.get_nowait()
                self.busy = False
                self._set_buttons(True)
                if kind == "ok":
                    cb(payload)
                else:
                    self.app.set_status(f"error: {payload}")
        except queue.Empty:
            pass
        self.after(40, self._poll_queue)

    def _handle_error(self, err):
        if isinstance(err, dict) and "compile_error" in err:
            r = err["compile_error"]
            self.app.set_status("compile failed")
            self._show_compile_error(r)
        else:
            self.app.set_status("error")
            messagebox.showerror("Error", str(err), parent=self)

    def _show_compile_error(self, r):
        top = tk.Toplevel(self)
        top.title("Compilation error")
        top.geometry("640x420")
        top.transient(self.winfo_toplevel())

        frame = ttk.Frame(top, padding=6)
        frame.pack(fill="both", expand=True)

        info = f"$ {' '.join(r.get('cmd', []))}\n\nexit code: {r.get('returncode', '?')}\n"
        body = (r.get("stderr") or "") + ("\n" + r["stdout"] if r.get("stdout") else "")

        txt = ScrolledText(frame, wrap="word", font=MONO, height=20)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", info + "\n" + body)
        txt.configure(state="disabled")

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Close", command=top.destroy).pack(side="right")
        ttk.Button(
            btns, text="Copy",
            command=lambda: _copy_to_clipboard(txt, self.app),
        ).pack(side="right", padx=(0, 4))

    def _build(self):
        self._do_auto_save()
        self.app.set_status("compiling...")

        def work():
            return self._prepare_binary(force=True)

        def done(result):
            b, err = result
            if err:
                self._handle_error(err)
            else:
                self.binary = b
                self.app.set_status(f"built: {b.name}")

        self._run_async(work, done)

    def _current_io(self):
        if not self.tests_data:
            return dict(DEFAULT_IO)
        return dict(self.tests_data.get("io") or DEFAULT_IO)

    def _run_all(self):
        if not self.tests_data:
            self.app.set_status("select a source first")
            return
        if not self.tests_data["tests"]:
            self.app.set_status("no tests")
            return

        if self._save_timer:
            self.after_cancel(self._save_timer)
            self._save_timer = None
        self._do_auto_save()

        tests = [dict(t) for t in self.tests_data["tests"]]
        total = len(tests)
        io_mode = self._current_io()
        work_root = work_root_for(self.source)
        self.app.set_status(f"building & running {total} test(s)...")

        def work():
            b, err = self._prepare_binary(force=False)
            if err:
                return {"error": err}
            results = []
            for t in tests:
                wd = work_root / f"test_{t['id']}"
                r = run_binary(
                    b, t["input"],
                    timeout=int(self.cfg.get("timeout", 5)),
                    work_dir=wd,
                    io_mode=io_mode,
                )
                ok = r["ok"] and compare(r["stdout"], t["expected"])
                results.append({
                    "id": t["id"],
                    "passed": ok,
                    "timeout": r.get("timeout", False),
                    "stdout": r["stdout"],
                    "stderr": r["stderr"],
                })
            return {"results": results}

        def done(payload):
            if payload.get("error"):
                self._handle_error(payload["error"])
                return

            results = payload["results"]
            passed = 0
            first_failed = None

            self.test_outputs = {r["id"]: r for r in results}

            for r in results:
                if r["passed"]:
                    passed += 1
                    tag, status = "pass", "PASS"
                elif r["timeout"]:
                    tag, status = "timeout", "TIMEOUT"
                    first_failed = first_failed or r
                else:
                    tag, status = "fail", "FAIL"
                    first_failed = first_failed or r
                self.tree.item(str(r["id"]), values=(r["id"], status), tags=(tag,))

            if first_failed:
                self.tree.selection_set(str(first_failed["id"]))
            elif results:
                self.tree.selection_set(str(results[0]["id"]))

            self.app.set_status(f"{passed}/{len(results)} passed")

        self._run_async(work, done)

    def _show_output(self, r):
        text = r["stdout"]
        if r["stderr"]:
            text += "\n[stderr]\n" + r["stderr"]
        _set_readonly(self.got_text, text)

    def _close_self(self):
        if not messagebox.askyesno(
            "Close tab",
            f"Close tab \u201c{self.title}\u201d?",
            parent=self,
        ):
            return
        self._do_auto_save()
        self.app.close_tab(self)


# =================================================================== RunnerApp

class RunnerApp:
    def __init__(self, root, initial_source=None):
        self.root = root
        self.cfg = _load_full_cfg()
        self.tabs = []
        self._bound = {}

        self.root.title("CP Runner")
        self.root.geometry("560x660")
        self.root.minsize(460, 500)

        self._setup_style()
        self._build_menubar()
        self._build_ui()
        self._apply_hotkeys()

        if initial_source:
            self.add_tab(Path(initial_source))
        else:
            self.add_tab()

        self.root.protocol("WM_DELETE_WINDOW", self._quit)

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

    def _build_menubar(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="New tab", accelerator="Ctrl+T", command=self.add_tab,
        )
        file_menu.add_command(
            label="Open file\u2026", accelerator="Ctrl+O", command=self._open_file,
        )
        file_menu.add_separator()

        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Recent files", menu=self.recent_menu)
        self._rebuild_recent_menu()

        file_menu.add_separator()
        file_menu.add_command(
            label="Settings\u2026", accelerator="Ctrl+,", command=self._open_settings,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Close tab", accelerator="Ctrl+W", command=self._close_current,
        )
        file_menu.add_command(
            label="Exit", accelerator="Ctrl+Q", command=self._quit,
        )
        menubar.add_cascade(label="File", menu=file_menu, underline=-1)

        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(
            label="Build", accelerator="Ctrl+B",
            command=lambda: self._dispatch_to_active("_build"),
        )
        run_menu.add_command(
            label="Run all", accelerator="F5",
            command=lambda: self._dispatch_to_active("_run_all"),
        )
        run_menu.add_separator()
        run_menu.add_command(
            label="Add test", accelerator="Ctrl+N",
            command=lambda: self._dispatch_to_active("_new_test"),
        )
        run_menu.add_command(
            label="Delete selected test", accelerator="Delete",
            command=lambda: self._dispatch_to_active("_delete_tests"),
        )
        menubar.add_cascade(label="Run", menu=run_menu, underline=-1)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu, underline=-1)

        self.root.config(menu=menubar)
        self._menubar = menubar
        self._file_menu = file_menu

    def _rebuild_recent_menu(self):
        self.recent_menu.delete(0, "end")
        items = load_history()
        if not items:
            self.recent_menu.add_command(
                label="(no recent files)", state="disabled",
            )
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
                command=(lambda p=path: self.open_path(p)) if exists else None,
            )
        self.recent_menu.add_separator()
        self.recent_menu.add_command(
            label="Clear recent",
            command=self._clear_recent,
        )

    def _clear_recent(self):
        if not messagebox.askyesno(
            "Clear history",
            "Clear all recent files?",
            parent=self.root,
        ):
            return
        clear_history()
        self._rebuild_recent_menu()
        self.set_status("history cleared")

    def _on_source_opened(self, path):
        add_to_history(path)
        self._rebuild_recent_menu()

    def open_path(self, path):
        p = Path(path)
        if not p.is_file():
            messagebox.showerror(
                "Open failed", f"File not found:\n{path}", parent=self.root,
            )
            self._rebuild_recent_menu()
            return
        self.add_tab(p)

    def _open_file(self):
        p = filedialog.askopenfilename(
            parent=self.root,
            title="Open source",
            filetypes=[("C/C++", "*.cpp *.cc *.cxx *.c"), ("All files", "*.*")],
        )
        if p:
            self.open_path(p)

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=2, pady=(2, 0))
        self.notebook.bind("<Button-2>", self._on_middle_click)
        self.notebook.bind("<Button-3>", self._on_tab_rightclick)

        self.status_var = tk.StringVar(value="ready")
        status = ttk.Label(self.root, textvariable=self.status_var,
                           style="Status.TLabel", anchor="w")
        status.grid(row=1, column=0, sticky="ew")

    # -------------------------------------------------- hotkeys

    def _apply_hotkeys(self):
        for binding in list(self._bound.values()):
            try:
                self.root.unbind(binding)
            except Exception:
                pass
        self._bound.clear()

        hotkeys = self.cfg.get("hotkeys") or DEFAULT_HOTKEYS
        for action, display in hotkeys.items():
            if not display:
                continue
            tk_binding = _parse_hotkey(display)
            if not tk_binding:
                continue
            callback = self._hotkey_callback(action)
            if callback is None:
                continue
            try:
                self.root.bind(tk_binding, callback)
                self._bound[action] = tk_binding
            except Exception:
                pass

    def _hotkey_callback(self, action):
        return {
            "new_tab":     lambda e: self._hk(self.add_tab),
            "open_file":   lambda e: self._hk(self._open_file),
            "close_tab":   lambda e: self._hk(self._close_current),
            "next_tab":    lambda e: self._hk(lambda: self._cycle_tab(1)),
            "prev_tab":    lambda e: self._hk(lambda: self._cycle_tab(-1)),
            "build":       lambda e: self._hk(lambda: self._dispatch_to_active("_build")),
            "run_all":     lambda e: self._hk(lambda: self._dispatch_to_active("_run_all")),
            "add_test":    lambda e: self._hk(lambda: self._dispatch_to_active("_new_test")),
            "delete_test": lambda e: self._hk(lambda: self._dispatch_to_active("_delete_tests")),
            "focus_next":  lambda e: self._focus_next(),
            "settings":    lambda e: self._hk(self._open_settings),
            "quit":        lambda e: self._hk(self._quit),
        }.get(action)

    def _hk(self, fn):
        fn()
        return "break"

    def _focus_next(self):
        tab = self._active_tab()
        if tab is None:
            return "break"
        focused = self.root.focus_get()
        if focused == tab.input_text:
            if str(tab.expected_text.cget("state")) != "disabled":
                tab.expected_text.focus_set()
            return "break"
        if focused == tab.expected_text:
            if str(tab.input_text.cget("state")) != "disabled":
                tab.input_text.focus_set()
            return "break"
        return "break"

    def _open_settings(self):
        SettingsDialog(self.root, self)

    def _show_about(self):
        messagebox.showinfo(
            "About CP Runner",
            "CP Runner\n\n"
            "Compile and test competitive programming solutions.\n"
            "Part of cptools.",
            parent=self.root,
        )

    def _quit(self):
        self.root.destroy()

    # -------------------------------------------------- active tab

    def _dispatch_to_active(self, method_name):
        tab = self._active_tab()
        if tab is None:
            return "break"
        getattr(tab, method_name)()
        return "break"

    def _active_tab(self):
        cur = self.notebook.select()
        if not cur:
            return None
        w = self.notebook.nametowidget(cur)
        return w if isinstance(w, SessionTab) else None

    # -------------------------------------------------- tabs

    def add_tab(self, source=None):
        tab = SessionTab(self.notebook, self, source=source)
        self.notebook.add(tab, text=tab.title)
        self.tabs.append(tab)
        self.notebook.select(tab)
        return tab

    def close_tab(self, tab):
        if len(self.tabs) <= 1:
            tab.set_source(None)
            return
        idx = self.tabs.index(tab)
        self.tabs.remove(tab)
        self.notebook.forget(tab)
        tab.destroy()
        if self.tabs:
            self.notebook.select(self.tabs[min(idx, len(self.tabs) - 1)])

    def _close_current(self):
        tab = self._active_tab()
        if tab is not None:
            tab._close_self()

    def _cycle_tab(self, delta):
        if not self.tabs:
            return
        cur = self.notebook.select()
        idx = self.notebook.index(cur)
        new = (idx + delta) % len(self.tabs)
        self.notebook.select(self.tabs[new])

    def _on_middle_click(self, event):
        try:
            idx = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return
        if 0 <= idx < len(self.tabs):
            self.tabs[idx]._close_self()

    def _on_tab_rightclick(self, event):
        try:
            idx = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="New tab", command=self.add_tab)
        menu.add_separator()
        menu.add_command(
            label="Close tab",
            command=lambda: self.tabs[idx]._close_self(),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def update_tab_title(self, tab):
        try:
            idx = self.notebook.index(tab)
        except tk.TclError:
            return
        self.notebook.tab(idx, text=tab.title)

    # -------------------------------------------------- status

    def set_status(self, msg):
        self.status_var.set(msg)


def launch(initial_source=None):
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.15)
    except Exception:
        pass
    RunnerApp(root, initial_source=initial_source)
    root.mainloop()
    return 0