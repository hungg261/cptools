import argparse
import json
import os
import sys
from pathlib import Path

from compile import compile_source, default_output, find_compiler, is_stale
from run import run_binary, compare
from store import load, save, add_test, remove_test, find_test, work_root_for

CONFIG_DIR = Path(os.environ["CPTOOLS_PLUGIN_CONFIG_DIR"])
DATA_DIR = Path(os.environ["CPTOOLS_PLUGIN_DATA_DIR"])
CACHE_DIR = Path(os.environ["CPTOOLS_PLUGIN_CACHE_DIR"])
CONFIG_FILE = CONFIG_DIR / "config.json"
AS_JSON = os.environ.get("CPTOOLS_OUTPUT") == "json"

DEFAULTS = {
    "compiler": "g++",
    "compiler_flags": ["-O2", "-std=c++17"],
    "timeout": 5,
    "compile_timeout": 60,
    "bin_dir": "",
    "rebuild": "auto",
}


def emit_json(obj):
    print(json.dumps(obj, ensure_ascii=False))


def load_config():
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    cfg = dict(DEFAULTS)
    for k, v in data.items():
        if k in ("timeout", "compile_timeout"):
            try:
                cfg[k] = int(v)
            except (TypeError, ValueError):
                pass
        else:
            cfg[k] = v
    if not isinstance(cfg.get("compiler_flags"), list):
        cfg["compiler_flags"] = list(DEFAULTS["compiler_flags"])
    return cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _bin_dir(cfg):
    if cfg.get("bin_dir"):
        return Path(cfg["bin_dir"]).expanduser()
    return CACHE_DIR / "bin"


def _prepare(source, cfg, force_rebuild=False):
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        return None, {"error": f"source not found: {source}"}

    compiler = cfg.get("compiler") or "g++"
    if not find_compiler(compiler):
        return None, {"error": f"compiler not found in PATH: {compiler}"}

    output = default_output(source, _bin_dir(cfg))
    rebuild_mode = cfg.get("rebuild", "auto")

    need_build = force_rebuild or rebuild_mode == "always"
    if rebuild_mode == "auto" and is_stale(source, output):
        need_build = True
    if rebuild_mode == "never" and not output.is_file():
        need_build = True

    build_result = None
    if need_build:
        build_result = compile_source(
            source,
            output,
            compiler=compiler,
            flags=cfg.get("compiler_flags"),
            timeout=int(cfg.get("compile_timeout", 60)),
        )
        if not build_result["ok"]:
            return None, {"error": "compilation failed", "build": build_result}

    return {"source": source, "binary": output, "build": build_result}, None


def cmd_build(argv):
    parser = argparse.ArgumentParser(add_help=False, prog="cpt run build")
    parser.add_argument("source")
    parser.add_argument("-o", "--output")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    cfg = load_config()
    source = Path(ns.source).expanduser().resolve()
    if not source.is_file():
        print(f"source not found: {source}", file=sys.stderr)
        return 1

    output = (
        Path(ns.output).expanduser().resolve()
        if ns.output
        else default_output(source, _bin_dir(cfg))
    )
    compiler = cfg.get("compiler") or "g++"

    result = compile_source(
        source, output,
        compiler=compiler,
        flags=cfg.get("compiler_flags"),
        timeout=int(cfg.get("compile_timeout", 60)),
    )

    if AS_JSON:
        emit_json({"ok": result["ok"], "binary": str(output), **result})
    else:
        if result["ok"]:
            print(f"built: {output}")
        else:
            print("compilation failed", file=sys.stderr)
            if result["stderr"]:
                print(result["stderr"], file=sys.stderr)

    return 0 if result["ok"] else 1


