import json
import os
import shutil
from pathlib import Path

from .. import paths


DEFAULT_IGNORE = {
    ".git", ".svn", ".hg",
    "__pycache__", "node_modules",
    ".venv", "venv", "env",
    "target", "build", "dist",
    ".idea", ".vscode", ".cache", ".pytest_cache",
}


def _config_file() -> Path:
    return paths.plugin_config_dir("snippet") / "config.json"


def _default_root() -> Path:
    p = paths.plugin_config_dir("snippet") / "snippets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_config() -> dict:
    f = _config_file()
    if not f.exists():
        return {"root_dir": "", "ignore": []}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {"root_dir": "", "ignore": []}
    if not isinstance(data, dict):
        return {"root_dir": "", "ignore": []}
    data.setdefault("root_dir", "")
    data.setdefault("ignore", [])
    if not isinstance(data.get("ignore"), list):
        data["ignore"] = []
    return data


def save_config(cfg: dict) -> None:
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def root_dir() -> Path:
    cfg = load_config()
    raw = (cfg.get("root_dir") or "").strip()
    if not raw:
        return _default_root()
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def _ignore_names() -> set:
    cfg = load_config()
    return DEFAULT_IGNORE | set(cfg.get("ignore") or [])


def _should_skip(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    return path.name in _ignore_names()


def _walk(root: Path):
    if not root.is_dir():
        return
    stack = [root]
    while stack:
        cur = stack.pop()
        try:
            entries = sorted(cur.iterdir())
        except OSError:
            continue
        for e in entries:
            if _should_skip(e):
                continue
            if e.is_symlink():
                continue
            if e.is_dir():
                stack.append(e)
            elif e.is_file():
                yield e


def relpath(file: Path) -> str:
    return file.relative_to(root_dir()).as_posix()


def iter_all() -> list:
    root = root_dir()
    files = list(_walk(root))
    files.sort(key=lambda p: str(p.relative_to(root)).lower())
    return files


def resolve_all(name: str) -> list:
    if not name:
        return []
    root = root_dir()
    if not root.is_dir():
        return []
    norm = name.replace("\\", "/").strip().lstrip("/")
    if not norm:
        return []

    all_files = iter_all()

    for f in all_files:
        if relpath(f) == norm:
            return [f]

    for f in all_files:
        rel = relpath(f)
        if "." in rel and rel.rsplit(".", 1)[0] == norm:
            return [f]

    return [f for f in all_files if f.stem == norm]


def resolve(name: str):
    matches = resolve_all(name)
    if len(matches) == 1:
        return matches[0]
    return None


def read(name: str):
    p = resolve(name)
    if p is None:
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def add_file(src: Path, as_name: str = None) -> Path:
    root = root_dir()
    root.mkdir(parents=True, exist_ok=True)
    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(src)

    if as_name:
        clean = as_name.replace("\\", "/").strip().lstrip("/")
        if not clean:
            clean = src.name
        target = root / clean
    else:
        target = root / src.name

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    return target


def remove(name: str) -> bool:
    p = resolve(name)
    if p is None:
        return False
    try:
        p.unlink()
        return True
    except OSError:
        return False


def rename(old_name: str, new_name: str):
    src = resolve(old_name)
    if src is None:
        return None
    root = root_dir()
    clean = new_name.replace("\\", "/").strip().lstrip("/")
    if not clean:
        return None
    dst = root / clean
    if dst.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return dst