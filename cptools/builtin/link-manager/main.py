import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from cptools.lib.editor import get_editors, launch as launch_editor, ordered_keys
from cptools.lib.open import open_file, open_folder, reveal_file

from oj import (
    parse as parse_url,
    oj_names,
    find_oj,
    make_custom_oj,
    BUILTIN_OJS,
)

from conf import (
    DATA_DIR, CONFIG_DIR, TEMPLATES_DIR, DEFAULTS,
    load_config, save_config, resolve_dir, expand,
    list_templates, find_template, render_template,
)
from store import add_problem, load_problems, save_problems

AS_JSON = os.environ.get("CPTOOLS_OUTPUT") == "json"


def emit_json(obj):
    print(json.dumps(obj, ensure_ascii=False))


def unique_path(directory, base, ext):
    p = directory / f"{base}{ext}"
    if not p.exists():
        return p
    i = 2
    while True:
        p = directory / f"{base}_v{i}{ext}"
        if not p.exists():
            return p
        i += 1


def _open_with_editor(path, editor_name, cfg):
    editor_name = editor_name or cfg.get("default_editor") or ""
    if not editor_name:
        open_file(path)
        return
    editors = get_editors(cfg.get("editors"))
    if editor_name not in editors:
        print(f"editor '{editor_name}' not found, using system default", file=sys.stderr)
        open_file(path)
        return
    launch_editor(editors[editor_name], path)


def load_oj_classes(cfg):
    classes = []
    for name, spec in (cfg.get("custom_ojs") or {}).items():
        try:
            patterns = spec.get("patterns") or []
            id_template = spec.get("id_template")
            classes.append(make_custom_oj(name, patterns, id_template))
        except Exception as e:
            print(f"[link-manager] invalid custom oj '{name}': {e}", file=sys.stderr)
    return classes


def _ask_and_open(path, cfg):
    import questionary

    editors = get_editors(cfg.get("editors"))
    if not editors:
        answer = questionary.confirm(f"Open {path.name}?").ask()
        if answer:
            open_file(path)
        return

    from cptools.lib.editor import ordered_keys

    default = cfg.get("default_editor") or ""
    keys = ordered_keys(editors)
    if default and default in editors:
        keys = [default] + [k for k in keys if k != default]

    choices = [questionary.Choice(title=editors[k].label, value=k) for k in keys]
    choices.append(questionary.Choice(title="system default", value="__system__"))
    choices.append(questionary.Choice(title="no", value="__no__"))

    result = questionary.select("Open with?", choices=choices).ask()
    if result is None or result == "__no__":
        return
    if result == "__system__":
        open_file(path)
        return
    launch_editor(editors[result], path)


def cmd_parse(argv):
    if not argv:
        print("usage: parse <url>", file=sys.stderr)
        return 2

    url = argv[0]
    cfg = load_config()
    classes = load_oj_classes(cfg)
    obj = parse_url(url, classes)
    target = resolve_dir(cfg, obj.name if obj else None)

    if obj is None:
        if AS_JSON:
            emit_json({"ok": False, "error": "unrecognized url", "link": url, "dir": str(target)})
        else:
            print("unrecognized url")
            print(f"would save to: {target}")
        return 1

    if AS_JSON:
        emit_json({"ok": True, "oj": obj.name, "id": obj.id, "link": obj.link, "dir": str(target)})
    else:
        print(f"oj:   {obj.name}")
        print(f"id:   {obj.id}")
        print(f"link: {obj.link}")
        print(f"dir:  {target}")
    return 0


