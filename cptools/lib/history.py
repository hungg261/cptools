import json
from datetime import datetime
from pathlib import Path

from .. import paths


MAX_ENTRIES = 15


def _history_file() -> Path:
    return paths.data_root() / "shared" / "history.json"


def load() -> list[dict]:
    f = _history_file()
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        items = data.get("recent", [])
    elif isinstance(data, list):
        items = data
    else:
        return []
    return [it for it in items if isinstance(it, dict) and it.get("path")]


def save(items: list[dict]) -> None:
    f = _history_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(
            {"recent": items[:MAX_ENTRIES]},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def add(path) -> list[dict]:
    p = str(Path(path).resolve())
    items = load()
    items = [it for it in items if it.get("path") != p]
    items.insert(0, {
        "path": p,
        "opened_at": datetime.now().isoformat(timespec="seconds"),
    })
    items = items[:MAX_ENTRIES]
    save(items)
    return items


def clear() -> None:
    save([])


def remove(path) -> list[dict]:
    p = str(Path(path).resolve())
    items = [it for it in load() if it.get("path") != p]
    save(items)
    return items