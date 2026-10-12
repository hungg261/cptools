import json
from pathlib import Path

from .. import paths


def _config_file() -> Path:
    return paths.config_root() / "config.json"


def load() -> dict:
    f = _config_file()
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save(data: dict) -> None:
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get(key, default=None):
    return load().get(key, default)


def set(key, value) -> None:
    data = load()
    data[key] = value
    save(data)


def update(**kwargs) -> None:
    data = load()
    data.update(kwargs)
    save(data)


def delete(key) -> bool:
    data = load()
    if key not in data:
        return False
    del data[key]
    save(data)
    return True