def cmd_run(argv):
    parser = argparse.ArgumentParser(add_help=False, prog="cpt run run")
    parser.add_argument("source")
    parser.add_argument("-i", "--input")
    parser.add_argument("--raw")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    cfg = load_config()
    prep, err = _prepare(ns.source, cfg)
    if err:
        print(err["error"], file=sys.stderr)
        if err.get("build", {}).get("stderr"):
            print(err["build"]["stderr"], file=sys.stderr)
        return 1

    input_text = ""
    if ns.raw is not None:
        input_text = ns.raw
    elif ns.input:
        try:
            input_text = Path(ns.input).read_text(encoding="utf-8")
        except OSError as e:
            print(f"cannot read input: {e}", file=sys.stderr)
            return 1

    wd = work_root_for(prep["source"]) / "adhoc"

    result = run_binary(
        prep["binary"], input_text,
        timeout=int(cfg.get("timeout", 5)),
        work_dir=wd,
    )

    if AS_JSON:
        emit_json({
            "ok": result["ok"] and result["returncode"] == 0,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "returncode": result["returncode"],
            "timeout": result.get("timeout", False),
        })
    else:
        if result["stdout"]:
            sys.stdout.write(result["stdout"])
        if result["stderr"]:
            sys.stderr.write(result["stderr"])

    if not result["ok"] or result["returncode"] != 0:
        return 1
    return 0


