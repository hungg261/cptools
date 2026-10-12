import os
import subprocess
import sys
import threading
import time
from pathlib import Path


HIDE_WINDOW = 0
if sys.platform == "win32":
    HIDE_WINDOW = subprocess.CREATE_NO_WINDOW


def _kill(proc):
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=1)
    except Exception:
        pass


def _decode(b):
    if b is None:
        return ""
    if isinstance(b, str):
        return b
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("utf-8", errors="replace")


class _PipeForwarder(threading.Thread):
    """Reads bytes from src fileobj, writes to dst fileobj, logs chunks."""

    def __init__(self, src, dst, log, log_lock, prefix):
        super().__init__(daemon=True)
        self.src = src
        self.dst = dst
        self.log = log
        self.log_lock = log_lock
        self.prefix = prefix
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            src_fd = self.src.fileno()
        except Exception:
            return
        while not self._stop_event.is_set():
            try:
                chunk = os.read(src_fd, 4096)
            except (OSError, ValueError):
                break
            if not chunk:
                break
            try:
                self.dst.write(chunk)
                self.dst.flush()
            except (OSError, ValueError, BrokenPipeError):
                break
            with self.log_lock:
                self.log.append((self.prefix, chunk))
        try:
            self.dst.close()
        except Exception:
            pass
        try:
            self.src.close()
        except Exception:
            pass


def run_interactive(
    sol_cmd,
    interactor_cmd,
    input_text,
    timeout,
    cancel_event,
    tracker,
    work_dir,
    interactor_args=None,
):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    input_file = work_dir / "input.txt"
    output_file = work_dir / "output.txt"
    answer_file = work_dir / "answer.txt"

    input_file.write_bytes(input_text.encode("utf-8"))
    output_file.write_bytes(b"")
    answer_file.write_bytes(b"")

    inter_argv = list(interactor_cmd) + [
        input_file.name,
        output_file.name,
        answer_file.name,
    ]
    if interactor_args:
        inter_argv.extend(interactor_args)

    try:
        sol_proc = subprocess.Popen(
            list(sol_cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(work_dir),
            bufsize=0,
            creationflags=HIDE_WINDOW,
        )
    except OSError as e:
        return _err(str(e))

    try:
        inter_proc = subprocess.Popen(
            inter_argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(work_dir),
            bufsize=0,
            creationflags=HIDE_WINDOW,
        )
    except OSError as e:
        _kill(sol_proc)
        return _err(str(e))

    tracker.add(sol_proc)
    tracker.add(inter_proc)

    log = []
    log_lock = threading.Lock()

    fwd_a = _PipeForwarder(sol_proc.stdout, inter_proc.stdin, log, log_lock, ">>")
    fwd_b = _PipeForwarder(inter_proc.stdout, sol_proc.stdin, log, log_lock, "<<")
    fwd_a.start()
    fwd_b.start()

    start = time.monotonic()
    timeout_flag = False
    cancelled = False

    try:
        while True:
            if cancel_event.is_set():
                cancelled = True
                _kill(inter_proc)
                _kill(sol_proc)
                break

            if inter_proc.poll() is not None:
                break

            if time.monotonic() - start > timeout:
                timeout_flag = True
                _kill(inter_proc)
                _kill(sol_proc)
                break

            time.sleep(0.02)

        try:
            sol_proc.wait(timeout=1.5)
        except Exception:
            _kill(sol_proc)
        try:
            inter_proc.wait(timeout=1.5)
        except Exception:
            _kill(inter_proc)

        elapsed = time.monotonic() - start
    finally:
        tracker.discard(sol_proc)
        tracker.discard(inter_proc)

    # Let forwarders drain remaining bytes from pipes. They exit naturally
    # when the src end hits EOF (process exit closes stdout). Only force-stop
    # if they're still alive after a grace period (e.g. pipe held open).
    for _ in range(30):
        if not fwd_a.is_alive() and not fwd_b.is_alive():
            break
        time.sleep(0.05)

    for fwd in (fwd_a, fwd_b):
        if fwd.is_alive():
            fwd.stop()
        try:
            fwd.join(timeout=1.5)
        except Exception:
            pass

    inter_rc = inter_proc.returncode
    sol_rc = sol_proc.returncode

    log_parts = []
    with log_lock:
        for prefix, chunk in log:
            text = _decode(chunk).rstrip()
            for line in text.splitlines():
                log_parts.append(f"{prefix} {line}")
    log_text = "\n".join(log_parts)

    inter_stderr = ""
    sol_stderr = ""
    try:
        inter_stderr = _decode(inter_proc.stderr.read())
    except Exception:
        pass
    try:
        sol_stderr = _decode(sol_proc.stderr.read())
    except Exception:
        pass

    stderr_text = ""
    if sol_stderr.strip():
        stderr_text += f"[solver stderr]\n{sol_stderr.strip()}\n"
    if inter_stderr.strip():
        stderr_text += f"[interactor stderr]\n{inter_stderr.strip()}\n"
    stderr_text = stderr_text.strip()

    if cancelled:
        status = "CANCELLED"
    elif timeout_flag:
        status = "TLE"
    elif sol_rc is None or sol_rc != 0:
        status = "RTE"
    elif inter_rc == 0:
        status = "OK"
    elif inter_rc in (1, 2, 3):
        status = "WA"
    else:
        status = "RTE"

    return {
        "status": status,
        "elapsed": elapsed,
        "rc": inter_rc,
        "sol_rc": sol_rc,
        "log": log_text,
        "stderr": stderr_text,
        "timeout": timeout_flag,
        "cancelled": cancelled,
    }


def _err(msg):
    return {
        "status": "RTE",
        "elapsed": 0.0,
        "rc": None,
        "sol_rc": None,
        "log": "",
        "stderr": msg,
        "timeout": False,
        "cancelled": False,
    }