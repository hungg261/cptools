import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

import questionary
from rich.table import Table

from .. import paths, registry
from ..console import console, err_console
from ..manifest import load as load_manifest


def handle(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print_help()
        return 0

    action = args[0]
    if action == "list":
        return cmd_list()
    if action == "info":
        return cmd_info(args[1:])
    if action == "install":
        return cmd_install(args[1:])
    if action == "uninstall":
        return cmd_uninstall(args[1:])

    console.print(f"[red]error[/red] unknown subcommand: plugin {action}")
    return 2


def cmd_list() -> int:
    plugins = sorted(registry.discover(), key=lambda p: p.name)
    if not plugins:
        console.print("No plugins installed.")
        return 0

    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("name")
    table.add_column("version")
    table.add_column("aliases")
    table.add_column("type")
    table.add_column("commands")

    for p in plugins:
        table.add_row(
            p.name,
            p.version,
            ", ".join(p.alias) if p.alias else "-",
            "builtin" if p.builtin else "user",
            ", ".join(p.commands) if p.commands else "-",
        )

    console.print(table)
    return 0


def cmd_info(args: list[str]) -> int:
    if not args:
        console.print("[red]error[/red] usage: cpt plugin info <name>")
        return 2

    name = args[0]
    plugin = registry.resolve(name)
    if plugin is None:
        console.print(f"[red]error[/red] plugin '{name}' not found")
        return 1

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("name", plugin.name)
    if plugin.alias:
        table.add_row("aliases", ", ".join(plugin.alias))
    table.add_row("version", plugin.version)
    if plugin.description:
        table.add_row("description", plugin.description)
    table.add_row("path", str(plugin.path))
    table.add_row("exec", " ".join(plugin.exec))
    table.add_row("protocol", str(plugin.protocol))
    table.add_row("builtin", str(plugin.builtin).lower())
    if plugin.commands:
        table.add_row("commands", "")
        for cmd, desc in plugin.commands.items():
            table.add_row(f"  {cmd}", desc)

    console.print(table)
    return 0


def cmd_install(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print_install_help()
        return 0 if args else 2

    force = False
    src_arg = None
    for a in args:
        if a in ("-f", "--force"):
            force = True
        elif src_arg is None:
            src_arg = a
        else:
            err_console.print(f"[red]error[/red] unexpected argument: {a}")
            return 2

    if src_arg is None:
        err_console.print("[red]error[/red] missing path")
        return 2

    if src_arg.startswith("git+"):
        return _install_from_git(src_arg, force)

    src = Path(src_arg).expanduser()
    if not src.exists():
        err_console.print(f"[red]error[/red] not found: {src}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        if src.is_dir():
            src_dir = src
        else:
            tmpdir = Path(tmp) / "extract"
            tmpdir.mkdir()
            try:
                _extract(src, tmpdir)
            except ValueError as e:
                err_console.print(f"[red]error[/red] {e}")
                return 1
            src_dir = tmpdir

        plugin_dir = _find_plugin_dir(src_dir)
        if plugin_dir is None:
            err_console.print(
                "[red]error[/red] cptools-plugin.toml not found in source"
            )
            return 1

        return _install_plugin(plugin_dir, force)


def _install_from_git(url: str, force: bool) -> int:
    git = shutil.which("git")
    if not git:
        err_console.print(
            "[red]error[/red] git not found in PATH. "
            "Install from https://git-scm.com/"
        )
        return 1

    base, ref = _parse_git_url(url)

    with tempfile.TemporaryDirectory() as tmp:
        repo_dir = Path(tmp) / "repo"
        if not _git_clone(git, base, ref, repo_dir):
            return 1

        plugin_dir = _find_plugin_dir(repo_dir)
        if plugin_dir is None:
            err_console.print(
                "[red]error[/red] cptools-plugin.toml not found in repo"
            )
            return 1

        return _install_plugin(plugin_dir, force)


def _parse_git_url(s: str) -> tuple[str, str | None]:
    s = s[4:]
    if "#" in s:
        base, ref = s.rsplit("#", 1)
        return base, ref or None
    if "@" in s:
        before, after = s.rsplit("@", 1)
        if "/" not in after and ":" not in after:
            return before, after
    return s, None


def _git_clone(git: str, base: str, ref: str | None, dest: Path) -> bool:
    cmd = [git, "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [base, str(dest)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        err_console.print("[red]error[/red] git clone timed out")
        return False
    except OSError as e:
        err_console.print(f"[red]error[/red] failed to run git: {e}")
        return False

    if result.returncode == 0:
        return True

    if not ref:
        err_console.print(f"[red]error[/red] git clone failed: {result.stderr.strip()}")
        return False

    shutil.rmtree(dest, ignore_errors=True)

    try:
        result = subprocess.run(
            [git, "clone", base, str(dest)],
            capture_output=True, text=True, timeout=300,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        err_console.print(f"[red]error[/red] git clone failed: {e}")
        return False

    if result.returncode != 0:
        err_console.print(f"[red]error[/red] git clone failed: {result.stderr.strip()}")
        return False

    try:
        co = subprocess.run(
            [git, "-C", str(dest), "checkout", ref],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        err_console.print(f"[red]error[/red] git checkout failed: {e}")
        return False

    if co.returncode != 0:
        err_console.print(f"[red]error[/red] git checkout '{ref}' failed: {co.stderr.strip()}")
        return False

    return True


def _install_plugin(plugin_dir: Path, force: bool) -> int:
    try:
        plugin = load_manifest(plugin_dir)
    except Exception as e:
        err_console.print(f"[red]error[/red] invalid manifest: {e}")
        return 1

    target = paths.user_plugins_dir() / plugin.name
    builtin_path = paths.builtin_plugins_dir() / plugin.name

    if builtin_path.is_dir():
        console.print(
            f"[yellow]note[/yellow] '{plugin.name}' exists as builtin; "
            "user version will take priority"
        )

    if target.exists():
        if not force:
            answer = questionary.confirm(
                f"'{plugin.name}' already installed at {target}. Overwrite?"
            ).ask()
            if answer is None:
                return 1
            if not answer:
                console.print("aborted")
                return 0
        shutil.rmtree(target)

    shutil.copytree(plugin_dir, target)

    console.print(f"[green]installed[/green] {plugin.name} v{plugin.version}")
    console.print(f"  path: {target}")
    return 0


def print_install_help() -> None:
    console.print(
        "[bold]Usage:[/bold]\n"
        "  cpt plugin install <path>          install from dir or archive\n"
        "  cpt plugin install <git-url>       install from git repo\n"
        "  cpt plugin install <path> -f       overwrite without asking\n"
        "\n"
        "[bold]Archives:[/bold]\n"
        "  .zip .tar .tar.gz .tgz .tar.bz2 .tar.xz .rar\n"
        "\n"
        "[bold]Git URLs:[/bold]\n"
        "  git+https://github.com/user/plugin\n"
        "  git+https://github.com/user/plugin@v1.2.0\n"
        "  git+https://github.com/user/plugin#main\n"
        "  git+ssh://git@github.com/user/plugin\n"
        "  git+file:///path/to/repo\n"
    )


def cmd_uninstall(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        console.print(
            "[bold]Usage:[/bold]\n"
            "  cpt plugin uninstall <name>            remove plugin code\n"
            "  cpt plugin uninstall <name> -y         skip confirmation\n"
            "  cpt plugin uninstall <name> --purge    also remove config/data/cache"
        )
        return 0 if args else 2

    name = None
    yes = False
    purge = False
    for a in args:
        if a in ("-y", "--yes"):
            yes = True
        elif a == "--purge":
            purge = True
        elif name is None:
            name = a
        else:
            err_console.print(f"[red]error[/red] unexpected argument: {a}")
            return 2

    if name is None:
        err_console.print("[red]error[/red] missing plugin name")
        return 2

    target = paths.user_plugins_dir() / name
    builtin_path = paths.builtin_plugins_dir() / name

    if not target.exists():
        if builtin_path.is_dir():
            err_console.print(
                f"[red]error[/red] '{name}' is a builtin plugin, cannot uninstall"
            )
            return 1
        err_console.print(f"[red]error[/red] plugin '{name}' not installed")
        return 1

    if not yes:
        msg = f"Uninstall '{name}'?"
        if not purge:
            msg += " (config/data kept)"
        answer = questionary.confirm(msg).ask()
        if answer is None:
            return 1
        if not answer:
            console.print("aborted")
            return 0

    shutil.rmtree(target)
    console.print(f"[green]uninstalled[/green] {name}")

    cfg_dir = paths.plugin_config_dir(name)
    data_dir = paths.plugin_data_dir(name)
    cache_dir = paths.plugin_cache_dir(name)

    if purge:
        for d in (cfg_dir, data_dir, cache_dir):
            if d.exists():
                shutil.rmtree(d)
        console.print("  purged config, data, and cache")
    else:
        kept = [
            d for d in (cfg_dir, data_dir, cache_dir)
            if d.exists() and any(d.iterdir())
        ]
        if kept:
            console.print("  kept:")
            for d in kept:
                console.print(f"    {d}")
            console.print("  use --purge to remove them")

    return 0


def print_help() -> None:
    console.print(
        "[bold]Usage:[/bold]\n"
        "  cpt plugin list                    list all plugins\n"
        "  cpt plugin info <name>             show plugin details\n"
        "  cpt plugin install <path> [-f]     install from dir or archive\n"
        "  cpt plugin uninstall <name> [-y] [--purge]\n"
    )


def _extract(src: Path, dest: Path) -> None:
    name = src.name.lower()

    if name.endswith(".zip"):
        _safe_extract_zip(src, dest)
        return

    tar_exts = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
    if name.endswith(tar_exts):
        _safe_extract_tar(src, dest)
        return

    if name.endswith(".rar"):
        try:
            import rarfile
        except ImportError:
            raise ValueError(
                "rar support requires 'rarfile' (pip install cptools[rar]) "
                "and an unrar binary in PATH"
            )
        with rarfile.RarFile(src) as rf:
            dest = dest.resolve()
            for info in rf.infolist():
                _safe_join(dest, info.filename)
            rf.extractall(dest)
        return

    raise ValueError(f"unsupported archive format: {src.name}")


def _safe_join(base: Path, name: str) -> Path:
    p = (base / name).resolve()
    try:
        p.relative_to(base.resolve())
    except ValueError:
        raise ValueError(f"unsafe path in archive: {name}")
    return p


def _safe_extract_zip(src: Path, dest: Path) -> None:
    dest = dest.resolve()
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            _safe_join(dest, info.filename)
        z.extractall(dest)


def _safe_extract_tar(src: Path, dest: Path) -> None:
    dest = dest.resolve()
    with tarfile.open(src) as t:
        members = t.getmembers()
        for member in members:
            _safe_join(dest, member.name)
            if member.issym() or member.islnk():
                raise ValueError(
                    f"archive contains link: {member.name}"
                )
            if member.isdev():
                raise ValueError(
                    f"archive contains device file: {member.name}"
                )
        if sys.version_info >= (3, 12):
            t.extractall(dest, filter="data")
        else:
            t.extractall(dest)


def _find_plugin_dir(root: Path) -> Path | None:
    root = root.resolve()
    candidates = [m.parent for m in root.rglob("cptools-plugin.toml")]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (len(p.relative_to(root).parts), str(p)))
    return candidates[0]