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
        return 0 if argv else 2
    if len(argv) < 2:
        print("usage: add <name> <path>", file=sys.stderr)
        return 2
    name = argv[0]
    raw = " ".join(argv[1:])
    if not name or name.startswith("@"):
        print("invalid name", file=sys.stderr)
        return 2
    if name in folders.list_names():
        print(f"folder '{name}' already exists", file=sys.stderr)
        return 1
    folders.set_folder(name, raw)
    if AS_JSON:
        emit_json({"ok": True, "name": name, "path": raw})
    else:
        print(f"added: {name} -> {raw}")
    return 0


def cmd_remove(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: remove <name>")
        return 0 if argv else 2
    name = argv[0]
    if name not in folders.list_names():
        print(f"not found: {name}", file=sys.stderr)
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
    old, new = argv[0], argv[1]
    if old not in folders.list_names():
        print(f"not found: {old}", file=sys.stderr)
        return 1
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
    name = argv[0]
    data = folders.load()
    raw = data["folders"].get(name)
    if raw is None:
        print(f"not found: {name}", file=sys.stderr)
        return 1
    resolved = folders.resolve_ref("@" + name)
    if AS_JSON:
        emit_json({"name": name, "path": str(resolved)})
    else:
        print(resolved)
    return 0


def cmd_open(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: open <name> [<name2> ...]")
        return 0 if argv else 2
    names = argv
    missing = [n for n in names if n not in folders.list_names()]
    if missing:
        for n in missing:
            print(f"not found: {n}", file=sys.stderr)
        return 1
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
    name = argv[0]
    if name not in folders.list_names():
        print(f"not found: {name}", file=sys.stderr)
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
  cpt folders remove <name>                 unregister
  cpt folders rename <old> <new>            rename
  cpt folders show <name>                   print path
  cpt folders open <name> [<name2> ...]     open one or more
  cpt folders open-all                      open all at once
  cpt folders default [<name>]              get or set default
  cpt folders resolve <@name>[/sub]         resolve a reference
  cpt folders config [show|reset]

reference syntax (for other plugins):
  @name          path of folder "name"
  @name/sub      path of folder joined with "sub"

storage:
  <config_root>/plugins/folders/folders.json
""")


COMMANDS = {
    "list": cmd_list,
    "ls": cmd_list,
    "add": cmd_add,
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