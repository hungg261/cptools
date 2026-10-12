import os
import shutil
import sys
from pathlib import Path

from . import config as host_config


KNOWN = [
    ("codeblocks", "Code::Blocks", "codeblocks", [
        r"C:\Program Files\CodeBlocks\codeblocks.exe",
        r"C:\Program Files (x86)\CodeBlocks\codeblocks.exe",
        "/Applications/Code::Blocks.app/Contents/MacOS/codeblocks",
    ]),
    ("vscode", "VS Code", "code", [
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
        r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
        "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
    ]),
    ("sublime", "Sublime Text", "subl", [
        r"C:\Program Files\Sublime Text\sublime_text.exe",
        r"C:\Program Files\Sublime Text 3\sublime_text.exe",
        r"C:\Program Files (x86)\Sublime Text\sublime_text.exe",
        "/Applications/Sublime Text.app/Contents/SharedSupport/bin/subl",
    ]),
    ("notepadpp", "Notepad++", "notepad++", [
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe",
    ]),
    ("notepad", "Notepad", "notepad", []),
    ("gedit", "gedit", "gedit", []),
    ("kate", "Kate", "kate", []),
    ("vim", "Vim", "vim", []),
    ("nano", "Nano", "nano", []),
    ("emacs", "Emacs", "emacs", []),
]

_LABELS = {key: label for key, label, *_ in KNOWN}


def _resolve_exe(exe: str, extra_paths: list[str]) -> str | None:
    found = shutil.which(exe)
    if found:
        return found
    for p in extra_paths:
        expanded = Path(os.path.expandvars(os.path.expanduser(p)))
        if expanded.is_file():
            return str(expanded)
    return None


def detect_editors() -> dict[str, str]:
    result = {}
    for key, _label, exe, extra in KNOWN:
        path = _resolve_exe(exe, extra)
        if path:
            result[key] = path
    return result


def _user_editors() -> dict:
    data = host_config.get("editor_registry", {})
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and v}


def list_editors() -> dict[str, str]:
    result = detect_editors()
    result.update(_user_editors())
    return result


def known_editors() -> list[tuple[str, str]]:
    return [(key, label) for key, label, *_ in KNOWN]


def label_for(key: str) -> str:
    return _LABELS.get(key, key)


def ordered_keys(editors: dict) -> list[str]:
    order = [k for k, *_ in KNOWN if k in editors]
    extra = [k for k in editors if k not in order]
    return order + sorted(extra)


def get_default() -> str:
    v = host_config.get("default_editor", "")
    return v if isinstance(v, str) else ""


def set_default(name: str) -> None:
    host_config.set("default_editor", name)


def set_editor(name: str, exe: str) -> None:
    data = host_config.get("editor_registry", {})
    if not isinstance(data, dict):
        data = {}
    data[name] = exe
    host_config.set("editor_registry", data)


def remove_editor(name: str) -> None:
    data = host_config.get("editor_registry", {})
    if not isinstance(data, dict):
        return
    if name not in data:
        return
    del data[name]
    host_config.set("editor_registry", data)


def launch(editor_key: str, path) -> bool:
    import subprocess
    editors = list_editors()
    exe = editors.get(editor_key)
    if not exe:
        return False
    try:
        if not Path(exe).is_file():
            return False
    except OSError:
        return False

    try:
        if sys.platform == "win32" and exe.lower().endswith((".cmd", ".bat")):
            subprocess.Popen(
                ["cmd.exe", "/c", exe, str(path)],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            subprocess.Popen([exe, str(path)])
        return True
    except (OSError, FileNotFoundError):
        return False