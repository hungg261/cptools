import argparse
import json
import os
import sys
from pathlib import Path

from cptools.lib import folders
from cptools.lib.open import open_folder

AS_JSON = os.environ.get("CPTOOLS_OUTPUT") == "json"


def emit_json(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _confirm(msg):
    try:
        ans = input(f"{msg} [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def _resolve_or_report(query, cmd_name):
    """Fuzzy resolve. Returns name or None. Prints messages on failure."""
    name, result = folders.path_of(query)
    if name is not None:
        return name
    if isinstance(result, list) and result:
        print(f"'{query}' is ambiguous. candidates:", file=sys.stderr)
        for c in result:
            print(f"  {c}", file=sys.stderr)
        return None
    print(f"not found: {query}", file=sys.stderr)
    return None


def _interactive_select(multi=False):
    """Questionary-based picker. Returns list of names (possibly empty)."""
    names = folders.list_names()
    if not names:
        return []
    try:
        import questionary
    except ImportError:
        return []

    data = folders.load()
    default = data.get("default", "")
    choices = []
    for n in names:
        path = folders.get_path(n)
        label = f"{n}  ({path})"
        if n == default:
            label = "★ " + label
        choices.append(questionary.Choice(title=label, value=n))

    if multi:
        result = questionary.checkbox("Select folder(s):", choices=choices).ask()
        if result is None:
            return []
        return list(result)
    else:
        result = questionary.select("Select folder:", choices=choices).ask()
        if result is None:
            return []
        return [result]


def cmd_list(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("usage: list")
        return 0
    data = folders.load()
    default = data.get("default", "")
    items = sorted(data["folders"].items())
    if AS_JSON:
        emit_json({
            "default": default,
            "folders": [{"name": n, "path": p} for n, p in items],
        })
        return 0
    if not items:
        print("no folders registered")
        print('add one: cpt folders add <name> "<path>"')
        return 0
    width = max((len(n) for n, _ in items), default=1)
    for name, raw in items:
        mark = "*" if name == default else " "
        try:
            resolved = folders.resolve_ref("@" + name)
            suffix = "" if str(resolved) == raw else f"  -> {resolved}"
        except Exception:
            suffix = ""
        print(f"{mark} {name:<{width}}  {raw}{suffix}")
    print()
    print("* = default")
    return 0


def cmd_add(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: add <name> <path>")
        print("       add <name> --pick")
        return 0 if argv else 2

    parser = argparse.ArgumentParser(add_help=False, prog="cpt folders add")
    parser.add_argument("name")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--pick", action="store_true")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    name = ns.name
    if not name or name.startswith("@"):
        print("invalid name", file=sys.stderr)
        return 2
    if name in folders.list_names():
        print(f"folder '{name}' already exists", file=sys.stderr)
        return 1

    if ns.pick:
        picked = _pick_directory()
        if not picked:
            print("cancelled")
            return 0
        raw = picked
    elif ns.path:
        raw = ns.path
    else:
        print("usage: add <name> <path>", file=sys.stderr)
        print("       add <name> --pick", file=sys.stderr)
        return 2

    folders.set_folder(name, raw)
    if AS_JSON:
        emit_json({"ok": True, "name": name, "path": raw})
    else:
        print(f"added: {name} -> {raw}")
    return 0


def _pick_directory():
    if not sys.stdin.isatty():
        print("no interactive terminal; use <path> instead", file=sys.stderr)
        return None
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("tkinter not available", file=sys.stderr)
        return None
    try:
        root = tk.Tk()
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
    except Exception as e:
        print(f"cannot open dialog: {e}", file=sys.stderr)
        return None


def cmd_pick(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("usage: pick")
        return 0

    picked = _pick_directory()
    if not picked:
        print("cancelled")
        return 0

    default_name = Path(picked).name or "folder"
    try:
        import questionary
        name = questionary.text(
            f"Name for '{picked}':", default=default_name,
        ).ask()
    except Exception:
        try:
            name = input(f"Name for '{picked}' [{default_name}]: ").strip()
            if not name:
                name = default_name
        except EOFError:
            name = default_name

    if not name:
        print("aborted")
        return 0
    name = name.strip()
    if name.startswith("@") or not name:
        print("invalid name", file=sys.stderr)
        return 2
    if name in folders.list_names():
        print(f"folder '{name}' already exists", file=sys.stderr)
        return 1

    folders.set_folder(name, picked)
    print(f"added: {name} -> {picked}")
    return 0


def cmd_remove(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: remove <name>")
        return 0 if argv else 2
    name = _resolve_or_report(argv[0], "remove")
    if name is None:
        return 1
    if not _confirm(f"Remove folder '{name}' from list? (files are not touched)"):
        print("aborted")
        return 0
    folders.remove_folder(name)
    print(f"removed: {name}")
    return 0


def cmd_rename(argv):
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print("usage: rename <old> <new>")
        return 0 if (argv and argv[0] in ("-h", "--help")) else 2
    old = _resolve_or_report(argv[0], "rename")
    if old is None:
        return 1
    new = argv[1]
    if new in folders.list_names():
        print(f"'{new}' already exists", file=sys.stderr)
        return 1
    folders.rename_folder(old, new)
    print(f"renamed: {old} -> {new}")
    return 0


def cmd_show(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: show <name>")
        return 0 if argv else 2
    name = _resolve_or_report(argv[0], "show")
    if name is None:
        return 1
    resolved = folders.resolve_ref("@" + name)
    if AS_JSON:
        emit_json({"name": name, "path": str(resolved)})
    else:
        print(resolved)
    return 0


def cmd_open(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("usage: open [<name> ...]")
        return 0

    if not argv:
        if not sys.stdin.isatty():
            print("usage: open <name> [<name2> ...]", file=sys.stderr)
            return 2
        chosen = _interactive_select(multi=True)
        if not chosen:
            print("nothing selected")
            return 0
        names = chosen
    else:
        names = []
        for q in argv:
            n = _resolve_or_report(q, "open")
            if n is None:
                return 1
            names.append(n)

    opened = 0
    for name in names:
        p = folders.resolve_ref("@" + name)
        if p is None:
            print(f"cannot resolve: {name}", file=sys.stderr)
            continue
        p.mkdir(parents=True, exist_ok=True)
        try:
            open_folder(p)
            opened += 1
            if not AS_JSON:
                print(f"opened: {name} -> {p}")
        except Exception as e:
            print(f"failed: {name}: {e}", file=sys.stderr)
    if AS_JSON:
        emit_json({"ok": opened == len(names), "opened": opened})
    return 0 if opened == len(names) else 1


def cmd_open_all(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("usage: open-all")
        return 0
    names = folders.list_names()
    if not names:
        print("no folders registered")
        return 0
    for name in names:
        p = folders.resolve_ref("@" + name)
        if p is None:
            continue
        p.mkdir(parents=True, exist_ok=True)
        try:
            open_folder(p)
            if not AS_JSON:
                print(f"opened: {name} -> {p}")
        except Exception as e:
            print(f"failed: {name}: {e}", file=sys.stderr)
    if AS_JSON:
        emit_json({"ok": True, "count": len(names)})
    return 0


def cmd_default(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("usage: default [<name>]")
        return 0
    if not argv:
        cur = folders.get_default()
        if AS_JSON:
            emit_json({"default": cur})
        else:
            print(cur or "(none)")
        return 0
    name = _resolve_or_report(argv[0], "default")
    if name is None:
        return 1
    folders.set_default(name)
    print(f"default = {name}")
    return 0


def cmd_resolve(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: resolve <@name>[/sub]")
        return 0 if argv else 2
    ref = argv[0]
    p = folders.resolve_ref(ref)
    if p is None:
        print(f"cannot resolve: {ref}", file=sys.stderr)
        return 1
    if AS_JSON:
        emit_json({"ref": ref, "path": str(p)})
    else:
        print(p)
    return 0


def cmd_config(argv):
    if not argv or argv[0] in ("show", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("usage: config [show | reset]")
            return 0
        data = folders.load()
        if AS_JSON:
            emit_json(data)
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    sub = argv[0]
    if sub == "reset":
        folders.save({"folders": {}, "default": ""})
        print("reset")
        return 0
    print(f"unknown: config {sub}", file=sys.stderr)
    return 2


def print_help():
    print("""folders - manage named folders

usage:
  cpt folders list                          list all folders
  cpt folders add <name> <path>             register a folder
  cpt folders add <name> --pick             pick path via dialog
  cpt folders pick                          dialog + name prompt
  cpt folders remove <name>                 unregister (fuzzy)
  cpt folders rename <old> <new>            rename (fuzzy old)
  cpt folders show <name>                   print path (fuzzy)
  cpt folders open [<name> ...]             open one or more
                                            (no arg = interactive picker)
  cpt folders open-all                      open all at once
  cpt folders default [<name>]              get or set default
  cpt folders resolve <@name>[/sub]         resolve a reference
  cpt folders config [show|reset]

reference syntax (for other plugins):
  @name          path of folder "name"
  @name/sub      path of folder joined with "sub"

names are fuzzy-matched: typos and prefixes are ok when unambiguous.

storage:
  <config_root>/plugins/folders/folders.json
""")


COMMANDS = {
    "list": cmd_list,
    "ls": cmd_list,
    "add": cmd_add,
    "pick": cmd_pick,
    "remove": cmd_remove,
    "rm": cmd_remove,
    "rename": cmd_rename,
    "mv": cmd_rename,
    "show": cmd_show,
    "open": cmd_open,
    "open-all": cmd_open_all,
    "default": cmd_default,
    "resolve": cmd_resolve,
    "config": cmd_config,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print_help()
        return 0
    cmd = argv[0]
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print_help()
        return 2
    return COMMANDS[cmd](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))