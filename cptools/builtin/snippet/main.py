import argparse
import json
import os
import sys
from pathlib import Path

from cptools.lib import clipboard
from cptools.lib import snippets
from cptools.lib import editor_registry

AS_JSON = os.environ.get("CPTOOLS_OUTPUT") == "json"


def emit_json(obj):
    print(json.dumps(obj, ensure_ascii=False))


def _ambiguous_or_missing(name):
    cands = snippets.resolve_all(name)
    if len(cands) > 1:
        print(f"ambiguous name '{name}'. candidates:", file=sys.stderr)
        for c in cands:
            print(f"  {snippets.relpath(c)}", file=sys.stderr)
    else:
        print(f"not found: {name}", file=sys.stderr)


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
    root = snippets.root_dir()
    files = snippets.iter_all()
    if AS_JSON:
        for f in files:
            emit_json({"name": snippets.relpath(f), "path": str(f)})
        return 0
    if not files:
        print(f"no snippets (root: {root})")
        return 0
    for f in files:
        print(snippets.relpath(f))
    return 0


def cmd_show(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: show <name>")
        return 0 if argv else 2
    name = argv[0]
    text = snippets.read(name)
    if text is None:
        _ambiguous_or_missing(name)
        return 1
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def cmd_copy(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: copy <name>")
        return 0 if argv else 2
    name = argv[0]
    text = snippets.read(name)
    if text is None:
        _ambiguous_or_missing(name)
        return 1
    ok = clipboard.copy(text)
    if not ok:
        print("clipboard not available", file=sys.stderr)
        return 1
    p = snippets.resolve(name)
    if AS_JSON:
        emit_json({"ok": True, "name": snippets.relpath(p)})
    else:
        print(f"copied: {snippets.relpath(p)}")
    return 0


def cmd_add(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("usage: add <file> [--name NAME]")
        return 0
    parser = argparse.ArgumentParser(add_help=False, prog="cpt snip add")
    parser.add_argument("src")
    parser.add_argument("--name", "-n", default=None)
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2
    src = Path(ns.src).expanduser()
    if not src.is_file():
        print(f"not a file: {src}", file=sys.stderr)
        return 1
    try:
        dest = snippets.add_file(src, as_name=ns.name)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if AS_JSON:
        emit_json({"ok": True, "path": str(dest)})
    else:
        print(f"added: {dest}")
    return 0


def cmd_remove(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: remove <name>")
        return 0 if argv else 2
    name = argv[0]
    p = snippets.resolve(name)
    if p is None:
        _ambiguous_or_missing(name)
        return 1
    if not _confirm(f"Delete {snippets.relpath(p)}?"):
        print("aborted")
        return 0
    if not snippets.remove(name):
        print("failed to delete", file=sys.stderr)
        return 1
    print(f"removed: {snippets.relpath(p)}")
    return 0


def cmd_rename(argv):
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print("usage: rename <old> <new>")
        return 0 if (argv and argv[0] in ("-h", "--help")) else 2
    old, new = argv[0], argv[1]
    p = snippets.resolve(old)
    if p is None:
        _ambiguous_or_missing(old)
        return 1
    old_rel = snippets.relpath(p)
    dst = snippets.rename(old, new)
    if dst is None:
        print("cannot rename: target exists or invalid name", file=sys.stderr)
        return 1
    print(f"renamed: {old_rel} -> {snippets.relpath(dst)}")
    return 0


def cmd_edit(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: edit <name>")
        return 0 if argv else 2
    name = argv[0]
    p = snippets.resolve(name)
    if p is None:
        _ambiguous_or_missing(name)
        return 1

    key = editor_registry.get_default()
    if key and key in editor_registry.list_editors():
        editor_registry.launch(key, p)
        print(f"opened: {snippets.relpath(p)}")
        return 0

    from cptools.lib.open import reveal_file
    reveal_file(p)
    print(f"revealed: {snippets.relpath(p)}")
    return 0


def cmd_folder(argv):
    from cptools.lib.open import open_folder
    root = snippets.root_dir()
    root.mkdir(parents=True, exist_ok=True)
    open_folder(root)
    print(f"opened: {root}")
    return 0


def cmd_root(argv):
    if not argv or argv[0] in ("show", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("usage: root [show | set PATH | reset]")
            return 0
        print(snippets.root_dir())
        return 0

    sub = argv[0]
    if sub == "set":
        if len(argv) < 2:
            print("usage: root set <path>", file=sys.stderr)
            return 2
        raw = " ".join(argv[1:]).strip()
        cfg = snippets.load_config()
        cfg["root_dir"] = raw
        snippets.save_config(cfg)
        print(f"root_dir = {snippets.root_dir()}")
        return 0
    if sub == "reset":
        cfg = snippets.load_config()
        cfg["root_dir"] = ""
        snippets.save_config(cfg)
        print(f"root_dir = {snippets.root_dir()}")
        return 0

    print(f"unknown: root {sub}", file=sys.stderr)
    return 2


def cmd_config(argv):
    cfg = snippets.load_config()

    if not argv or argv[0] in ("show", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("usage: config [show | get KEY | set KEY VALUE | reset]")
            return 0
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0

    sub = argv[0]
    if sub == "get":
        if len(argv) < 2:
            return 2
        v = cfg.get(argv[1])
        if v is None:
            return 1
        if isinstance(v, (list, dict)):
            print(json.dumps(v))
        else:
            print(v)
        return 0
    if sub == "set":
        if len(argv) < 3:
            return 2
        key = argv[1]
        value = " ".join(argv[2:])
        if key == "ignore":
            cfg[key] = value.split()
        else:
            cfg[key] = value
        snippets.save_config(cfg)
        print(f"{key} = {cfg[key]}")
        return 0
    if sub == "reset":
        snippets.save_config({"root_dir": "", "ignore": []})
        print("reset to defaults")
        return 0

    print(f"unknown: config {sub}", file=sys.stderr)
    return 2


def cmd_gui(argv):
    try:
        from gui import launch
    except ImportError as e:
        print(f"GUI not available: {e}", file=sys.stderr)
        return 1
    return launch()


def print_help():
    print("""snippet - manage code snippets

usage:
  cpt snip list                    list all snippets
  cpt snip show <name>             print a snippet to stdout
  cpt snip copy <name>             copy to clipboard
  cpt snip add <file> [--name N]   add a file to the snippets root
  cpt snip remove <name>           delete a snippet
  cpt snip rename <old> <new>      rename a snippet
  cpt snip edit <name>             open in editor
  cpt snip folder                  open root in file manager
  cpt snip root [show|set|reset]   manage root directory
  cpt snip gui                     open GUI browser
  cpt snip config [show|get|set|reset]

name resolution:
  exact path      ds/segtree.cpp
  without ext     ds/segtree
  unique stem     segtree

config keys:
  root_dir        snippets root folder (empty = default)
  ignore          additional folder names to skip
""")


COMMANDS = {
    "list": cmd_list,
    "show": cmd_show,
    "copy": cmd_copy,
    "add": cmd_add,
    "remove": cmd_remove,
    "rm": cmd_remove,
    "rename": cmd_rename,
    "mv": cmd_rename,
    "edit": cmd_edit,
    "folder": cmd_folder,
    "root": cmd_root,
    "config": cmd_config,
    "gui": cmd_gui,
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