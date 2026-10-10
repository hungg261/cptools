from pathlib import Path
from platformdirs import user_config_dir, user_data_dir

APP = "cptools"


def config_root() -> Path:
    p = Path(user_config_dir(APP, appauthor=False))
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_root() -> Path:
    p = Path(user_data_dir(APP, appauthor=False))
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_plugins_dir() -> Path:
    p = data_root() / "plugins"
    p.mkdir(parents=True, exist_ok=True)
    return p


def builtin_plugins_dir() -> Path:
    return Path(__file__).parent / "builtin"


def plugin_config_dir(name: str) -> Path:
    p = config_root() / "plugins" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def plugin_data_dir(name: str) -> Path:
    p = data_root() / "data" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def plugin_cache_dir(name: str) -> Path:
    p = data_root() / "cache" / name
    p.mkdir(parents=True, exist_ok=True)
    return p