import json
import os
from pathlib import Path
from string import Template

from cptools.lib import folders as folders_lib

CONFIG_DIR = Path(os.environ["CPTOOLS_PLUGIN_CONFIG_DIR"])
DATA_DIR = Path(os.environ["CPTOOLS_PLUGIN_DATA_DIR"])

CONFIG_FILE = CONFIG_DIR / "config.json"
TEMPLATES_DIR = CONFIG_DIR / "templates"

PLUGIN_DIR = Path(__file__).parent
PLUGIN_TEMPLATES_DIR = PLUGIN_DIR / "templates"

DEFAULTS = {
    "default_dir": "",
    "fallback_dir": "",
    "oj_dirs": {},
    "default_template": "cpp_default",
    "default_ext": ".cpp",
    "default_editor": "",
    "editors": {},
    "prompt_after_new": True,
    "auto_oj_subdir": True,
    "custom_ojs": {},
}

BOOL_KEYS = ("prompt_after_new", "auto_oj_subdir")

_FALSE_STRINGS = ("0", "false", "no", "off", "")


def load_config():
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in data.items() if k != "oj_dirs"})
    cfg["oj_dirs"] = dict(data.get("oj_dirs") or {})

    if cfg.get("default_template") == "cpp":
        cfg["default_template"] = "cpp_default"

    for key in BOOL_KEYS:
        v = cfg.get(key)
        if isinstance(v, str):
            cfg[key] = v.strip().lower() not in _FALSE_STRINGS
        else:
            cfg[key] = bool(v)

    return cfg


def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def expand(s):
    if not s:
        return None
    s = str(s)
    if s.startswith("@"):
        try:
            p = folders_lib.resolve_ref(s)
        except Exception:
            p = None
        if p is None:
            return None
        try:
            return p.resolve()
        except OSError:
            return p
    return folders_lib.resolve_user_path(s)


def resolve_dir(cfg, oj_name):
    oj_dirs = cfg.get("oj_dirs") or {}
    auto_subdir = bool(cfg.get("auto_oj_subdir", True))

    if oj_name:
        if oj_name in oj_dirs:
            p = expand(oj_dirs[oj_name])
            if p:
                return p
        if cfg.get("default_dir"):
            base = expand(cfg["default_dir"])
            if base:
                return base / oj_name if auto_subdir else base
        return DATA_DIR / "submissions" / oj_name

    if cfg.get("fallback_dir"):
        p = expand(cfg["fallback_dir"])
        if p:
            return p
    if cfg.get("default_dir"):
        p = expand(cfg["default_dir"])
        if p:
            return p
    return DATA_DIR / "submissions" / "misc"


def list_templates():
    result = {}
    if PLUGIN_TEMPLATES_DIR.is_dir():
        for f in PLUGIN_TEMPLATES_DIR.iterdir():
            if f.is_file():
                result[f.stem] = f
    if TEMPLATES_DIR.is_dir():
        for f in TEMPLATES_DIR.iterdir():
            if f.is_file():
                result[f.stem] = f
    return result


def find_template(name):
    if TEMPLATES_DIR.is_dir():
        for f in TEMPLATES_DIR.iterdir():
            if f.is_file() and f.stem == name:
                return f
    if PLUGIN_TEMPLATES_DIR.is_dir():
        for f in PLUGIN_TEMPLATES_DIR.iterdir():
            if f.is_file() and f.stem == name:
                return f
    return None


def render_template(path, ctx, now=None):
    text = path.read_text(encoding="utf-8")

    if "$" in text:
        return Template(text).safe_substitute(ctx)

    # Legacy: strftime-style templates with no $ placeholders
    if now is not None:
        try:
            return now.strftime(text)
        except Exception:
            return text
    return text