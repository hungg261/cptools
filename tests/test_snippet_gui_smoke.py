import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "snippet"


def _make_env(tmp_root):
    env = os.environ.copy()
    env["CPTOOLS_PLUGIN_NAME"] = "snippet"
    env["CPTOOLS_INVOKED_AS"] = "snip"
    env["CPTOOLS_PLUGIN_CONFIG_DIR"] = str(tmp_root / "cfg")
    env["CPTOOLS_PLUGIN_DATA_DIR"] = str(tmp_root / "data")
    env["CPTOOLS_PLUGIN_CACHE_DIR"] = str(tmp_root / "cache")
    env["CPTOOLS_CONFIG_ROOT"] = str(tmp_root / "hostcfg")
    env["CPTOOLS_DATA_ROOT"] = str(tmp_root / "hostdata")
    env["CPTOOLS_PROTOCOL"] = "1"
    env["CPTOOLS_OUTPUT"] = "human"
    env["PYTHONIOENCODING"] = "utf-8"
    for d in ("cfg", "data", "cache", "hostcfg", "hostdata"):
        (tmp_root / d).mkdir(parents=True, exist_ok=True)
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


def test_manifest_valid():
    import tomllib
    manifest = PLUGIN_DIR / "cptools-plugin.toml"
    assert manifest.is_file()
    with manifest.open("rb") as f:
        data = tomllib.load(f)
    assert data["plugin"]["name"] == "snippet"
    assert "list" in data["commands"]
    assert "copy" in data["commands"]
    assert "gui" in data["commands"]


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
        "from gui import SnippetApp\n"
        "root = tk.Tk()\n"
        "app = SnippetApp(root)\n"
        "root.after(500, root.destroy)\n"
        "root.mainloop()\n"
        "print('OK')\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=20,
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout