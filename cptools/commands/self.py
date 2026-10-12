import os
import platform
import shutil
import sys
from pathlib import Path

from .. import __version__, paths
from ..console import console, err_console


def handle(args):
    if not args or args[0] in ("-h", "--help"):
        print_help()
        return 0

    action = args[0]
    rest = args[1:]

    if action == "paths":
        return cmd_paths(rest)
    if action == "version":
        return cmd_version(rest)
    if action == "doctor":
        return cmd_doctor(rest)
    if action == "reset":
        return cmd_reset(rest)

    err_console.print(f"[red]error[/red] unknown subcommand: self {action}")
    return 2


def print_help():
    console.print(
        "[bold]Usage:[/bold]\n"
        "  cpt self paths                  show config/data/cache paths\n"
        "  cpt self version                show versions and platform\n"
        "  cpt self doctor                 check environment\n"
        "  cpt self reset [opts]           delete data / cache / config\n"
        "\n"
        "[bold]reset options:[/bold]\n"
        "  --data                delete plugin data and shared history\n"
        "  --cache               delete plugin cache\n"
        "  --config              delete config files\n"
        "  --plugin NAME         delete data + cache of one plugin\n"
        "  --with-config         with --plugin, also delete its config\n"
        "  --all                 delete everything (data + cache + config)\n"
        "  -y, --yes             skip confirmation\n"
    )


# =================================================================== helpers

def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024.0
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n / 1024:.1f} TB"


