import random
import shlex
import subprocess
import sys
import time
import threading
from pathlib import Path

from cptools.lib.compile import compile_source, default_output

from store import (
    bin_dir, clear_fails, save_fail, work_root, testlib_dir,
    DEFAULT_IO,
)
from interactive import run_interactive


HIDE_WINDOW = 0
if sys.platform == "win32":
    HIDE_WINDOW = subprocess.CREATE_NO_WINDOW


def _decode(b):
    if b is None:
        return ""
    return b.decode("utf-8", errors="replace")


def _kill(proc):
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=1)
    except Exception:
        pass


def _run_proc(cmd, stdin_bytes, timeout, cancel_event, tracker, cwd):
    kwargs = {}
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=HIDE_WINDOW,
            **kwargs,
        )
    except OSError as e:
        return {
            "rc": None, "stdout": "", "stderr": str(e),
            "elapsed": 0.0, "timeout": False, "cancelled": False,
            "error": True,
        }

    tracker.add(proc)
    start = time.monotonic()
    try:
        if stdin_bytes is not None:
            try:
                proc.stdin.write(stdin_bytes)
            except Exception:
                pass
            try:
                proc.stdin.close()
            except Exception:
                pass

        while True:
            if cancel_event.is_set():
                _kill(proc)
                return {
                    "rc": None, "stdout": "", "stderr": "",
                    "elapsed": time.monotonic() - start,
                    "timeout": False, "cancelled": True,
                }
            rc = proc.poll()
            if rc is not None:
                break
            if time.monotonic() - start > timeout:
                _kill(proc)
                return {
                    "rc": None, "stdout": "", "stderr": "",
                    "elapsed": time.monotonic() - start,
                    "timeout": True, "cancelled": False,
                }
            time.sleep(0.02)

        out_b = proc.stdout.read()
        err_b = proc.stderr.read()
        return {
            "rc": rc,
            "stdout": _decode(out_b),
            "stderr": _decode(err_b),
            "elapsed": time.monotonic() - start,
            "timeout": False,
            "cancelled": False,
        }
    finally:
        tracker.discard(proc)


