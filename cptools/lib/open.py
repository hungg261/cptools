import os
import shutil
import subprocess
import sys
from pathlib import Path


def _is_windows() -> bool:
    return sys.platform == "win32"


def _is_mac() -> bool:
    return sys.platform == "darwin"


def open_file(path) -> None:
    path = Path(path)
    if _is_windows():
        os.startfile(str(path))
    elif _is_mac():
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def open_folder(path) -> None:
    path = Path(path)
    if _is_windows():
        os.startfile(str(path))
    elif _is_mac():
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def reveal_file(path) -> None:
    path = Path(path).resolve()
    folder = path.parent

    if _is_windows():
        subprocess.Popen(["explorer", "/select,", str(path)])
        return

    if _is_mac():
        subprocess.Popen(["open", "-R", str(path)])
        return

    for fm in ("nautilus", "dolphin"):
        if shutil.which(fm):
            subprocess.Popen([fm, "--select", str(path)])
            return

    for fm in ("nemo", "thunar", "caja", "pcmanfm"):
        if shutil.which(fm):
            subprocess.Popen([fm, str(folder)])
            return

    open_folder(folder)


def open_with(path, exe: str, args: list[str] | None = None) -> None:
    args = args or []
    cmd = [exe, *args, str(path)]
    if _is_windows() and exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd.exe", "/c", *cmd]
    subprocess.Popen(cmd)