def _confirm(message: str) -> bool:
    if sys.stdin.isatty():
        try:
            import questionary
            ans = questionary.confirm(message).ask()
            return bool(ans)
        except Exception:
            pass
    try:
        ans = input(f"{message} [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def _safe_rmtree(path: Path):
    """Remove path. Returns (existed, ok, size)."""
    if not path.exists():
        return (False, True, 0)
    size = _dir_size(path)
    try:
        shutil.rmtree(path)
        return (True, True, size)
    except Exception as e:
        err_console.print(f"[red]error[/red] cannot delete {path}: {e}")
        return (True, False, size)


def _rmfile(path: Path):
    if not path.exists():
        return (False, True, 0)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    try:
        path.unlink()
        return (True, True, size)
    except Exception as e:
        err_console.print(f"[red]error[/red] cannot delete {path}: {e}")
        return (True, False, size)


# =================================================================== paths

def cmd_paths(args):
    cfg = paths.config_root()
    data = paths.data_root()
    print(f"config  {cfg}")
    print(f"data    {data}")
    print(f"cache   {data / 'cache'}")
    return 0


# =================================================================== version

def cmd_version(args):
    py = f"{platform.python_version()} ({sys.executable})"
    plat = platform.platform()
    print(f"cptools  {__version__}")
    print(f"python   {py}")
    print(f"platform {plat}")
    return 0


# =================================================================== doctor

def _check_import(name):
    try:
        mod = __import__(name)
        ver = getattr(mod, "__version__", "?")
        return (True, str(ver))
    except Exception as e:
        return (False, str(e))


def cmd_doctor(args):
    ok_count = 0
    warn_count = 0

    def ok(msg):
        nonlocal ok_count
        ok_count += 1
        console.print(f"[green][OK][/green]   {msg}")

    def warn(msg):
        nonlocal warn_count
        warn_count += 1
        console.print(f"[yellow][WARN][/yellow] {msg}")

    def bad(msg):
        nonlocal warn_count
        warn_count += 1
        console.print(f"[red][FAIL][/red] {msg}")

    v = sys.version_info
    if v >= (3, 11):
        ok(f"python {platform.python_version()}")
    else:
        bad(f"python {platform.python_version()} (need >= 3.11)")

    for pkg in ("platformdirs", "rich", "questionary"):
        good, info = _check_import(pkg)
        if good:
            ok(f"{pkg} {info}")
        else:
            bad(f"{pkg}: {info}")

    from ..lib.compile import find_compiler
    if find_compiler("g++"):
        ok("compiler g++")
    elif find_compiler("clang++"):
        warn("g++ not found, but clang++ is available")
    else:
        warn("no C++ compiler found in PATH (g++ or clang++)")

    try:
        from ..registry import discover
        plugins = discover()
        ok(f"{len(plugins)} plugin(s) discovered")
        for p in plugins:
            if p.builtin:
                continue
            ok(f"  user plugin: {p.name} v{p.version}")
    except Exception as e:
        bad(f"plugin discovery failed: {e}")

    for label, path in (
        ("config", paths.config_root()),
        ("data", paths.data_root()),
        ("cache", paths.data_root() / "cache"),
    ):
        test = path / ".cptools_write_test"
        try:
            path.mkdir(parents=True, exist_ok=True)
            test.write_text("x", encoding="utf-8")
            test.unlink()
            ok(f"{label} writable ({path})")
        except Exception as e:
            bad(f"{label} not writable ({path}): {e}")

    console.print()
    if warn_count == 0:
        console.print(f"[green]all checks passed[/green] ({ok_count})")
    else:
        console.print(f"{ok_count} ok, {warn_count} warn/fail")

    return 0 if warn_count == 0 else 1


# =================================================================== reset

def cmd_reset(args):
    if not args or args[0] in ("-h", "--help"):
        print_help()
        return 0

    do_data = False
    do_cache = False
    do_config = False
    do_all = False
    plugin_name = None
    with_config = False
    skip_confirm = False

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--data":
            do_data = True
        elif a == "--cache":
            do_cache = True
        elif a == "--config":
            do_config = True
        elif a == "--all":
            do_all = True
        elif a == "--plugin":
            if i + 1 >= len(args):
                err_console.print("[red]error[/red] --plugin requires a name")
                return 2
            plugin_name = args[i + 1]
            i += 1
        elif a == "--with-config":
            with_config = True
        elif a in ("-y", "--yes"):
            skip_confirm = True
        else:
            err_console.print(f"[red]error[/red] unknown option: {a}")
            return 2
        i += 1

    if not (do_data or do_cache or do_config or do_all or plugin_name):
        err_console.print("[red]error[/red] specify what to delete "
                          "(--data/--cache/--config/--all/--plugin NAME)")
        return 2

    if plugin_name and (do_data or do_cache or do_config or do_all):
        err_console.print("[red]error[/red] --plugin cannot be combined "
                          "with --data/--cache/--config/--all")
        return 2

    data_root = paths.data_root()
    config_root = paths.config_root()

    targets = []  # list of (label, kind, path)

    if do_all:
        targets.append(("config root", "dir", config_root))
        targets.append(("data root", "dir", data_root))
    else:
        if plugin_name:
            targets.append((
                f"plugin data ({plugin_name})", "dir",
                data_root / "data" / plugin_name,
            ))
            targets.append((
                f"plugin cache ({plugin_name})", "dir",
                data_root / "cache" / plugin_name,
            ))
            if with_config:
                targets.append((
                    f"plugin config ({plugin_name})", "dir",
                    config_root / "plugins" / plugin_name,
                ))
        else:
            if do_data:
                targets.append(("plugin data", "dir", data_root / "data"))
                targets.append(("shared data", "dir", data_root / "shared"))
            if do_cache:
                targets.append(("cache", "dir", data_root / "cache"))
            if do_config:
                targets.append(("config", "dir", config_root))

    # report + confirm
    total_size = 0
    existing = []
    for label, kind, path in targets:
        if not path.exists():
            continue
        size = _dir_size(path) if kind == "dir" else (
            path.stat().st_size if path.is_file() else 0
        )
        total_size += size
        existing.append((label, kind, path, size))

    if not existing:
        console.print("nothing to delete")
        return 0

    console.print("[bold]will delete:[/bold]")
    for label, kind, path, size in existing:
        console.print(f"  {label:30} {path}")
        console.print(f"  {' ' * 30} {_fmt_size(size)}")
    console.print(f"\ntotal: {_fmt_size(total_size)}")

    if not skip_confirm:
        if not _confirm("Delete the above?"):
            console.print("aborted")
            return 0

    deleted = 0
    failed = 0
    for label, kind, path, _size in existing:
        if kind == "dir":
            existed, ok, _ = _safe_rmtree(path)
        else:
            existed, ok, _ = _rmfile(path)
        if existed and ok:
            deleted += 1
        elif existed and not ok:
            failed += 1

    console.print()
    if failed == 0:
        console.print(f"[green]done[/green] ({deleted} item(s) removed)")
    else:
        console.print(f"[yellow]done[/yellow] "
                      f"({deleted} removed, {failed} failed)")

    return 0 if failed == 0 else 1