def _run_target(binary, input_text, timeout, cancel_event, tracker, work_dir, io_mode):
    """Run a target with per-target I/O mode (stdin/stdout or file)."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    in_mode = io_mode.get("input", "stdin")
    out_mode = io_mode.get("output", "stdout")

    if in_mode == "file":
        in_name = io_mode.get("input_file") or "input.txt"
        in_file = work_dir / in_name
        in_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            in_file.write_text(input_text, encoding="utf-8")
        except OSError as e:
            return {
                "rc": None, "stdout": "", "stderr": f"write input failed: {e}",
                "elapsed": 0.0, "timeout": False, "cancelled": False,
                "error": True,
            }
        stdin_bytes = None
    else:
        stdin_bytes = input_text.encode("utf-8")

    out_file = None
    if out_mode == "file":
        out_name = io_mode.get("output_file") or "output.txt"
        out_file = work_dir / out_name
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if out_file.exists():
            try:
                out_file.unlink()
            except OSError:
                pass

    r = _run_proc(
        [str(binary)],
        stdin_bytes=stdin_bytes,
        timeout=timeout,
        cancel_event=cancel_event,
        tracker=tracker,
        cwd=work_dir,
    )

    if out_mode == "file" and out_file is not None and r.get("rc") is not None:
        if out_file.exists():
            try:
                r["stdout"] = out_file.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                r["stdout"] = f"<read output failed: {e}>"
        else:
            r["stdout"] = ""

    return r


def _classify(t, tl, warn_f, slow_f, fail_f):
    if t < warn_f * tl:
        return "OK"
    if t < slow_f * tl:
        return "WARN"
    if t < fail_f * tl:
        return "SLOW"
    return "TLE"


def _compare(a, b, mode):
    if mode == "exact":
        return a.rstrip() == b.rstrip()
    if mode == "line":
        al = [ln.rstrip() for ln in a.splitlines()]
        bl = [ln.rstrip() for ln in b.splitlines()]
        while al and not al[-1]:
            al.pop()
        while bl and not bl[-1]:
            bl.pop()
        return al == bl
    return a.split() == b.split()


class StressRunner:
    def __init__(
        self, global_cfg, sol_cfg, source,
        on_start=None, on_log=None, on_fail=None,
        on_progress=None, on_done=None, on_error=None,
        on_compile=None,
        cancel_event=None,
    ):
        self.gcfg = global_cfg
        self.scfg = sol_cfg
        self.source = Path(source).resolve()
        self.on_start = on_start or (lambda: None)
        self.on_log = on_log or (lambda *a: None)
        self.on_fail = on_fail or (lambda *a: None)
        self.on_progress = on_progress or (lambda *a: None)
        self.on_done = on_done or (lambda *a: None)
        self.on_error = on_error or (lambda msg: None)
        self.on_compile = on_compile or (lambda *a: None)
        self.cancel_event = cancel_event or threading.Event()
        self._procs = set()
        self.last_reason = ""
        self.last_iterations = 0
        self.last_fails = 0
        self.last_elapsed = 0.0

    def cancel(self):
        self.cancel_event.set()
        for p in list(self._procs):
            _kill(p)

    def _compute_binaries(self):
        bd = bin_dir(self.source)
        mode = self.scfg.get("mode", "standard")
        targets = {
            "sol": self.source,
            "gen": Path(self.scfg.get("generator") or ""),
        }
        if mode == "standard":
            extra = self.scfg["standard"].get("extra")
            if extra:
                targets["brute"] = Path(extra)
        elif mode == "checker":
            extra = self.scfg["checker"].get("extra")
            checker = self.scfg["checker"].get("checker")
            if extra:
                targets["brute"] = Path(extra)
            if checker:
                targets["checker"] = Path(checker)
        elif mode == "interactive":
            interactor = self.scfg["interactive"].get("extra")
            if interactor:
                targets["interactor"] = Path(interactor)
        return targets, bd

    def _compile(self):
        compiler = self.gcfg.get("compiler") or "g++"
        raw_flags = self.gcfg.get("compiler_flags") or []
        if isinstance(raw_flags, str):
            flags = raw_flags.split()
        else:
            flags = [str(x) for x in raw_flags]
        timeout = int(self.gcfg.get("compile_timeout", 60))

        tl_dir = testlib_dir()
        if (tl_dir / "testlib.h").is_file():
            flags.append(f"-I{tl_dir}")

        targets, bd = self._compute_binaries()

        result = {}
        for key, src in targets.items():
            if not src or not Path(src).is_file():
                if key in ("sol", "gen"):
                    return None, f"missing file for '{key}': {src}"
                result[key] = None
                continue
            out = default_output(src, bd)
            self.on_compile(key, "compiling", str(src))
            r = compile_source(
                src, out, compiler=compiler, flags=flags, timeout=timeout,
            )
            if not r["ok"]:
                err = r.get("stderr") or r.get("stdout") or ""
                self.on_compile(key, "failed", str(src))
                return None, f"compile failed for {key}:\n{err}"
            result[key] = out
            self.on_compile(key, "done", str(src))
        return result, None

    def run(self):
        self.on_start()

        no_compile = bool(self.gcfg.get("no_compile", False))

        if no_compile:
            targets, bd = self._compute_binaries()
            bins = {}
            for key, src in targets.items():
                if not src or not Path(src).is_file():
                    if key in ("sol", "gen"):
                        self.on_error(f"missing file for '{key}': {src}")
                        self.on_done("missing_file", 0, 0, 0.0)
                        return
                    bins[key] = None
                    continue
                out = default_output(src, bd)
                if not out.is_file():
                    self.on_error(
                        f"binary not found for {key}: {out}\n"
                        "disable 'no_compile' to build first"
                    )
                    self.on_done("missing_binary", 0, 0, 0.0)
                    return
                bins[key] = out
            self.on_compile("_skip_", "skipped", "")
        else:
            bins, err = self._compile()
            if err:
                if err == "__cancelled__":
                    self.on_done("cancelled", 0, 0, 0.0)
                else:
                    self.on_error(err)
                    self.on_done("compile_failed", 0, 0, 0.0)
                return

        sol_bin = bins["sol"]
        gen_bin = bins["gen"]
        brute_bin = bins.get("brute")
        checker_bin = bins.get("checker")

        mode = self.scfg.get("mode", "standard")
        match_mode = self.scfg["standard"].get("match_mode", "line")
        interactor_bin = bins.get("interactor")

        io_cfg = self.scfg.get("io") or {}
        sol_io = io_cfg.get("sol") or dict(DEFAULT_IO)
        brute_io = io_cfg.get("brute") or dict(DEFAULT_IO)

        tl = float(self.gcfg.get("time_limit", 1.0))
        warn_f = float(self.gcfg.get("warn_factor", 1.0))
        slow_f = float(self.gcfg.get("slow_factor", 2.0))
        fail_f = float(self.gcfg.get("fail_factor", 3.0))
        gen_timeout = float(self.gcfg.get("gen_timeout", 5.0))
        stop_on_fail = bool(self.gcfg.get("stop_on_fail", True))
        max_fails = int(self.gcfg.get("max_fails", 50))

        seed_base = int(self.scfg.get("seed", 0))
        randomize = bool(self.scfg.get("randomize_per_iter", False))
        gen_args = self.scfg.get("gen_args", "")
        try:
            extra_gen_args = shlex.split(gen_args, posix=False) if gen_args else []
        except ValueError:
            extra_gen_args = gen_args.split()

        clear_fails(self.source)

        work = work_root(self.source)
        work.mkdir(parents=True, exist_ok=True)

        rng = random.Random()

        fails = 0
        iter_n = 0
        start = time.monotonic()
        last_progress = start
        reason = "done"

        try:
            while True:
                if self.cancel_event.is_set():
                    reason = "cancelled"
                    break

                iter_n += 1
                seed = rng.randint(1, 10 ** 9) if randomize else seed_base + (iter_n - 1)

                base_wd = work / f"test_{iter_n}"
                gen_wd = base_wd / "gen"
                brute_wd = base_wd / "brute"
                sol_wd = base_wd / "sol"
                checker_wd = base_wd / "checker"
                inter_wd = base_wd / "interactive"

                # ---- gen ----
                gen_wd.mkdir(parents=True, exist_ok=True)
                gen_res = _run_proc(
                    [str(gen_bin), str(iter_n), str(seed), *extra_gen_args],
                    stdin_bytes=None,
                    timeout=gen_timeout,
                    cancel_event=self.cancel_event,
                    tracker=self._procs,
                    cwd=gen_wd,
                )
                if gen_res.get("cancelled"):
                    reason = "cancelled"
                    break
                if gen_res.get("timeout") or gen_res.get("error"):
                    self.on_error(f"generator failed at iter {iter_n}: {gen_res}")
                    reason = "gen_error"
                    break
                if gen_res.get("rc") != 0:
                    self.on_error(
                        f"generator exited rc={gen_res.get('rc')} "
                        f"at iter {iter_n}: {gen_res.get('stderr','')}"
                    )
                    reason = "gen_error"
                    break

                input_text = gen_res["stdout"]

                # ---- interactive ----
                if mode == "interactive":
                    if interactor_bin is None:
                        self.on_error("interactor not configured")
                        reason = "config_error"
                        break
                    i_res = run_interactive(
                        [str(sol_bin)],
                        [str(interactor_bin)],
                        input_text,
                        timeout=tl * fail_f,
                        cancel_event=self.cancel_event,
                        tracker=self._procs,
                        work_dir=inter_wd,
                    )
                    if i_res.get("cancelled"):
                        reason = "cancelled"
                        break
                    st = i_res["status"]
                    elapsed = i_res["elapsed"]
                    if st == "OK":
                        st = _classify(elapsed, tl, warn_f, slow_f, fail_f)
                    self.on_log(iter_n, seed, st, elapsed)
                    if st in ("WA", "RTE", "TLE"):
                        fails += 1
                        fail_dir = save_fail(
                            self.source, fails, seed, st,
                            input_text=input_text,
                            log=i_res.get("log", ""),
                            stderr=i_res.get("stderr", ""),
                        )
                        self.on_fail(fails, seed, st, elapsed, str(fail_dir))
                        if stop_on_fail:
                            reason = "fail"
                            break
                        if fails >= max_fails:
                            reason = "max_fails"
                            break
                    now = time.monotonic()
                    if now - last_progress > 0.1:
                        self.on_progress(iter_n, fails, now - start)
                        last_progress = now
                    continue

                # ---- brute ----
                expected_text = ""
                if brute_bin:
                    b_res = _run_target(
                        brute_bin, input_text,
                        timeout=tl * fail_f,
                        cancel_event=self.cancel_event,
                        tracker=self._procs,
                        work_dir=brute_wd,
                        io_mode=brute_io,
                    )
                    if b_res.get("cancelled"):
                        reason = "cancelled"
                        break
                    if b_res.get("timeout"):
                        self.on_error(
                            f"brute timed out at iter {iter_n} — "
                            "increase fail_factor or optimize brute"
                        )
                        reason = "brute_timeout"
                        break
                    if b_res.get("rc") != 0:
                        self.on_error(
                            f"brute crashed at iter {iter_n} "
                            f"rc={b_res.get('rc')}: {b_res.get('stderr','')}"
                        )
                        reason = "brute_error"
                        break
                    expected_text = b_res["stdout"]

                # ---- sol ----
                sol_res = _run_target(
                    sol_bin, input_text,
                    timeout=tl * fail_f,
                    cancel_event=self.cancel_event,
                    tracker=self._procs,
                    work_dir=sol_wd,
                    io_mode=sol_io,
                )
                if sol_res.get("cancelled"):
                    reason = "cancelled"
                    break

                elapsed = sol_res["elapsed"]

                # ---- classify ----
                if sol_res.get("timeout"):
                    status = "TLE"
                    elapsed = tl * fail_f
                elif sol_res.get("error") or sol_res.get("rc") != 0:
                    status = "RTE"
                elif mode == "checker" and checker_bin:
                    checker_wd.mkdir(parents=True, exist_ok=True)
                    inp_f = checker_wd / "input.txt"
                    got_f = checker_wd / "got.txt"
                    exp_f = checker_wd / "exp.txt"
                    inp_f.write_text(input_text, encoding="utf-8")
                    got_f.write_text(sol_res["stdout"], encoding="utf-8")
                    exp_f.write_text(expected_text, encoding="utf-8")
                    c_res = _run_proc(
                        [str(checker_bin), str(inp_f), str(got_f), str(exp_f)],
                        stdin_bytes=None,
                        timeout=5.0,
                        cancel_event=self.cancel_event,
                        tracker=self._procs,
                        cwd=checker_wd,
                    )
                    if c_res.get("cancelled"):
                        reason = "cancelled"
                        break
                    rc = c_res.get("rc")
                    if rc == 0:
                        status = _classify(elapsed, tl, warn_f, slow_f, fail_f)
                    elif rc in (1, 2, 3):
                        status = "WA"
                    else:
                        status = "RTE"
                else:
                    speed = _classify(elapsed, tl, warn_f, slow_f, fail_f)
                    if _compare(sol_res["stdout"], expected_text, match_mode):
                        status = speed
                    else:
                        status = "WA"

                self.on_log(iter_n, seed, status, elapsed)

                # ---- fail handling ----
                if status in ("WA", "RTE", "TLE"):
                    fails += 1
                    fail_dir = save_fail(
                        self.source, fails, seed, status,
                        input_text=input_text,
                        expected=expected_text,
                        got=sol_res.get("stdout", ""),
                        stderr=sol_res.get("stderr", ""),
                    )
                    self.on_fail(fails, seed, status, elapsed, str(fail_dir))
                    if stop_on_fail:
                        reason = "fail"
                        break
                    if fails >= max_fails:
                        reason = "max_fails"
                        break

                # ---- progress ----
                now = time.monotonic()
                if now - last_progress > 0.1:
                    self.on_progress(iter_n, fails, now - start)
                    last_progress = now

        except Exception as e:
            reason = "exception"
            self.on_error(f"internal error: {type(e).__name__}: {e}")

        total = time.monotonic() - start
        self.last_reason = reason
        self.last_iterations = iter_n
        self.last_fails = fails
        self.last_elapsed = total
        self.on_done(reason, iter_n, fails, total)