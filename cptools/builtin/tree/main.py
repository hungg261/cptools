import argparse
import json
import os
import sys
from pathlib import Path

from walker import walk
from render import render

def _user_cwd():
    return Path(os.environ.get("CPTOOLS_CWD") or os.getcwd())


def _stdout_utf8():
    enc = (sys.stdout.encoding or "").lower().replace("-", "")
    return enc in ("utf8", "utf8mb4", "utf8mb4")

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CONFIG_DIR = Path(os.environ["CPTOOLS_PLUGIN_CONFIG_DIR"])
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "default_excludes": ["__pycache__", "node_modules", ".venv", "venv", "*.pyc"],
    "max_depth": 0,
    "show_hidden": False,
}


def load_config():
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    cfg = dict(DEFAULTS)
    cfg.update(data)
    return cfg


def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def pick_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as e:
        print(f"tkinter not available: {e}", file=sys.stderr)
        return None

    try:
        root = tk.Tk()
    except Exception as e:
        print(f"cannot open dialog: {e}", file=sys.stderr)
        return None

    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        picked = filedialog.askdirectory()
    finally:
        root.destroy()
    return picked or None


def cmd_show(argv):
    parser = argparse.ArgumentParser(add_help=False, prog="cpt tree")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("-s", "--simple", action="store_true")
    parser.add_argument("-d", "--depth", type=int, default=None)
    parser.add_argument("-e", "--exclude", action="append", default=[])
    parser.add_argument("-a", "--all", action="store_true", dest="show_hidden")
    parser.add_argument("--pick", action="store_true")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    cfg = load_config()

    if ns.pick:
        picked = pick_folder()
        if not picked:
            print("cancelled", file=sys.stderr)
            return 1
        target = Path(picked)
    else:
        target = Path(ns.path).expanduser()
        if not target.is_absolute():
            target = _user_cwd() / target
        target = target.resolve()

    if not target.exists():
        print(f"not found: {target}", file=sys.stderr)
        return 1

    excludes = list(cfg.get("default_excludes") or []) + list(ns.exclude or [])
    max_depth = ns.depth if ns.depth is not None else int(cfg.get("max_depth") or 0)
    show_hidden = bool(ns.show_hidden or cfg.get("show_hidden"))

    entries = walk(target, excludes=excludes, max_depth=max_depth, show_hidden=show_hidden)
    simple = ns.simple or not _stdout_utf8()
    print(render(entries, simple=simple))
    return 0


def cmd_config(argv):
    cfg = load_config()

    if not argv or argv[0] in ("show", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print_config_help()
            return 0
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0

    sub = argv[0]

    if sub == "exclude":
        return _config_exclude(cfg, argv[1:])

    if sub == "set":
        if len(argv) < 3:
            print("usage: config set <key> <value>", file=sys.stderr)
            return 2
        key = argv[1]
        value = argv[2]
        if key == "max_depth":
            try:
                cfg["max_depth"] = int(value)
            except ValueError:
                print("max_depth must be int", file=sys.stderr)
                return 2
        elif key == "show_hidden":
            cfg["show_hidden"] = value.lower() in ("1", "true", "yes", "on")
        elif key == "default_excludes":
            print("use 'config exclude' to manage excludes", file=sys.stderr)
            return 2
        else:
            print(f"unknown key: {key}", file=sys.stderr)
            return 2
        save_config(cfg)
        print(f"{key} = {cfg[key]}")
        return 0

    if sub == "reset":
        save_config(dict(DEFAULTS))
        print("reset to defaults")
        return 0

    print(f"unknown: config {sub}", file=sys.stderr)
    return 2


def _config_exclude(cfg, argv):
    if not argv or argv[0] == "list":
        for p in cfg.get("default_excludes") or []:
            print(p)
        return 0

    if argv[0] == "add":
        if len(argv) < 2:
            print("usage: config exclude add <pattern>", file=sys.stderr)
            return 2
        pat = argv[1]
        lst = list(cfg.get("default_excludes") or [])
        if pat in lst:
            print(f"already excluded: {pat}")
            return 0
        lst.append(pat)
        cfg["default_excludes"] = lst
        save_config(cfg)
        print(f"added: {pat}")
        return 0

    if argv[0] == "remove":
        if len(argv) < 2:
            print("usage: config exclude remove <pattern>", file=sys.stderr)
            return 2
        pat = argv[1]
        lst = list(cfg.get("default_excludes") or [])
        if pat not in lst:
            print(f"not found: {pat}", file=sys.stderr)
            return 1
        lst.remove(pat)
        cfg["default_excludes"] = lst
        save_config(cfg)
        print(f"removed: {pat}")
        return 0

    if argv[0] == "clear":
        cfg["default_excludes"] = []
        save_config(cfg)
        print("cleared")
        return 0

    print(f"unknown: config exclude {argv[0]}", file=sys.stderr)
    return 2


def print_config_help():
    print("""usage: cpt tree config <subcommand>

  show                     print current config
  set <key> <value>        set a key (max_depth, show_hidden)
  reset                    reset all to defaults
  exclude list             list exclude patterns
  exclude add <pattern>    add a pattern
  exclude remove <pattern> remove a pattern
  exclude clear            remove all patterns
""")


def print_help():
    print("""tree - show directory tree

usage:
  cpt tree [path] [opts]                show tree of path (default: .)
  cpt tree --pick [opts]                pick a folder interactively
  cpt tree config <subcommand>          manage settings

options:
  -s, --simple           use ASCII characters (+-- `-- |)
  -d, --depth N          limit recursion depth (0 = unlimited)
  -e, --exclude PATTERN  exclude matching files/dirs (repeatable)
  -a, --all              include hidden files (dotfiles)
  --pick                 open a folder picker dialog

examples:
  cpt tree
  cpt tree . -d 3
  cpt tree D:\\Projects -e "*.pyc" -e "__pycache__"
  cpt tree --simple --pick
""")


COMMANDS = {
    "config": cmd_config,
    "show": cmd_show,
}


def main(argv):
    if not argv:
        return cmd_show([])
    if argv[0] in ("-h", "--help"):
        print_help()
        return 0
    cmd = argv[0]
    if cmd in COMMANDS:
        return COMMANDS[cmd](argv[1:])
    return cmd_show(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))