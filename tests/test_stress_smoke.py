import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def test_plugin_discoverable(tmp_path):
    """Verify stress plugin is discoverable by cptools."""
    data = tmp_path / "data"
    data.mkdir()
    env = os.environ.copy()
    env["CPTOOLS_PLUGIN_CONFIG_DIR"] = str(tmp_path / "cfg")
    env["CPTOOLS_PLUGIN_DATA_DIR"] = str(data)
    env["CPTOOLS_PLUGIN_CACHE_DIR"] = str(tmp_path / "cache")
    env["CPTOOLS_CONFIG_ROOT"] = str(tmp_path / "hostcfg")
    env["CPTOOLS_DATA_ROOT"] = str(tmp_path / "hostdata")

    code = (
        "from cptools import registry;"
        "plugins = registry.discover();"
        "names = [p.name for p in plugins];"
        "print('PLUGINS:', ','.join(names));"
        "assert 'stress' in names, names;"
        "print('OK')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_manifest_valid():
    import tomllib
    manifest = REPO_ROOT / "cptools" / "builtin" / "stress" / "cptools-plugin.toml"
    assert manifest.is_file()
    with manifest.open("rb") as f:
        data = tomllib.load(f)
    assert data["plugin"]["name"] == "stress"
    assert "run" in data["commands"]
    assert "gui" in data["commands"]
    assert "config" in data["commands"]