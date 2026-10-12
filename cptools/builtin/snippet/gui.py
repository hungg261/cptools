import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from cptools import paths
from cptools.lib import clipboard
from cptools.lib import editor_registry
from cptools.lib import snippets
from cptools.lib.open import open_file, open_folder, reveal_file


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

FG_MUTED = "#666666"

DEFAULT_HOTKEYS = {
    "copy":     "Ctrl+C",
    "edit":     "Ctrl+E",
    "rename":   "F2",
    "delete":   "Delete",
    "add":      "Ctrl+N",
    "search":   "Ctrl+F",
    "refresh":  "F5",
    "settings": "Ctrl+comma",
    "quit":     "Ctrl+Q",
}

HOTKEY_ACTIONS = [
    ("copy",     "Copy snippet"),
    ("edit",     "Edit snippet"),
    ("rename",   "Rename snippet"),
    ("delete",   "Delete snippet"),
    ("add",      "Add file"),
    ("search",   "Focus search"),
    ("refresh",  "Refresh list"),
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


def _config_file() -> Path:
    return paths.plugin_config_dir("snippet") / "config.json"


def _load_full_cfg() -> dict:
    f = _config_file()
    data = {}
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("root_dir", "")
    data.setdefault("ignore", [])
    data.setdefault("suppress_edit_warning", False)
    data.setdefault("suppress_copy_message", False)
    hk = dict(DEFAULT_HOTKEYS)
    user_hk = data.get("hotkeys") or {}
    if isinstance(user_hk, dict):
        for k, v in user_hk.items():
            if k in DEFAULT_HOTKEYS and isinstance(v, str):
                hk[k] = v
    data["hotkeys"] = hk
    return data


def _save_full_cfg(cfg: dict) -> None:
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


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


# ---------------------------------------------------------------- SettingsDialog

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Settings")
        self.geometry("520x560")
        self.transient(parent)
        self.minsize(460, 500)

        self.cfg = dict(app.cfg)
        self._hotkeys = dict(app.cfg.get("hotkeys") or DEFAULT_HOTKEYS)

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        btns = ttk.Frame(outer)
        btns.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(btns, text="Reset", command=self._reset).pack(side="left")
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=(0, 4))

        t1 = ttk.LabelFrame(outer, text=" Editor ", padding=(8, 6))
        t1.pack(fill="x", pady=(0, 6))

        f = ttk.Frame(t1)
        f.pack(fill="x", pady=2)
        ttk.Label(f, text="Default editor", width=18, anchor="w").pack(side="left")

        editors = editor_registry.list_editors()
        self.editor_keys = editor_registry.ordered_keys(editors) if editors else []
        editor_labels = [
            f"{editor_registry.label_for(k)} ({k})" for k in self.editor_keys
        ]
        cur = editor_registry.get_default()
        cur_label = "(system default)"
        for k, lbl in zip(self.editor_keys, editor_labels):
            if k == cur:
                cur_label = lbl
                break
        self.editor_var = tk.StringVar(value=cur_label)
        self.editor_combo = ttk.Combobox(
            f, textvariable=self.editor_var,
            values=["(system default)"] + editor_labels,
            state="readonly", width=32,
        )
        self.editor_combo.pack(side="left", fill="x", expand=True)

        t2 = ttk.LabelFrame(outer, text=" Popups ", padding=(8, 6))
        t2.pack(fill="x", pady=(0, 6))

        self.suppress_edit_var = tk.BooleanVar(
            value=bool(self.cfg.get("suppress_edit_warning", False))
        )
        ttk.Checkbutton(
            t2, text="Don't warn before opening in external editor",
            variable=self.suppress_edit_var,
        ).pack(anchor="w")

        self.suppress_copy_var = tk.BooleanVar(
            value=bool(self.cfg.get("suppress_copy_message", False))
        )
        ttk.Checkbutton(
            t2, text="Don't show popup after copy",
            variable=self.suppress_copy_var,
        ).pack(anchor="w")

        t3 = ttk.LabelFrame(outer, text=" Hotkeys ", padding=(8, 6))
        t3.pack(fill="both", expand=True, pady=(0, 6))

        hk_frame = ttk.Frame(t3)
        hk_frame.pack(fill="both", expand=True)
        self.hk_tree = ttk.Treeview(
            hk_frame, columns=("action", "binding"),
            show="headings", selectmode="browse", height=8,
        )
        self.hk_tree.heading("action", text="Action")
        self.hk_tree.heading("binding", text="Binding")
        self.hk_tree.column("action", width=200, anchor="w")
        self.hk_tree.column("binding", width=180, anchor="w")
        self.hk_tree.pack(fill="both", expand=True)
        self.hk_tree.bind("<Double-1>", lambda e: self._edit_hotkey())
        ttk.Label(
            t3, text="Double-click a row to rebind",
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
        self.editor_var.set("(system default)")
        self.suppress_edit_var.set(False)
        self.suppress_copy_var.set(False)
        self._hotkeys = dict(DEFAULT_HOTKEYS)
        self._populate_hotkeys()

    def _save(self):
        chosen = self.editor_var.get()
        if chosen != "(system default)":
            for k in self.editor_keys:
                lbl = editor_registry.label_for(k)
                if chosen.startswith(f"{lbl} ("):
                    editor_registry.set_default(k)
                    break
        self.cfg["suppress_edit_warning"] = self.suppress_edit_var.get()
        self.cfg["suppress_copy_message"] = self.suppress_copy_var.get()
        self.cfg["hotkeys"] = dict(self._hotkeys)
        self.app.cfg = dict(self.cfg)
        _save_full_cfg(self.app.cfg)
        self.app._apply_hotkeys()
        self.app.set_status("settings saved")
        self.destroy()


# ---------------------------------------------------------------- SnippetApp

class SnippetApp:
    def __init__(self, root):
        self.root = root
        self.cfg = _load_full_cfg()
        self.current_path = None
        self._all_files = []
        self._bound = {}

        self.root.title("Snippets")
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            w = min(760, int(sw * 0.9))
            h = min(560, int(sh * 0.75))
            x = max(20, (sw - w) // 2)
            y = max(20, (sh - h) // 8)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.root.geometry("760x560")
        self.root.minsize(600, 420)

        self._setup_style()
        self._build_menubar()
        self._build_ui()
        self._apply_hotkeys()

        self.refresh_list()
        self._update_status()

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
        style.configure("Treeview", font=UI, rowheight=21)
        style.configure("Treeview.Heading", font=(UI_FONT, 9))
        style.configure("Status.TLabel", font=UI_SMALL, padding=(4, 2),
                        foreground=FG_MUTED)

    def _build_menubar(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Add file\u2026", accelerator="Ctrl+N", command=self._add_file,
        )
        file_menu.add_command(
            label="Change root folder\u2026", command=self._change_root,
        )
        file_menu.add_command(
            label="Open root folder", command=self._open_folder,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Settings\u2026", accelerator="Ctrl+,",
            command=self._open_settings,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit", accelerator="Ctrl+Q", command=self.root.destroy,
        )
        menubar.add_cascade(label="File", menu=file_menu, underline=-1)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(
            label="Refresh", accelerator="F5", command=self.refresh_list,
        )
        view_menu.add_command(
            label="Focus search", accelerator="Ctrl+F",
            command=lambda: self.search_entry.focus_set(),
        )
        menubar.add_cascade(label="View", menu=view_menu, underline=-1)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu, underline=-1)

        self.root.config(menu=menubar)

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=(6, 6, 6, 0))
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Search", width=7).grid(row=0, column=0, sticky="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        self.search_entry = ttk.Entry(top, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        self.search_entry.bind("<Return>", lambda e: self._focus_tree())
        self.search_entry.bind("<Escape>", lambda e: self._focus_tree())
        ttk.Button(top, text="Clear", width=6,
                   command=lambda: self.search_var.set("")).grid(row=0, column=2, padx=(0, 4))
        ttk.Button(top, text="+ Add", width=8,
                   command=self._add_file).grid(row=0, column=3)

        main = ttk.Frame(self.root, padding=(6, 6, 6, 0))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(left, columns=("name",), show="headings",
                                 selectmode="browse")
        self.tree.heading("name", text="Name")
        self.tree.column("name", width=200, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        header = ttk.Frame(right)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        self.preview_label = ttk.Label(header, text="(no snippet selected)",
                                       font=UI_SMALL, foreground=FG_MUTED)
        self.preview_label.grid(row=0, column=0, sticky="w")

        preview_wrap = ttk.Frame(right)
        preview_wrap.grid(row=1, column=0, sticky="nsew", pady=(2, 0))
        preview_wrap.columnconfigure(0, weight=1)
        preview_wrap.rowconfigure(0, weight=1)

        self.preview_text = tk.Text(
            preview_wrap, wrap="none", font=MONO, state="disabled",
            undo=False, padx=4, pady=3,
        )
        self.preview_text.grid(row=0, column=0, sticky="nsew")

        vbar = ttk.Scrollbar(preview_wrap, orient="vertical",
                             command=self.preview_text.yview)
        vbar.grid(row=0, column=1, sticky="ns")
        hbar = ttk.Scrollbar(preview_wrap, orient="horizontal",
                             command=self.preview_text.xview)
        hbar.grid(row=1, column=0, sticky="ew")
        self.preview_text.configure(
            yscrollcommand=vbar.set, xscrollcommand=hbar.set,
        )

        action = ttk.Frame(self.root, padding=(6, 6, 6, 0))
        action.grid(row=2, column=0, sticky="ew")

        ttk.Button(action, text="Copy", width=8,
                   command=self._copy).pack(side="left")
        ttk.Button(action, text="Edit", width=8,
                   command=self._edit).pack(side="left", padx=(4, 0))
        ttk.Button(action, text="Rename", width=8,
                   command=self._rename).pack(side="left", padx=(4, 0))
        ttk.Button(action, text="Delete", width=8,
                   command=self._delete).pack(side="left", padx=(4, 0))
        ttk.Button(action, text="Reveal", width=8,
                   command=self._reveal).pack(side="left", padx=(4, 0))

        self.status_var = tk.StringVar(value="ready")
        status = ttk.Label(self.root, textvariable=self.status_var,
                           style="Status.TLabel", anchor="w")
        status.grid(row=3, column=0, sticky="ew")

        self.root.bind("<Escape>", lambda e: self._focus_tree())

    # ------------------------------------------------------ hotkeys

    def _apply_hotkeys(self):
        for binding in list(self._bound.values()):
            try:
                self.root.unbind(binding)
            except Exception:
                pass
        self._bound.clear()
        hk = self.cfg.get("hotkeys") or DEFAULT_HOTKEYS
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
            "copy":     self._hk_copy,
            "edit":     lambda e: self._hk(self._edit),
            "rename":   lambda e: self._hk(self._rename),
            "delete":   lambda e: self._hk(self._delete),
            "add":      lambda e: self._hk(self._add_file),
            "search":   lambda e: self._hk(lambda: self.search_entry.focus_set()),
            "refresh":  lambda e: self._hk(self.refresh_list),
            "settings": lambda e: self._hk(self._open_settings),
            "quit":     lambda e: self._hk(self.root.destroy),
        }.get(action)

    def _hk(self, fn):
        fn()
        return "break"

    def _hk_copy(self, event=None):
        focused = self.root.focus_get()
        if isinstance(focused, tk.Text):
            return None
        self._copy()
        return "break"

    def _focus_tree(self):
        children = self.tree.get_children()
        if children:
            first = children[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
            self.tree.see(first)
        self.tree.focus_set()
        return "break"

    # ------------------------------------------------------ data

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        try:
            self._all_files = snippets.iter_all()
        except Exception:
            self._all_files = []

        query = self.search_var.get().strip().lower()
        filtered = self._all_files
        if query:
            filtered = [f for f in self._all_files
                        if query in snippets.relpath(f).lower()]

        for f in filtered:
            self.tree.insert("", "end", iid=str(f), values=(snippets.relpath(f),))

        if not self.tree.get_children():
            self.current_path = None
            self._set_preview(None)
        else:
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)

        self._update_status()

    def _on_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self.current_path = None
            self._set_preview(None)
            return
        self.current_path = Path(sel[0])
        self._set_preview(self.current_path)

    def _set_preview(self, path):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        if path is None or not path.is_file():
            self.preview_text.configure(state="disabled")
            self.preview_label.configure(text="(no snippet selected)")
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            text = f"<cannot read: {e}>"
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state="disabled")
        self.preview_label.configure(text=snippets.relpath(path))

    def _update_status(self):
        root = snippets.root_dir()
        n = len(self._all_files)
        self.status_var.set(f"root: {root}  \u00b7  {n} snippet(s)")

    # ------------------------------------------------------ actions

    def _get_selected(self):
        if self.current_path is None or not self.current_path.is_file():
            self.set_status("no snippet selected")
            return None
        return self.current_path

    def _copy(self):
        p = self._get_selected()
        if p is None:
            return
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            messagebox.showerror("Error", str(e), parent=self.root)
            return
        ok = clipboard.copy(text)
        rel = snippets.relpath(p)
        if ok:
            self.set_status(f"copied: {rel}")
            if not self.cfg.get("suppress_copy_message"):
                messagebox.showinfo(
                    "Copied", f"Copied '{rel}' to clipboard.",
                    parent=self.root,
                )
        else:
            self.set_status("clipboard not available")
            messagebox.showwarning(
                "Clipboard",
                "Clipboard is not available on this system.",
                parent=self.root,
            )

    def _edit(self):
        p = self._get_selected()
        if p is None:
            return

        if not self.cfg.get("suppress_edit_warning"):
            ok = messagebox.askokcancel(
                "Open in editor",
                f"Open {snippets.relpath(p)} in external editor?\n\n"
                "Changes are saved directly to disk "
                "(this is not a separate buffer).",
                parent=self.root,
            )
            if not ok:
                return

        editors = editor_registry.list_editors()
        default = editor_registry.get_default()

        order = []
        if default and default in editors:
            order.append(default)
        for k in editor_registry.ordered_keys(editors):
            if k not in order:
                order.append(k)

        for k in order:
            try:
                if editor_registry.launch(k, p):
                    self.set_status(f"opened in {k}: {snippets.relpath(p)}")
                    return
            except Exception:
                continue

        open_file(p)
        self.set_status(f"opened with system default: {snippets.relpath(p)}")

    def _rename(self):
        p = self._get_selected()
        if p is None:
            return
        old_rel = snippets.relpath(p)
        new_name = simpledialog.askstring(
            "Rename snippet",
            f"Rename {old_rel} on disk.\n"
            "Enter new relative path (directories created if needed):",
            initialvalue=old_rel, parent=self.root,
        )
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_rel:
            return
        try:
            result = snippets.rename(old_rel, new_name)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)
            return
        if result is None:
            messagebox.showerror(
                "Rename failed",
                f"Target exists or invalid name: {new_name}",
                parent=self.root,
            )
            return
        self.set_status(f"renamed: {old_rel} -> {new_name}")
        self.refresh_list()

    def _delete(self):
        p = self._get_selected()
        if p is None:
            return
        rel = snippets.relpath(p)
        if not messagebox.askyesno(
            "Delete snippet",
            f"Delete {rel} from disk?\n\nThis cannot be undone.",
            parent=self.root,
        ):
            return
        try:
            ok = snippets.remove(rel)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)
            return
        if not ok:
            messagebox.showerror("Delete failed", rel, parent=self.root)
            return
        self.set_status(f"deleted: {rel}")
        self.refresh_list()

    def _reveal(self):
        p = self._get_selected()
        if p is None:
            return
        reveal_file(p)
        self.set_status(f"revealed: {snippets.relpath(p)}")

    def _add_file(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Add snippet file",
            filetypes=[("All files", "*.*")],
        )
        if not path:
            return
        src = Path(path)
        try:
            dest = snippets.add_file(src)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)
            return
        self.set_status(f"added: {dest.name}")
        self.refresh_list()

    def _change_root(self):
        current = snippets.root_dir()
        chosen = filedialog.askdirectory(
            parent=self.root, title="Choose snippets root folder",
            initialdir=str(current) if current.is_dir() else None,
        )
        if not chosen:
            return
        chosen_path = Path(chosen).resolve()
        self.cfg["root_dir"] = str(chosen_path)
        _save_full_cfg(self.cfg)
        self.set_status(f"root changed: {chosen_path}")
        self.refresh_list()

    def _open_folder(self):
        root = snippets.root_dir()
        root.mkdir(parents=True, exist_ok=True)
        open_folder(root)
        self.set_status(f"opened: {root}")

    def _open_settings(self):
        SettingsDialog(self.root, self)

    def _show_about(self):
        messagebox.showinfo(
            "About Snippets",
            "Snippet manager\n\n"
            "Files in a configurable root folder.\n"
            "Copy snippets to clipboard for quick paste.\n"
            "Part of cptools.",
            parent=self.root,
        )

    def set_status(self, msg):
        self.status_var.set(msg)


def launch():
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.15)
    except Exception:
        pass
    SnippetApp(root)
    root.mainloop()
    return 0