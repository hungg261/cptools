from rich.table import Table

from .. import registry
from ..console import console


def handle(args: list[str]) -> int:
    if not args or args[0] in ("-h", "--help"):
        print_help()
        return 0

    action = args[0]
    if action == "list":
        return cmd_list()
    if action == "info":
        return cmd_info(args[1:])

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


def print_help() -> None:
    console.print(
        "[bold]Usage:[/bold]\n"
        "  cpt plugin list          list all plugins\n"
        "  cpt plugin info <name>   show plugin details\n"
    )