def cmd_test(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("""usage:
  cpt run test <source>            run all tests
  cpt run test <source> -i ID      run one test
  cpt run test add <source> <in_file> <expected_file>
  cpt run test list <source>
  cpt run test rm <source> <id>
""")
        return 0 if argv else 2

    if argv[0] == "add":
        return _test_add(argv[1:])
    if argv[0] == "list":
        return _test_list(argv[1:])
    if argv[0] == "rm":
        return _test_rm(argv[1:])

    return _test_run(argv)


def _test_run(argv):
    parser = argparse.ArgumentParser(add_help=False, prog="cpt run test")
    parser.add_argument("source")
    parser.add_argument("-i", "--id", type=int, dest="test_id")
    parser.add_argument("--rebuild", action="store_true")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    data = load(ns.source)
    if not data["tests"]:
        print("no tests stored for this source", file=sys.stderr)
        return 1

    tests = data["tests"]
    if ns.test_id is not None:
        t = find_test(data, ns.test_id)
        if t is None:
            print(f"no test with id {ns.test_id}", file=sys.stderr)
            return 1
        tests = [t]

    cfg = load_config()
    prep, err = _prepare(ns.source, cfg, force_rebuild=ns.rebuild)
    if err:
        print(err["error"], file=sys.stderr)
        if err.get("build", {}).get("stderr"):
            print(err["build"]["stderr"], file=sys.stderr)
        return 1

    io_mode = data.get("io")
    work_root = work_root_for(prep["source"])

    results = []
    passed = 0
    for t in tests:
        wd = work_root / f"test_{t['id']}"
        r = run_binary(
            prep["binary"], t["input"],
            timeout=int(cfg.get("timeout", 5)),
            work_dir=wd,
            io_mode=io_mode,
        )
        got = r["stdout"]
        ok = r["ok"] and compare(got, t["expected"])
        if ok:
            passed += 1
        results.append({
            "id": t["id"],
            "passed": ok,
            "input": t["input"],
            "expected": t["expected"],
            "got": got,
            "stderr": r["stderr"],
            "timeout": r.get("timeout", False),
        })

    if AS_JSON:
        emit_json({
            "source": str(prep["source"]),
            "binary": str(prep["binary"]),
            "passed": passed,
            "total": len(tests),
            "results": results,
        })
    else:
        for r in results:
            mark = "PASS" if r["passed"] else "FAIL"
            print(f"[{mark}] test {r['id']}")
            if not r["passed"]:
                if r["timeout"]:
                    print("  timeout")
                else:
                    print(f"  expected: {r['expected']!r}")
                    print(f"  got:      {r['got']!r}")
        print(f"\n{passed}/{len(tests)} passed")

    return 0 if passed == len(tests) else 1


def _test_add(argv):
    parser = argparse.ArgumentParser(add_help=False, prog="cpt run test add")
    parser.add_argument("source")
    parser.add_argument("input_file")
    parser.add_argument("expected_file")
    try:
        ns = parser.parse_args(argv)
    except SystemExit:
        return 2

    try:
        input_text = Path(ns.input_file).read_text(encoding="utf-8")
        expected = Path(ns.expected_file).read_text(encoding="utf-8")
    except OSError as e:
        print(f"cannot read file: {e}", file=sys.stderr)
        return 1

    data = load(ns.source)
    tid = add_test(data, input_text, expected)
    save(data)

    if AS_JSON:
        emit_json({"ok": True, "id": tid, "source": data["source"]})
    else:
        print(f"added test {tid} for {data['source']}")
    return 0


def _test_list(argv):
    if not argv:
        print("usage: test list <source>", file=sys.stderr)
        return 2
    data = load(argv[0])
    if AS_JSON:
        emit_json(data)
        return 0
    if not data["tests"]:
        print("no tests")
        return 0
    for t in data["tests"]:
        inp = t["input"].splitlines()[0] if t["input"] else ""
        print(f"  {t['id']:3}  input={inp[:40]!r}")
    return 0


def _test_rm(argv):
    if len(argv) < 2:
        print("usage: test rm <source> <id>", file=sys.stderr)
        return 2
    source = argv[0]
    try:
        tid = int(argv[1])
    except ValueError:
        print("id must be int", file=sys.stderr)
        return 2

    data = load(source)
    if not remove_test(data, tid):
        print(f"no test with id {tid}", file=sys.stderr)
        return 1
    save(data)
    print(f"removed test {tid}")
    return 0


def cmd_gui(argv):
    source = argv[0] if argv else None
    try:
        from gui import launch
    except ImportError as e:
        print(f"GUI not available: {e}", file=sys.stderr)
        return 1
    return launch(source)


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
        if isinstance(v, list):
            print(json.dumps(v))
        else:
            print(v)
        return 0

    if sub == "set":
        if len(argv) < 3:
            return 2
        key = argv[1]
        value = " ".join(argv[2:])
        if key in ("timeout", "compile_timeout"):
            try:
                cfg[key] = int(value)
            except ValueError:
                print(f"{key} must be int", file=sys.stderr)
                return 2
        elif key == "compiler_flags":
            cfg[key] = value.split()
        elif key == "rebuild":
            if value not in ("auto", "always", "never"):
                print("rebuild must be auto|always|never", file=sys.stderr)
                return 2
            cfg[key] = value
        else:
            cfg[key] = value
        save_config(cfg)
        print(f"{key} = {cfg[key]}")
        return 0

    if sub == "reset":
        save_config(dict(DEFAULTS))
        print("reset to defaults")
        return 0

    print(f"unknown: config {sub}", file=sys.stderr)
    return 2


def print_help():
    print("""runner - compile and run competitive programming solutions

usage:
  cpt run build <source> [-o BIN]              compile only
  cpt run run <source> [-i FILE] [--raw TEXT]  compile if needed + run
  cpt run test <source> [-i ID] [--rebuild]    run stored tests
  cpt run test add <source> <in_file> <exp_file>
  cpt run test list <source>
  cpt run test rm <source> <id>
  cpt run gui [source]                         open GUI
  cpt run config [show|get|set|reset]

config keys:
  compiler           compiler executable (default: g++)
  compiler_flags     list of flags (default: -O2 -std=c++17)
  timeout            run timeout in seconds (default: 5)
  compile_timeout    compile timeout in seconds (default: 60)
  bin_dir            output dir for binaries (default: plugin cache)
  rebuild            auto | always | never (default: auto)
""")


COMMANDS = {
    "build": cmd_build,
    "run": cmd_run,
    "test": cmd_test,
    "gui": cmd_gui,
    "config": cmd_config,
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