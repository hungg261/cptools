import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "runner"

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" and not os.environ.get("DISPLAY"),
    reason="no display",
)


def test_gui_imports():
    env = os.environ.copy()
    env["CPTOOLS_PLUGIN_NAME"] = "runner"
    env["CPTOOLS_PLUGIN_CONFIG_DIR"] = os.environ.get("TMPDIR", "/tmp") + "/cptg-cfg"
    env["CPTOOLS_PLUGIN_DATA_DIR"] = os.environ.get("TMPDIR", "/tmp") + "/cptg-data"
    env["CPTOOLS_PLUGIN_CACHE_DIR"] = os.environ.get("TMPDIR", "/tmp") + "/cptg-cache"

    code = (
        "import sys;"
        "sys.path.insert(0, r'" + str(PLUGIN_DIR) + "');"
        "import gui;"
        "print('OK')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_gui_launch_and_close():
    """Open GUI, close after 1s. Requires display."""
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("no DISPLAY")
    if sys.platform == "darwin" and not os.environ.get("DISPLAY"):
        pytest.skip("no DISPLAY")

    code = f"""
import sys
sys.path.insert(0, r'{PLUGIN_DIR}')
import tkinter as tk
from gui import RunnerApp
root = tk.Tk()
app = RunnerApp(root)
root.after(500, root.destroy)
root.mainloop()
print('OK')
"""
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=15,
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout