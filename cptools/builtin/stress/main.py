import argparse
import json
import os
import sys
import threading

from cptools.lib.compile import find_compiler
from store import (
    load_config, save_config, load_solution, save_solution,
    DEFAULT_CONFIG, work_root, fails_dir,
)
from loop import StressRunner

AS_JSON = os.environ.get("CPTOOLS_OUTPUT") == "json"


def emit_json(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


# ---------- logging ----------

_STATUS_COLORS = {
    "OK":   "\033[32m",   # green
    "WARN": "\033[33m",   # yellow
    "SLOW": "\033[38;5;208m",  # orange
    "WA":   "\033[31m",   # red
    "TLE":  "\033[31m",
    "RTE":  "\033[35m",   # magenta
}
_RESET = "\033[0m"


def _colored(status):
    if not sys.stdout.isatty():
        return f"[{status}]"
    c = _STATUS_COLORS.get(status, "")
    return f"{c}[{status}]{_RESET}" if c else f"[{status}]"


# ---------- run ----------

def cmd_run(argv):
    parser = argparse.ArgumentParser(add_help=False, prog="cpt stress run")
    parser.add_argument("source")
    parser.add_argument("--gen", "-g", dest="generator", required=True)
    parser.add_argument("--brute", "-b", dest="brute")
    parser.add_argument("--checker", "-c", dest="checker")
    parser.add_argument(
        "-m", "--mode",
        choices=["standard", "checker"],
        default=None,
    )
    parser.add_argument("--seed", "-s", type=int)
    parser.add_argument("--randomize-seed", action="store_true")
    parser.add_argument("--gen-args", default=None)
    parser.add_argument("--match", choices=["token", "exact", "whitespace"])
    parser.add_argument("--max-fails", type=int)
    parser.add_argument("--no-stop-on-fail", action="store_true")
    parser.add_argument("--time-limit", type=float)
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    if not os.path.isfile(ns.source):
        print(f"source not found: {ns.source}", file=sys.stderr)
        return 1
    if not os.path.isfile(ns.generator):
        print(f"generator not found: {ns.generator}", file=sys.stderr)
        return 1

    mode = ns.mode
    if not mode:
        if ns.checker:
            mode = "checker"
        else:
            mode = "standard"

    if mode == "checker":
        if not ns.checker:
            print("--checker is required for checker mode", file=sys.stderr)
            return 2
        if not ns.brute:
            print("--brute is required for checker mode", file=sys.stderr)
            return 2
    else:
        if not ns.brute:
            print("--brute is required for standard mode", file=sys.stderr)
            return 2

    scfg = load_solution(ns.source)
    scfg["generator"] = ns.generator
    scfg["mode"] = mode

    if mode == "standard":
        scfg["standard"]["extra"] = ns.brute
        if ns.match:
            scfg["standard"]["match_mode"] = ns.match
    else:
        scfg["checker"]["extra"] = ns.brute
        scfg["checker"]["checker"] = ns.checker

    if ns.seed is not None:
        scfg["seed"] = ns.seed
    if ns.randomize_seed:
        scfg["randomize_per_iter"] = True
    if ns.gen_args is not None:
        scfg["gen_args"] = ns.gen_args

    save_solution(scfg)

    gcfg = load_config()
    if ns.time_limit is not None:
        gcfg["time_limit"] = ns.time_limit
    if ns.max_fails is not None:
        gcfg["max_fails"] = ns.max_fails
    if ns.no_stop_on_fail:
        gcfg["stop_on_fail"] = False

    compiler = gcfg.get("compiler") or "g++"
    if not find_compiler(compiler):
        print(f"compiler not found: {compiler}", file=sys.stderr)
        return 1

    cancel_event = threading.Event()
    stopped = {"flag": False}

    def on_log(iter_n, seed, status, elapsed):
        if AS_JSON:
            emit_json({
                "type": "log",
                "iter": iter_n,
                "seed": seed,
                "status": status,
                "elapsed": round(elapsed, 4),
            })
        else:
            print(
                f"{iter_n:>6}  seed={seed:<10}  {_colored(status):>14}  "
                f"{elapsed:.3f}s",
                flush=True,
            )

    def on_fail(idx, seed, status, elapsed, fail_dir):
        if AS_JSON:
            emit_json({
                "type": "fail",
                "index": idx,
                "seed": seed,
                "status": status,
                "elapsed": round(elapsed, 4),
                "dir": fail_dir,
            })

    def on_error(msg):
        if AS_JSON:
            emit_json({"type": "error", "message": msg})
        else:
            print(f"error: {msg}", file=sys.stderr)

    def on_done(reason, total_iters, fails, elapsed):
        if AS_JSON:
            emit_json({
                "type": "done",
                "reason": reason,
                "iterations": total_iters,
                "fails": fails,
                "elapsed": round(elapsed, 3),
                "fails_dir": str(fails_dir(ns.source)) if fails else "",
            })
        else:
            print()
            print(
                f"{reason} — {total_iters} iterations, "
                f"{fails} fails, {elapsed:.2f}s"
            )
            if fails:
                print(f"fails saved to: {fails_dir(ns.source)}")

    runner = StressRunner(
        gcfg, scfg, ns.source,
        on_log=on_log,
        on_fail=on_fail,
        on_error=on_error,
        on_done=on_done,
        cancel_event=cancel_event,
    )

    def _sigint(sig, frame):
        if stopped["flag"]:
            raise KeyboardInterrupt
        stopped["flag"] = True
        cancel_event.set()
        print("\nstopping...", file=sys.stderr)

    try:
        import signal
        signal.signal(signal.SIGINT, _sigint)
    except (ValueError, AttributeError):
        pass

    runner.run()
    return 0


# ---------- config ----------

def cmd_config(argv):
    cfg = load_config()

    if not argv or argv[0] in ("show", "-h", "--help"):
        if argv and argv[0] in ("-h", "--help"):
            print("usage: config [show | get KEY | set KEY VALUE | reset]")
            return 0
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0

    sub = argv[0]

    if sub == "get":
        if len(argv) < 2:
            return 2
        v = cfg.get(argv[1])
        if v is None:
            return 1
        if isinstance(v, (list, dict)):
            print(json.dumps(v))
        else:
            print(v)
        return 0

    if sub == "set":
        if len(argv) < 3:
            return 2
        key = argv[1]
        value = " ".join(argv[2:])
        if key in ("time_limit", "warn_factor", "slow_factor",
                   "fail_factor", "gen_timeout"):
            try:
                cfg[key] = float(value)
            except ValueError:
                print(f"{key} must be float", file=sys.stderr)
                return 2
        elif key == "max_fails" or key == "compile_timeout":
            try:
                cfg[key] = int(value)
            except ValueError:
                print(f"{key} must be int", file=sys.stderr)
                return 2
        elif key == "stop_on_fail":
            cfg[key] = value.lower() in ("1", "true", "yes", "on")
        elif key == "compiler_flags":
            cfg[key] = value.split()
        elif key == "match_mode":
            if value not in ("token", "exact", "whitespace"):
                print("match_mode must be token|exact|whitespace", file=sys.stderr)
                return 2
            cfg[key] = value
        else:
            cfg[key] = value
        save_config(cfg)
        print(f"{key} = {cfg[key]}")
        return 0

    if sub == "reset":
        save_config(dict(DEFAULT_CONFIG))
        print("reset to defaults")
        return 0

    print(f"unknown: config {sub}", file=sys.stderr)
    return 2


# ---------- gui (stub) ----------

def cmd_gui(argv):
    try:
        from gui import launch
    except ImportError as e:
        print(f"GUI not available: {e}", file=sys.stderr)
        return 1
    source = argv[0] if argv else None
    return launch(source)


# ---------- help ----------

def print_help():
    print("""stress - auto stress-test competitive programming solutions

usage:
  cpt stress run <source> --gen GEN.cpp --brute B.cpp [opts]
  cpt stress run <source> --gen GEN.cpp --brute B.cpp --checker C.cpp
  cpt stress gui [source]                       open GUI
  cpt stress config [show|get|set|reset]

run options:
  -g, --gen FILE         generator source
  -b, --brute FILE       brute force source
  -c, --checker FILE     checker source (implies --mode checker)
  -m, --mode MODE        standard | checker
  -s, --seed N           starting seed (default: from config)
  --randomize-seed       randomize seed per iteration
  --gen-args ARGS        extra args passed to generator after seed
  --match MODE           token | exact | whitespace
  --max-fails N          stop after N fails
  --no-stop-on-fail      keep going after fails
  --time-limit SEC       override time limit

config keys:
  compiler           compiler executable (default: g++)
  compiler_flags     flags (default: -O2 -std=c++17)
  compile_timeout    compile timeout in seconds (default: 60)
  time_limit         per-run time limit (default: 1.0)
  warn_factor        WARN threshold multiplier (default: 1.0)
  slow_factor        SLOW threshold multiplier (default: 2.0)
  fail_factor        TLE threshold multiplier (default: 3.0)
  gen_timeout        generator timeout (default: 5.0)
  match_mode         default match mode
  stop_on_fail       stop on first fail (default: true)
  max_fails          max fails to collect (default: 50)
""")


# ---------- dispatch ----------

COMMANDS = {
    "run": cmd_run,
    "config": cmd_config,
    "gui": cmd_gui,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print_help()
        return 0
    cmd = argv[0]
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print_help()
        return 2
    return COMMANDS[cmd](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))