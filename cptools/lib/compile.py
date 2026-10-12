import shutil
import subprocess
import sys
from pathlib import Path


def find_compiler(name):
    return shutil.which(name)


def default_output(source, bin_dir):
    stem = Path(source).stem
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    ext = ".exe" if sys.platform == "win32" else ""
    return bin_dir / f"{stem}{ext}"


def compile_source(source, output, compiler="g++", flags=None, timeout=60):
    flags = list(flags) if flags is not None else ["-O2", "-std=c++17"]
    cmd = [compiler, *flags, str(source), "-o", str(output)]

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        return {
            "ok": r.returncode == 0,
            "cmd": cmd,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False, "cmd": cmd, "stdout": "",
            "stderr": "compilation timed out", "returncode": -1,
        }
    except FileNotFoundError:
        return {
            "ok": False, "cmd": cmd, "stdout": "",
            "stderr": f"compiler not found: {compiler}", "returncode": -1,
        }
    except OSError as e:
        return {
            "ok": False, "cmd": cmd, "stdout": "",
            "stderr": str(e), "returncode": -1,
        }


def is_stale(source, output):
    s = Path(source)
    o = Path(output)
    if not s.is_file() or not o.is_file():
        return True
    try:
        return s.stat().st_mtime > o.stat().st_mtime
    except OSError:
        return True