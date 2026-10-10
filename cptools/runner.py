import os
import subprocess
import sys

from . import paths
from .console import err_console
from .manifest import Plugin


PYTHON_FAMILY = {"python", "python3", "python.exe", "python3.exe", "py", "py.exe"}


def _resolve_cmd(exec_list: list[str]) -> list[str]:
    if not exec_list:
        return exec_list
    first_lower = exec_list[0].lower()
    if first_lower in PYTHON_FAMILY:
        return [sys.executable, *exec_list[1:]]
    if exec_list[0].endswith(".py"):
        return [sys.executable, *exec_list]
    return list(exec_list)


def run(plugin: Plugin, args: list[str], invoked_as: str, as_json: bool = False) -> int:
    env = os.environ.copy()
    env["CPTOOLS_PLUGIN_NAME"] = plugin.name
    env["CPTOOLS_INVOKED_AS"] = invoked_as
    env["CPTOOLS_PLUGIN_CONFIG_DIR"] = str(paths.plugin_config_dir(plugin.name))
    env["CPTOOLS_PLUGIN_DATA_DIR"] = str(paths.plugin_data_dir(plugin.name))
    env["CPTOOLS_PLUGIN_CACHE_DIR"] = str(paths.plugin_cache_dir(plugin.name))
    env["CPTOOLS_PROTOCOL"] = str(plugin.protocol)
    env["CPTOOLS_OUTPUT"] = "json" if as_json else "human"
    env["CPTOOLS_CWD"] = os.getcwd()
    if "PYTHONIOENCODING" not in env:
        env["PYTHONIOENCODING"] = "utf-8"

    cmd = [*_resolve_cmd(plugin.exec), *args]

    try:
        proc = subprocess.run(cmd, env=env, cwd=plugin.path)
    except FileNotFoundError:
        err_console.print(f"[red]error[/red] cannot run '{plugin.name}': {cmd[0]}")
        return 127
    return proc.returncode