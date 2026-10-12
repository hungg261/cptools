import os
import shutil
import subprocess
import sys


def copy(text) -> bool:
    if text is None:
        text = ""
    if not isinstance(text, str):
        text = str(text)
    data = text.encode("utf-8")

    if sys.platform == "win32":
        return _run(["clip"], data)
    if sys.platform == "darwin":
        return _run(["pbcopy"], data)

    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        return _run(["wl-copy"], data)
    if shutil.which("xclip"):
        return _run(["xclip", "-selection", "clipboard"], data)
    if shutil.which("xsel"):
        return _run(["xsel", "-ib"], data)
    return False


def _run(cmd, data) -> bool:
    try:
        r = subprocess.run(cmd, input=data, timeout=5)
        return r.returncode == 0
    except Exception:
        return False