import argparse
import sys

from . import __version__, registry, runner
from .console import console


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cpt",
        description="Competitive programming tools manager",
        add_help=False,
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("-h", "--help", action="store_true", help="Show help")
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _build_parser().parse_args(argv)

    if args.version:
        console.print(f"cptools {__version__}")
        return 0

    if args.help or not args.rest:
        print_help()
        return 0

    if args.rest[0] == "plugin":
        from .commands.plugin import handle
        return handle(args.rest[1:])

    name = args.rest[0]
    plugin_args = args.rest[1:]

    plugin = registry.resolve(name)
    if plugin is None:
        console.print(
            f"[red]error[/red] plugin '{name}' not found. Run [bold]cpt plugin list[/bold]."
        )
        return 1

    return runner.run(plugin, plugin_args, invoked_as=name, as_json=args.json)


def print_help() -> None:
    console.print(
        "[bold]Usage:[/bold]\n"
        "  cpt <plugin> <command> [args...]     run a plugin\n"
        "  cpt --json <plugin> <command>        JSON output\n"
        "  cpt plugin list                      list plugins\n"
        "  cpt plugin info <name>               plugin details\n"
        "  cpt --help                           show help\n"
        "  cpt --version                        show version\n"
    )


if __name__ == "__main__":
    sys.exit(main())