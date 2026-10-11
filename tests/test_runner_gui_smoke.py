import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "runner"


def _make_env(tmp_root):
    env = os.environ.copy()
    env["CPTOOLS_PLUGIN_NAME"] = "runner"
    env["CPTOOLS_INVOKED_AS"] = "run"
    env["CPTOOLS_PLUGIN_CONFIG_DIR"] = str(tmp_root / "cfg")
    env["CPTOOLS_PLUGIN_DATA_DIR"] = str(tmp_root / "data")
    env["CPTOOLS_PLUGIN_CACHE_DIR"] = str(tmp_root / "cache")
    env["CPTOOLS_PROTOCOL"] = "1"
    env["CPTOOLS_OUTPUT"] = "human"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def test_gui_imports(tmp_path):
    env = _make_env(tmp_path)
    code = (
        "import sys;"
        "sys.path.insert(0, r'" + str(PLUGIN_DIR) + "');"
        "import gui;"
        "print('OK')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        env=env, capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


@pytest.mark.skipif(
    sys.platform.startswith("linux") and not os.environ.get("DISPLAY"),
    reason="no DISPLAY",
)
def test_gui_launch_and_close(tmp_path):
    env = _make_env(tmp_path)

    code = (
        "import sys\n"
        f"sys.path.insert(0, r'{PLUGIN_DIR}')\n"
        "import tkinter as tk\n"
        "from gui import RunnerApp\n"
        "root = tk.Tk()\n"
        "app = RunnerApp(root)\n"
        "root.after(500, root.destroy)\n"
        "root.mainloop()\n"
        "print('OK')\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=15,
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout