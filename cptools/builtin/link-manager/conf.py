import json
import os
from pathlib import Path
from string import Template

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
}


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

    # migrate old default template name
    if cfg.get("default_template") == "cpp":
        cfg["default_template"] = "cpp_default"

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
    return Path(os.path.expandvars(os.path.expanduser(str(s)))).resolve()


def resolve_dir(cfg, oj_name):
    oj_dirs = cfg.get("oj_dirs") or {}

    if oj_name and oj_name in oj_dirs:
        p = expand(oj_dirs[oj_name])
        if p:
            return p

    if oj_name and cfg.get("default_dir"):
        p = expand(cfg["default_dir"])
        if p:
            return p

    if not oj_name and cfg.get("fallback_dir"):
        p = expand(cfg["fallback_dir"])
        if p:
            return p

    if not oj_name and cfg.get("default_dir"):
        p = expand(cfg["default_dir"])
        if p:
            return p

    return DATA_DIR / "submissions" / (oj_name or "misc")


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