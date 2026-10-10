import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path


@dataclass
class Editor:
    key: str
    label: str
    exe: str
    args: list[str] = field(default_factory=list)


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


def detect_editors() -> dict[str, Editor]:
    result = {}
    for key, label, exe, extra in KNOWN:
        path = _resolve_exe(exe, extra)
        if path:
            result[key] = Editor(key=key, label=label, exe=path)
    return result


def get_editors(user_editors: dict | None = None) -> dict[str, Editor]:
    result = detect_editors()
    for key, exe in (user_editors or {}).items():
        if not exe:
            continue
        exe = str(exe)
        label = _LABELS.get(key, key)
        if key in result:
            result[key] = replace(result[key], exe=exe, label=label)
        else:
            result[key] = Editor(key=key, label=label, exe=exe)
    return result


def ordered_keys(editors: dict[str, Editor]) -> list[str]:
    order = [k for k, *_ in KNOWN if k in editors]
    extra = [k for k in editors if k not in order]
    return order + sorted(extra)


def known_editors() -> list[tuple[str, str]]:
    return [(key, label) for key, label, *_ in KNOWN]


def launch(editor: Editor, path) -> None:
    cmd = [editor.exe, *editor.args, str(path)]
    if sys.platform == "win32" and editor.exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd.exe", "/c", *cmd]
    subprocess.Popen(cmd)