import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "link-manager"


@pytest.fixture
def plugin_dirs(tmp_path):
    dirs = {
        "config": tmp_path / "config",
        "data": tmp_path / "data",
        "cache": tmp_path / "cache",
        "work": tmp_path / "work",
        "host_config": tmp_path / "host_config",
        "host_data": tmp_path / "host_data",
    }
    for d in dirs.values():
        d.mkdir()
    return dirs


@pytest.fixture
def run_plugin(plugin_dirs):
    def _run(*args, output="human", input=""):
        env = os.environ.copy()
        env["CPTOOLS_PLUGIN_NAME"] = "link-manager"
        env["CPTOOLS_INVOKED_AS"] = "link"
        env["CPTOOLS_PLUGIN_CONFIG_DIR"] = str(plugin_dirs["config"])
        env["CPTOOLS_PLUGIN_DATA_DIR"] = str(plugin_dirs["data"])
        env["CPTOOLS_PLUGIN_CACHE_DIR"] = str(plugin_dirs["cache"])
        env["CPTOOLS_CONFIG_ROOT"] = str(plugin_dirs["host_config"])
        env["CPTOOLS_DATA_ROOT"] = str(plugin_dirs["host_data"])
        env["CPTOOLS_PROTOCOL"] = "1"
        env["CPTOOLS_OUTPUT"] = output
        env["CPTOOLS_CWD"] = str(plugin_dirs["work"])
        return subprocess.run(
            [sys.executable, "main.py", *args],
            cwd=PLUGIN_DIR,
            env=env,
            capture_output=True,
            text=True,
            input=input,
        )
    return _run