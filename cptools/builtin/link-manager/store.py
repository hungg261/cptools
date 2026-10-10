import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ["CPTOOLS_PLUGIN_DATA_DIR"])
STORE_FILE = DATA_DIR / "problems.json"


def _migrate(item: dict) -> dict:
    # v0.1 used "site" and "url"; v0.2 uses "oj" and "link"
    if "oj" not in item and "site" in item:
        item["oj"] = item.pop("site")
    if "link" not in item and "url" in item:
        item["link"] = item.pop("url")
    return item


def load_problems():
    if not STORE_FILE.exists():
        return []
    try:
        raw = json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    migrated = [_migrate(dict(it)) for it in raw]
    if migrated != raw:
        save_problems(migrated)
    return migrated


def save_problems(items):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORE_FILE.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_problem(item):
    items = load_problems()
    items.append(item)
    save_problems(items)