def cmd_new(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: new <url> [--template NAME] [--ext EXT] [--dir PATH] [--name NAME] [--open [EDITOR]] [--no-open]")
        return 0 if argv else 2

    parser = argparse.ArgumentParser(add_help=False, prog="cpt link new")
    parser.add_argument("url")
    parser.add_argument("--template", "-t")
    parser.add_argument("--ext", "-e")
    parser.add_argument("--dir", "-d")
    parser.add_argument("--name", "-n")
    parser.add_argument("--open", nargs="?", const="__default__", default=None)
    parser.add_argument("--no-open", action="store_true")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    cfg = load_config()
    classes = load_oj_classes(cfg)
    obj = parse_url(ns.url, classes)

    if ns.dir:
        target_dir = expand(ns.dir)
    else:
        target_dir = resolve_dir(cfg, obj.name if obj else None)
    target_dir.mkdir(parents=True, exist_ok=True)

    tpl_name = ns.template or cfg.get("default_template") or "cpp_default"
    tpl_path = find_template(tpl_name)
    if tpl_path is None:
        print(f"template '{tpl_name}' not found (run: cpt link template list)", file=sys.stderr)
        return 1

    ext = ns.ext or cfg.get("default_ext") or ".cpp"
    if not ext.startswith("."):
        ext = "." + ext

    if ns.name:
        base = ns.name
    elif obj:
        base = obj.id
    else:
        tail = ns.url.split("?")[0].rstrip("/").split("/")[-1]
        base = tail or "problem"

    final = unique_path(target_dir, base, ext)

    now = datetime.now()
    ctx = {
        "link": obj.link if obj else ns.url,
        "id": obj.id if obj else base,
        "oj": obj.name if obj else "unknown",
        "name": final.stem,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H.%M.%S"),
        "datetime": now.strftime("%Y-%m-%d-%H.%M.%S"),
        "timestamp": str(int(now.timestamp())),
    }
    content = render_template(tpl_path, ctx, now=now)
    final.write_text(content, encoding="utf-8")

    add_problem({
        "oj": obj.name if obj else "unknown",
        "id": obj.id if obj else base,
        "link": obj.link if obj else ns.url,
        "path": str(final),
        "created_at": now.isoformat(timespec="seconds"),
    })

    if AS_JSON:
        emit_json({
            "ok": True,
            "path": str(final),
            "oj": obj.name if obj else "unknown",
            "id": obj.id if obj else base,
            "link": obj.link if obj else ns.url,
        })
    else:
        print(f"created: {final}")
        if str(final).startswith(str(DATA_DIR)):
            print("hint: files are stored in plugin data dir")
            print('  set a location: cpt link config set default_dir "D:/CP"')

    if ns.no_open:
        return 0

    if ns.open is not None:
        editor = None if ns.open == "__default__" else ns.open
        _open_with_editor(final, editor, cfg)
        return 0

    if cfg.get("prompt_after_new") and sys.stdin.isatty():
        _ask_and_open(final, cfg)

    return 0


def cmd_list(argv):
    items = load_problems()
    if AS_JSON:
        for it in items:
            emit_json({"type": "item", **it})
        return 0
    if not items:
        print("no problems saved")
        return 0
    for it in items:
        oj = it.get("oj", "?")
        pid = it.get("id", "?")
        print(f"{oj:12} {pid:15} {it.get('path', '')}")
    return 0


def cmd_dir(argv):
    if not argv:
        print("usage: dir <url>", file=sys.stderr)
        return 2
    cfg = load_config()
    classes = load_oj_classes(cfg)
    obj = parse_url(argv[0], classes)
    print(resolve_dir(cfg, obj.name if obj else None))
    return 0


def cmd_open(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("""usage:
  cpt link open <url>              open target dir for a URL
  cpt link open <oj>               open dir for an OJ
  cpt link open --data             open plugin data directory
  cpt link open --config           open plugin config directory
  cpt link open --list             alias for --data
  cpt link open --problem <id>     open folder containing a saved problem
""")
        return 0 if argv else 2

    cfg = load_config()
    classes = load_oj_classes(cfg)

    if argv[0] in ("--data", "--list"):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        open_folder(DATA_DIR)
        print(f"opened: {DATA_DIR}")
        return 0

    if argv[0] == "--config":
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        open_folder(CONFIG_DIR)
        print(f"opened: {CONFIG_DIR}")
        return 0

    if argv[0] == "--problem":
        if len(argv) < 2:
            print("usage: open --problem <id>", file=sys.stderr)
            return 2
        pid = argv[1]
        matches = [it for it in load_problems() if it.get("id") == pid]
        if not matches:
            print(f"no saved problem with id '{pid}'", file=sys.stderr)
            return 1
        item = matches[-1]
        p = item.get("path")
        if not p:
            print(f"problem '{pid}' has no path", file=sys.stderr)
            return 1
        target = Path(p).parent
        if not target.is_dir():
            print(f"folder not found: {target}", file=sys.stderr)
            return 1
        open_folder(target)
        print(f"opened: {target}")
        return 0

    arg = argv[0]
    obj = parse_url(arg, classes)
    names = oj_names(classes)

    if obj is not None:
        target = resolve_dir(cfg, obj.name)
    else:
        if arg not in names:
            print(f"not a URL and not a known OJ: {arg}", file=sys.stderr)
            print(f"known OJs: {', '.join(names)}", file=sys.stderr)
            return 1
        target = resolve_dir(cfg, arg)

    target.mkdir(parents=True, exist_ok=True)
    open_folder(target)
    print(f"opened: {target}")
    return 0


def _find_problems(pid):
    return [it for it in load_problems() if it.get("id") == pid]


def cmd_open_file(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("""usage:
  cpt link open-file <id>                  open saved file with default editor
  cpt link open-file <id> --with EDITOR    open with specific editor
  cpt link open-file <id> --folder         reveal file in file manager
  cpt link open-file <id> -D, --delete     delete file + entry instead
  cpt link open-file <id> -D -y            delete without confirmation
""")
        return 0 if argv else 2

    parser = argparse.ArgumentParser(add_help=False, prog="cpt link open-file")
    parser.add_argument("id")
    parser.add_argument("--with", dest="editor", default=None)
    parser.add_argument("--folder", action="store_true")
    parser.add_argument("-D", "--delete", action="store_true")
    parser.add_argument("-y", "--yes", action="store_true")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    if ns.delete:
        rm_args = [ns.id]
        if ns.yes:
            rm_args.append("-y")
        return cmd_rm(rm_args)

    matches = _find_problems(ns.id)
    if not matches:
        print(f"no saved problem with id '{ns.id}'", file=sys.stderr)
        return 1

    item = matches[-1]
    p = item.get("path")
    if not p:
        print(f"problem '{ns.id}' has no path", file=sys.stderr)
        return 1

    target = Path(p)
    if not target.is_file():
        print(f"file not found: {target}", file=sys.stderr)
        return 1

    if ns.folder:
        reveal_file(target)
        print(f"revealed: {target}")
        return 0

    cfg = load_config()
    _open_with_editor(target, ns.editor, cfg)
    print(f"opened: {target}")
    return 0


def _confirm(message: str) -> bool:
    if sys.stdin.isatty():
        try:
            import questionary
            result = questionary.confirm(message).ask()
            return bool(result)
        except Exception:
            pass
    try:
        answer = input(f"{message} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def cmd_rm(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("""usage:
  cpt link rm <id>                 delete file and store entry
  cpt link rm <id> -y              skip confirmation
  cpt link rm <id> --keep-entry    delete file only
  cpt link rm <id> --all           delete all files with this id
""")
        return 0 if argv else 2

    parser = argparse.ArgumentParser(add_help=False, prog="cpt link rm")
    parser.add_argument("id")
    parser.add_argument("-y", "--yes", action="store_true")
    parser.add_argument("--keep-entry", action="store_true")
    parser.add_argument("--all", action="store_true")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    matches = _find_problems(ns.id)
    if not matches:
        print(f"no saved problem with id '{ns.id}'", file=sys.stderr)
        return 1

    targets = matches if ns.all else [matches[-1]]

    if not ns.yes:
        names = ", ".join(Path(it.get("path", "")).name for it in targets if it.get("path"))
        if not _confirm(f"Delete {len(targets)} file(s)? [{names}]"):
            print("aborted")
            return 0

    deleted = []
    for it in targets:
        p = it.get("path")
        if p:
            fp = Path(p)
            if fp.is_file():
                fp.unlink()
                deleted.append(str(fp))

    if not ns.keep_entry:
        remaining = [it for it in load_problems() if it not in targets]
        save_problems(remaining)

    for d in deleted:
        print(f"deleted: {d}")
    return 0


def cmd_undo(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("""usage:
  cpt link undo                 delete the most recently created file
  cpt link undo -y              skip confirmation
  cpt link undo --keep-entry    delete file, keep store entry
""")
        return 0

    parser = argparse.ArgumentParser(add_help=False, prog="cpt link undo")
    parser.add_argument("-y", "--yes", action="store_true")
    parser.add_argument("--keep-entry", action="store_true")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    items = load_problems()
    if not items:
        print("nothing to undo", file=sys.stderr)
        return 1

    last = items[-1]
    path_str = last.get("path", "")
    pid = last.get("id", "?")

    if not path_str:
        print(f"last entry has no path (id={pid})", file=sys.stderr)
        return 1

    p = Path(path_str)

    if not ns.yes:
        if not _confirm(f"Delete {p.name}?"):
            print("aborted")
            return 0

    if p.is_file():
        p.unlink()
        print(f"deleted: {p}")
    else:
        print(f"file not found: {p}", file=sys.stderr)

    if not ns.keep_entry:
        items.pop()
        save_problems(items)

    return 0


def cmd_editors(argv):
    if not argv or argv[0] in ("list", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("usage: editors [list | detect | known | set NAME PATH | unset NAME]")
            return 0
        return _editors_list()

    sub = argv[0]

    if sub == "detect":
        return _editors_detect()
    if sub == "known":
        return _editors_known()

    if sub == "set":
        if len(argv) < 3:
            print("usage: editors set <name> <path>", file=sys.stderr)
            return 2
        cfg = load_config()
        eds = dict(cfg.get("editors") or {})
        eds[argv[1]] = argv[2]
        cfg["editors"] = eds
        save_config(cfg)
        print(f"editors.{argv[1]} = {argv[2]}")
        return 0

    if sub == "unset":
        if len(argv) < 2:
            print("usage: editors unset <name>", file=sys.stderr)
            return 2
        cfg = load_config()
        eds = dict(cfg.get("editors") or {})
        eds.pop(argv[1], None)
        cfg["editors"] = eds
        save_config(cfg)
        return 0

    print(f"unknown: editors {sub}", file=sys.stderr)
    return 2


def cmd_oj(argv):
    if not argv or argv[0] in ("list", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("""usage: oj <subcommand>

  list                     list builtin and custom OJs
  show <name>              show details
  add <name> <pattern> [--id-template T]
  remove <name>
  test <url> [--oj NAME]   test parsing
""")
            return 0
        return _oj_list()

    sub = argv[0]
    if sub == "list":
        return _oj_list()
    if sub == "show":
        return _oj_show(argv[1:])
    if sub == "add":
        return _oj_add(argv[1:])
    if sub == "remove":
        return _oj_remove(argv[1:])
    if sub == "test":
        return _oj_test(argv[1:])

    print(f"unknown: oj {sub}", file=sys.stderr)
    return 2


def _oj_list():
    cfg = load_config()
    classes = load_oj_classes(cfg)
    custom_names = {c.name for c in classes}

    print("builtin:")
    for cls in BUILTIN_OJS:
        print(f"  {cls.name}")

    if custom_names:
        print()
        print("custom:")
        for cls in classes:
            print(f"  {cls.name}")

    return 0


def _oj_show(args):
    if not args:
        print("usage: oj show <name>", file=sys.stderr)
        return 2
    name = args[0]
    cfg = load_config()
    classes = load_oj_classes(cfg)
    cls = find_oj(name, classes)
    if cls is None:
        print(f"unknown OJ: {name}", file=sys.stderr)
        return 1

    is_builtin = any(c is cls for c in BUILTIN_OJS)
    print(f"name:     {cls.name}")
    print(f"type:     {'builtin' if is_builtin else 'custom'}")
    print("patterns:")
    for p in cls.patterns:
        print(f"  {p.pattern}")

    spec = (cfg.get("custom_ojs") or {}).get(name)
    if spec and spec.get("id_template"):
        print(f"id_template: {spec['id_template']}")
    return 0


def _oj_add(args):
    parser = argparse.ArgumentParser(add_help=False, prog="cpt link oj add")
    parser.add_argument("name")
    parser.add_argument("pattern", nargs="?")
    parser.add_argument("--id-template", dest="id_template", default=None)
    parser.add_argument("-a", "--append", action="store_true")
    try:
        ns = parser.parse_args(args)
    except SystemExit:
        return 2

    if not ns.pattern:
        print("usage: oj add <name> <pattern> [--id-template T]", file=sys.stderr)
        return 2

    cfg = load_config()
    custom = dict(cfg.get("custom_ojs") or {})
    spec = dict(custom.get(ns.name) or {"patterns": []})

    if not ns.append:
        spec["patterns"] = []
    spec["patterns"].append(ns.pattern)
    if ns.id_template:
        spec["id_template"] = ns.id_template

    custom[ns.name] = spec

    # validate
    try:
        make_custom_oj(ns.name, spec["patterns"], spec.get("id_template"))
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    cfg["custom_ojs"] = custom
    save_config(cfg)
    print(f"oj {ns.name}: {len(spec['patterns'])} pattern(s)")
    return 0


def _oj_remove(args):
    if not args:
        print("usage: oj remove <name>", file=sys.stderr)
        return 2
    name = args[0]
    cfg = load_config()
    custom = dict(cfg.get("custom_ojs") or {})
    if name not in custom:
        print(f"not a custom OJ: {name}", file=sys.stderr)
        return 1
    custom.pop(name)
    cfg["custom_ojs"] = custom
    save_config(cfg)
    print(f"removed: {name}")
    return 0


def _oj_test(args):
    parser = argparse.ArgumentParser(add_help=False, prog="cpt link oj test")
    parser.add_argument("url")
    parser.add_argument("--oj", dest="oj", default=None)
    try:
        ns = parser.parse_args(args)
    except SystemExit:
        return 2

    cfg = load_config()
    classes = load_oj_classes(cfg)

    if ns.oj:
        cls = find_oj(ns.oj, classes)
        if cls is None:
            print(f"unknown OJ: {ns.oj}", file=sys.stderr)
            return 1
        candidates = [cls]
    else:
        candidates = list(BUILTIN_OJS) + classes

    url = ns.url
    matches = []
    for cls in candidates:
        obj = cls.try_parse(url)
        if obj is not None:
            matches.append(obj)

    if not matches:
        print(f"no match: {url}")
        return 1

    print(f"URL: {url}")
    print(f"winner: {matches[0].name} -> {matches[0].id}")
    if len(matches) > 1:
        print("also matched:")
        for obj in matches[1:]:
            print(f"  {obj.name} -> {obj.id}")

    return 0


def _editors_list():
    from cptools.lib.editor import ordered_keys

    cfg = load_config()
    editors = get_editors(cfg.get("editors"))
    default = cfg.get("default_editor") or ""
    if not editors:
        print("no editors detected")
        print()
        print("Add one manually:")
        print('  cpt link editors set <name> "<path>"')
        print()
        print("Run 'cpt link editors known' for the list of names.")
        return 0
    for key in ordered_keys(editors):
        ed = editors[key]
        mark = "*" if key == default else " "
        print(f"{mark} {key:15} {ed.label:20} {ed.exe}")
    print()
    print("* = default editor")
    return 0


def _editors_detect():
    from cptools.lib.editor import detect_editors, known_editors

    detected = detect_editors()
    user = load_config().get("editors") or {}
    print("Detected on this system:")
    if not detected:
        print("  (none)")
    for key, *_ in known_editors():
        if key in detected:
            print(f"  {key:15} {detected[key].exe}")
    if user:
        print()
        print("User-configured:")
        for key, exe in user.items():
            print(f"  {key:15} {exe}")
    return 0


def _editors_known():
    from cptools.lib.editor import known_editors

    print("Known editor names:")
    for key, label in known_editors():
        print(f"  {key:15} {label}")
    return 0


def cmd_config(argv):
    cfg = load_config()

    if not argv or argv[0] in ("show", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("usage: config [show | get KEY | set KEY VALUE | unset KEY | reset [-y] [KEY]]")
            return 0
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0

    sub = argv[0]

    if sub == "get":
        if len(argv) < 2:
            print("usage: config get <key>", file=sys.stderr)
            return 2
        v = cfg_get(cfg, argv[1])
        if isinstance(v, (dict, list)):
            print(json.dumps(v, ensure_ascii=False))
        elif v is None:
            return 1
        else:
            print(v)
        return 0

    if sub == "set":
        if len(argv) < 3:
            print("usage: config set <key> <value>", file=sys.stderr)
            return 2
        cfg_set(cfg, argv[1], " ".join(argv[2:]))
        save_config(cfg)
        print(f"{argv[1]} = {cfg_get(cfg, argv[1])}")
        return 0

    if sub == "unset":
        if len(argv) < 2:
            print("usage: config unset <key>", file=sys.stderr)
            return 2
        cfg_unset(cfg, argv[1])
        save_config(cfg)
        return 0

    if sub == "reset":
        return _config_reset(cfg, argv[1:])

    print(f"unknown: config {sub}", file=sys.stderr)
    return 2


def _config_reset(cfg, args):
    yes = False
    key = None
    for a in args:
        if a in ("-y", "--yes"):
            yes = True
        elif key is None:
            key = a
        else:
            print(f"unexpected arg: {a}", file=sys.stderr)
            return 2

    if key:
        if key in DEFAULTS:
            cfg_set(cfg, key, DEFAULTS[key])
        else:
            cfg_unset(cfg, key)
        save_config(cfg)
        print(f"reset: {key}")
        return 0

    if not yes:
        print("This will reset all settings to defaults.")
        try:
            answer = input("Continue? [y/N] ").strip().lower()
        except EOFError:
            print("aborted")
            return 0
        if answer not in ("y", "yes"):
            print("aborted")
            return 0

    save_config(dict(DEFAULTS))
    print("settings reset to defaults")
    return 0


def cmd_template(argv):
    if not argv or argv[0] in ("list", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("usage: template [list | add PATH [NAME] | remove NAME | show NAME]")
            return 0
        tpls = list_templates()
        if not tpls:
            print("no templates")
            return 0
        for name in sorted(tpls):
            print(f"{name:20} {tpls[name]}")
        return 0

    sub = argv[0]

    if sub == "add":
        if len(argv) < 2:
            print("usage: template add <path> [name]", file=sys.stderr)
            return 2
        src = Path(argv[1]).expanduser()
        if not src.is_file():
            print(f"file not found: {src}", file=sys.stderr)
            return 1
        name = argv[2] if len(argv) > 2 else src.stem
        ext = src.suffix
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        dest = TEMPLATES_DIR / f"{name}{ext}"
        shutil.copyfile(src, dest)
        print(f"added: {dest}")
        return 0

    if sub == "remove":
        if len(argv) < 2:
            print("usage: template remove <name>", file=sys.stderr)
            return 2
        name = argv[1]
        removed = []
        if TEMPLATES_DIR.is_dir():
            for f in TEMPLATES_DIR.iterdir():
                if f.is_file() and f.stem == name:
                    f.unlink()
                    removed.append(str(f))
        if not removed:
            print(f"template '{name}' not in user templates", file=sys.stderr)
            return 1
        for r in removed:
            print(f"removed: {r}")
        return 0

    if sub == "show":
        if len(argv) < 2:
            print("usage: template show <name>", file=sys.stderr)
            return 2
        p = find_template(argv[1])
        if p is None:
            print(f"template '{argv[1]}' not found", file=sys.stderr)
            return 1
        print(p.read_text(encoding="utf-8"))
        return 0

    print(f"unknown: template {sub}", file=sys.stderr)
    return 2


def print_help():
    print("""link-manager - competitive programming problem manager

usage:
  cpt link <url>                              shortcut for: new <url>
  cpt link parse <url>                        parse URL, show info
  cpt link new <url> [opts]                   create source file
  cpt link list                               list saved problems
  cpt link dir <url>                          show target directory
  cpt link open <url|oj|--data|--config|--problem>   open a directory
  cpt link open-file <id> [opts]              open a saved file
  cpt link rm <id> [opts]                     delete file(s) and entry
  cpt link editors [list|detect|known|set|unset]   manage editors
  cpt link config [show|get|set|unset|reset]  manage settings
  cpt link template [list|add|remove|show]    manage templates
  cpt link open-file <id> [opts]              open a saved file
  cpt link rm <id> [opts]                     delete file(s) and entry
  cpt link undo [-y] [--keep-entry]           delete the most recent file
  cpt link oj <subcommand>                    manage OJs

new options:
  -t, --template NAME    template name (default: config.default_template)
  -e, --ext EXT          output extension (default: config.default_ext)
  -d, --dir PATH         override target directory
  -n, --name NAME        override file name (default: problem id)
  --open [EDITOR]        open after creating (optionally pick editor)
  --no-open              never prompt or open

open-file options:
  --with EDITOR          open with a specific editor
  --folder               reveal file in file manager
  -D, --delete           delete file + entry instead of opening
  -y, --yes              skip confirmation (with --delete)

rm options:
  -y, --yes              skip confirmation
  --keep-entry           delete file only, keep store entry
  --all                  delete every file with this id

config keys:
  default_dir            default directory for known OJs
  fallback_dir           directory for unknown OJs
  oj_dirs.<oj>           per-OJ directory (e.g. oj_dirs.codeforces)
  default_template       default template name
  default_ext            default output extension (e.g. .cpp)
  default_editor         default editor (e.g. vscode)
  editors.<name>         path to editor executable
  prompt_after_new       prompt to open after new (true/false)
  auto_oj_subdir         auto-create subdir per OJ (true/false)
  custom_ojs             user-defined OJ regexes (managed via 'cpt link oj')

template placeholders:
  $link  ${link}  and similar: $id $oj $name
  $date $time $datetime $timestamp
  use ${var} when followed by letters/digits (e.g. ${id}suffix)
  use $$ for a literal $ (e.g. $$link -> $link)
""")


def cfg_get(cfg, key):
    v = cfg
    for p in key.split("."):
        if not isinstance(v, dict):
            return None
        v = v.get(p)
    return v


def cfg_set(cfg, key, value):
    parts = key.split(".")
    v = cfg
    for p in parts[:-1]:
        if p not in v or not isinstance(v[p], dict):
            v[p] = {}
        v = v[p]
    v[parts[-1]] = value


def cfg_unset(cfg, key):
    parts = key.split(".")
    v = cfg
    for p in parts[:-1]:
        if not isinstance(v, dict) or p not in v:
            return
        v = v[p]
    if isinstance(v, dict):
        v.pop(parts[-1], None)


HANDLERS = {
    "parse": cmd_parse,
    "new": cmd_new,
    "create": cmd_new,
    "list": cmd_list,
    "dir": cmd_dir,
    "open": cmd_open,
    "open-file": cmd_open_file,
    "rm": cmd_rm,
    "remove": cmd_rm,
    "delete": cmd_rm,
    "undo": cmd_undo,
    "editors": cmd_editors,
    "oj": cmd_oj,
    "config": cmd_config,
    "template": cmd_template,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print_help()
        return 0
    cmd = argv[0]
    if cmd not in HANDLERS:
        if "://" in cmd:
            return cmd_new(argv)
        print(f"unknown command: {cmd}", file=sys.stderr)
        print_help()
        return 2
    return HANDLERS[cmd](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))