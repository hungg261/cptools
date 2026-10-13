import subprocess
from pathlib import Path


def run_binary(binary, input_text="", timeout=5, work_dir=None, io_mode=None):
    binary = Path(binary)
    work_dir = Path(work_dir) if work_dir else binary.parent
    work_dir.mkdir(parents=True, exist_ok=True)

    io_mode = io_mode or {}
    in_mode = io_mode.get("input", "stdin")
    out_mode = io_mode.get("output", "stdout")

    in_path = None
    out_path = None

    try:
        if in_mode == "file":
            input_file = io_mode.get("input_file") or "input.txt"
            in_path = work_dir / input_file
            try:
                in_path.write_text(input_text, encoding="utf-8")
            except OSError as e:
                return {
                    "ok": False, "stdout": "", "returncode": -1,
                    "stderr": f"cannot write input file: {e}",
                }

        if out_mode == "file":
            output_file = io_mode.get("output_file") or "output.txt"
            out_path = work_dir / output_file
            if out_path.exists():
                try:
                    out_path.unlink()
                except OSError:
                    pass

        stdin_text = input_text if in_mode == "stdin" else ""

        r = subprocess.run(
            [str(binary)],
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            cwd=work_dir,
        )

        if out_mode == "file":
            if out_path and out_path.exists():
                try:
                    stdout = out_path.read_text(encoding="utf-8")
                except OSError as e:
                    stdout = f"<cannot read output file: {e}>"
            else:
                stdout = ""
        else:
            stdout = r.stdout

        return {
            "ok": True,
            "stdout": stdout,
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


def _compare_line(a, b):
    al = [ln.rstrip() for ln in a.splitlines()]
    bl = [ln.rstrip() for ln in b.splitlines()]
    while al and not al[-1]:
        al.pop()
    while bl and not bl[-1]:
        bl.pop()
    return al == bl


def _compare_token(a, b):
    return a.split() == b.split()


def _compare_exact(a, b):
    return a.rstrip() == b.rstrip()


def compare(a, b, mode="line"):
    if mode == "exact":
        return _compare_exact(a, b)
    if mode == "token":
        return _compare_token(a, b)
    return _compare_line(a, b)