from pathlib import Path

from . import paths
from .console import err_console
from .manifest import Plugin, load

RESERVED = {"plugin", "help", "version", "--json", "--help", "-h", "-v"}
SUPPORTED_PROTOCOL = 1


def _scan(directory: Path, builtin: bool) -> list[Plugin]:
    result: list[Plugin] = []
    if not directory.is_dir():
        return result

    for child in sorted(directory.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "cptools-plugin.toml").exists():
            continue
        try:
            plugin = load(child, builtin=builtin)
        except Exception as e:
            err_console.print(f"[yellow]skip[/yellow] invalid plugin '{child.name}': {e}")
            continue
        if plugin.protocol > SUPPORTED_PROTOCOL:
            err_console.print(
                f"[yellow]skip[/yellow] '{plugin.name}' requires protocol "
                f"{plugin.protocol} > {SUPPORTED_PROTOCOL}"
            )
            continue
        result.append(plugin)

    return result


def discover() -> list[Plugin]:
    user = _scan(paths.user_plugins_dir(), builtin=False)
    builtin = _scan(paths.builtin_plugins_dir(), builtin=True)

    by_name = {p.name: p for p in user}
    for p in builtin:
        by_name.setdefault(p.name, p)
    return list(by_name.values())


def build_index(plugins: list[Plugin]) -> tuple[dict[str, Plugin], dict[str, Plugin]]:
    by_name = {p.name: p for p in plugins}
    by_alias: dict[str, Plugin] = {}

    for plugin in plugins:
        for alias in plugin.alias:
            if alias in RESERVED:
                err_console.print(
                    f"[yellow]warn[/yellow] alias '{alias}' of '{plugin.name}' is reserved"
                )
                continue
            if alias in by_name:
                err_console.print(
                    f"[yellow]warn[/yellow] alias '{alias}' of '{plugin.name}' "
                    f"collides with a plugin name"
                )
                continue
            if alias in by_alias:
                err_console.print(
                    f"[yellow]warn[/yellow] alias '{alias}' already belongs to "
                    f"'{by_alias[alias].name}', skipped for '{plugin.name}'"
                )
                continue
            by_alias[alias] = plugin

    return by_name, by_alias


def resolve(name: str) -> Plugin | None:
    plugins = discover()
    by_name, by_alias = build_index(plugins)
    return by_name.get(name) or by_alias.get(name)