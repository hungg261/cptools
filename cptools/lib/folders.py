import json
import os
from pathlib import Path

from .. import paths


def _config_file() -> Path:
    return paths.plugin_config_dir("folders") / "folders.json"


def _empty() -> dict:
    return {"folders": {}, "default": ""}


def load() -> dict:
    f = _config_file()
    if not f.exists():
        return _empty()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return _empty()
    if not isinstance(data, dict):
        return _empty()

    folders = data.get("folders")
    if not isinstance(folders, dict):
        folders = {}
    folders = {
        str(k): str(v) for k, v in folders.items()
        if isinstance(k, str) and isinstance(v, str) and k and v
    }

    default = data.get("default", "")
    if not isinstance(default, str):
        default = ""

    return {"folders": folders, "default": default}


def save(data: dict) -> None:
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_names() -> list[str]:
    data = load()
    return sorted(data["folders"].keys())


def get_path(name: str) -> Path | None:
    data = load()
    raw = data["folders"].get(name)
    if not raw:
        return None
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def resolve(name: str) -> Path | None:
    return get_path(name)


def resolve_ref(ref: str) -> Path | None:
    """Resolve a reference.

    - "@name"        -> path of folder "name"
    - "@name/sub"    -> path of folder "name" joined with "sub"
    - anything else  -> expanded Path (absolute, ~, env vars)
    """
    if not ref:
        return None
    s = str(ref)
    if s.startswith("@"):
        rest = s[1:]
        if "/" in rest:
            name, _, sub = rest.partition("/")
        elif "\\" in rest:
            name, _, sub = rest.partition("\\")
        else:
            name, sub = rest, ""
        base = get_path(name)
        if base is None:
            return None
        if sub:
            return base / sub
        return base
    return Path(os.path.expandvars(os.path.expanduser(s)))


def set_folder(name: str, raw_path: str) -> None:
    data = load()
    data["folders"][name] = str(raw_path)
    if not data["default"]:
        data["default"] = name
    save(data)


def remove_folder(name: str) -> bool:
    data = load()
    if name not in data["folders"]:
        return False
    del data["folders"][name]
    if data["default"] == name:
        data["default"] = next(iter(sorted(data["folders"])), "")
    save(data)
    return True


def rename_folder(old: str, new: str) -> bool:
    data = load()
    if old not in data["folders"]:
        return False
    if new in data["folders"]:
        return False
    data["folders"][new] = data["folders"].pop(old)
    if data["default"] == old:
        data["default"] = new
    save(data)
    return True


def get_default() -> str:
    return load().get("default", "")


def set_default(name: str) -> bool:
    data = load()
    if name not in data["folders"]:
        return False
    data["default"] = name
    save(data)
    return True


def find_names(query: str) -> list[str]:
    """Return candidate names matching query.

    Order of preference: exact, prefix, substring, fuzzy.
    Returns [] if nothing matches.
    """
    if not query:
        return []
    names = list_names()
    if query in names:
        return [query]
    prefix = [n for n in names if n.startswith(query)]
    if prefix:
        return prefix
    substr = [n for n in names if query in n]
    if substr:
        return substr
    import difflib
    return difflib.get_close_matches(query, names, n=5, cutoff=0.4)


def path_of(query: str):
    """Resolve a possibly fuzzy name.

    Returns (name, path) on unique match, (None, list_of_candidates)
    if ambiguous, (None, []) if nothing matches.
    """
    if not query:
        return (None, [])
    candidates = find_names(query)
    if not candidates:
        return (None, [])
    if len(candidates) == 1:
        name = candidates[0]
        return (name, get_path(name))
    return (None, candidates)