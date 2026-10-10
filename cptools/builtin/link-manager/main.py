import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from oj import parse as parse_url, oj_names
from conf import (
    DATA_DIR, CONFIG_DIR, TEMPLATES_DIR,
    load_config, save_config, resolve_dir, expand,
    list_templates, find_template, render_template,
)
from store import add_problem, load_problems

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


def open_dir(path):
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    else:
        subprocess.run(["xdg-open", str(path)])


def cmd_parse(argv):
    if not argv:
        print("usage: parse <url>", file=sys.stderr)
        return 2

    url = argv[0]
    obj = parse_url(url)
    cfg = load_config()
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
        print("usage: new <url> [--template NAME] [--dir PATH] [--name NAME]")
        return 0 if argv else 2

    parser = argparse.ArgumentParser(add_help=False, prog="cpt link new")
    parser.add_argument("url")
    parser.add_argument("--template", "-t")
    parser.add_argument("--dir", "-d")
    parser.add_argument("--name", "-n")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    obj = parse_url(ns.url)
    cfg = load_config()

    if ns.dir:
        target_dir = expand(ns.dir)
    else:
        target_dir = resolve_dir(cfg, obj.name if obj else None)
    target_dir.mkdir(parents=True, exist_ok=True)

    tpl_name = ns.template or cfg.get("default_template") or "cpp"
    tpl_path = find_template(tpl_name)
    if tpl_path is None:
        print(f"template '{tpl_name}' not found (run: cpt link template list)", file=sys.stderr)
        return 1
    ext = tpl_path.suffix

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
    obj = parse_url(argv[0])
    cfg = load_config()
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

    if argv[0] in ("--data", "--list"):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        open_dir(DATA_DIR)
        print(f"opened: {DATA_DIR}")
        return 0

    if argv[0] == "--config":
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        open_dir(CONFIG_DIR)
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
        open_dir(target)
        print(f"opened: {target}")
        return 0

    arg = argv[0]
    obj = parse_url(arg)

    if obj is not None:
        target = resolve_dir(cfg, obj.name)
    else:
        if arg not in oj_names():
            print(f"not a URL and not a known OJ: {arg}", file=sys.stderr)
            print(f"known OJs: {', '.join(oj_names())}", file=sys.stderr)
            return 1
        target = resolve_dir(cfg, arg)

    target.mkdir(parents=True, exist_ok=True)
    open_dir(target)
    print(f"opened: {target}")
    return 0


def cmd_config(argv):
    cfg = load_config()

    if not argv or argv[0] in ("show", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("usage: config [show | get KEY | set KEY VALUE | unset KEY]")
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

    print(f"unknown: config {sub}", file=sys.stderr)
    return 2


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
  cpt link parse <url>                        parse URL, show info
  cpt link new <url> [opts]                   create source file
  cpt link list                               list saved problems
  cpt link dir <url>                          show target directory
  cpt link open <url|oj|--data|--config|--problem>   open a directory
  cpt link config [show|get|set|unset]        manage settings
  cpt link template [list|add|remove|show]    manage templates

new options:
  -t, --template NAME    template name (default: config.default_template)
  -d, --dir PATH         override target directory
  -n, --name NAME        override file name (default: problem id)

config keys:
  default_dir            default directory for known OJs
  fallback_dir           directory for unknown OJs
  oj_dirs.<oj>           per-OJ directory (e.g. oj_dirs.codeforces)
  default_template       default template name

template placeholders:
  ${link} ${id} ${oj} ${name} ${date} ${time} ${datetime} ${timestamp}
  use $$ for a literal $, e.g. $${link} -> ${link}
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
    "config": cmd_config,
    "template": cmd_template,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print_help()
        return 0
    cmd = argv[0]
    if cmd not in HANDLERS:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print_help()
        return 2
    return HANDLERS[cmd](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))