import json
import os
import re
import sys
from pathlib import Path

DATA = Path(os.environ["CPTOOLS_PLUGIN_DATA_DIR"])
AS_JSON = os.environ.get("CPTOOLS_OUTPUT") == "json"

PATTERNS = {
    "codeforces": re.compile(
        r"codeforces\.com/(?:contest|problemset/problem)/(\d+)/(?:problem/)?([A-Z]\d?)"
    ),
    "atcoder": re.compile(r"atcoder\.jp/contests/([^/]+)/tasks/([^/]+)"),
}


def load() -> list[dict]:
    f = DATA / "problems.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def save(items: list[dict]) -> None:
    (DATA / "problems.json").write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def cmd_parse(args: list[str]) -> int:
    if not args:
        print("usage: parse <url>", file=sys.stderr)
        return 2

    url = args[0]
    for site, pat in PATTERNS.items():
        m = pat.search(url)
        if not m:
            continue
        item = {"site": site, "id": "-".join(m.groups()), "url": url}
        items = load()
        items.append(item)
        save(items)
        if AS_JSON:
            print(json.dumps({"type": "item", **item}, ensure_ascii=False))
        else:
            print(f"saved: {site} {item['id']}")
        return 0

    print("unrecognized url", file=sys.stderr)
    return 1


def cmd_list(args: list[str]) -> int:
    for item in load():
        if AS_JSON:
            print(json.dumps({"type": "item", **item}, ensure_ascii=False))
        else:
            print(f"{item['site']:12} {item['id']:15} {item['url']}")
    return 0


COMMANDS = {"parse": cmd_parse, "list": cmd_list}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"usage: main.py <{'|'.join(COMMANDS)}>", file=sys.stderr)
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))