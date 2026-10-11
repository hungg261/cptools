import subprocess


def run_binary(binary, input_text="", timeout=5):
    try:
        r = subprocess.run(
            [str(binary)],
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        return {
            "ok": True,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False, "stdout": "", "stderr": "timeout",
            "returncode": -1, "timeout": True,
        }
    except FileNotFoundError:
        return {
            "ok": False, "stdout": "", "stderr": f"not found: {binary}",
            "returncode": -1,
        }
    except OSError as e:
        return {
            "ok": False, "stdout": "", "stderr": str(e), "returncode": -1,
        }


def compare(got, expected):
    return got.rstrip() == expected.rstrip()