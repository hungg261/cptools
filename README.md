# cptools

[![test](https://github.com/hungg261/cptools/actions/workflows/test.yml/badge.svg)](https://github.com/hungg261/cptools/actions/workflows/test.yml)

CLI manager for competitive programming tools. Discovers and runs plugins
as subcommands.

## Install

```
pip install -e .
```

## Quick start

```
cpt plugin list
cpt link parse https://codeforces.com/contest/1923/problem/A
cpt link new   https://codeforces.com/contest/1923/problem/A
cpt link list
```

`cpt` and `cptools` are the same program.

## Commands

```
cpt <plugin> <command> [args...]     run a plugin
cpt --json <plugin> <command>        JSON output
cpt plugin list                      list plugins
cpt plugin info <name>               plugin details
cpt plugin install <path|archive|git-url>
cpt plugin uninstall <name>
cpt --help                           show help
cpt --version                        show version
```

## Builtin plugins

| Plugin | Aliases | Purpose |
|---|---|---|
| [link-manager](docs/link-manager.md) | `link`, `gen` | Manage problem URLs and source files |
| [tree](docs/tree.md) | | Show directory tree with filters |
| [runner](docs/runner.md) | `run` | Compile and test solutions with a GUI |

## Installing plugins

```
cpt plugin install <path>                    install from directory
cpt plugin install <file.zip>                install from archive
cpt plugin install git+<url>                 install from git
cpt plugin install git+<url>@v1.0.0          specific tag or branch
cpt plugin install <src> -f                  overwrite without asking

cpt plugin uninstall <name>                  remove plugin code
cpt plugin uninstall <name> -y               skip confirmation
cpt plugin uninstall <name> --purge          also remove config, data, cache
```

Supported archives: `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, `.rar`.

Git URL formats:

```
git+https://github.com/user/plugin
git+https://github.com/user/plugin@v1.2.0
git+https://github.com/user/plugin#dev
git+ssh://git@github.com/user/plugin
git+file:///path/to/local/repo
```

Git installs require `git` in PATH. RAR archives require `rarfile` and an
`unrar` binary (`pip install cptools[rar]`).

## Writing a plugin

A plugin is a directory with a manifest and an executable.

```
my-plugin/
├── cptools-plugin.toml
└── main.py
```

Manifest:

```toml
[plugin]
name = "my-plugin"
alias = ["mp"]
version = "0.1.0"
description = "My plugin"
exec = ["python", "main.py"]
protocol = 1

[commands]
hello = "Say hi"
```

Entry point:

```python
import sys

def cmd_hello(args):
    name = args[0] if args else "world"
    print(f"Hello, {name}!")
    return 0

COMMANDS = {"hello": cmd_hello}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))
```

Install and run:

```
cpt plugin install /path/to/my-plugin
cpt my-plugin hello
cpt mp hello
```

See [PROTOCOL.md](PROTOCOL.md) for the full spec.
See `cptools/builtin/link-manager/` for a complete example.

## Layout

Runtime paths (created automatically):

- Config: `%APPDATA%\cptools\plugins\<name>\` / `~/.config/cptools/plugins/<name>/`
- Data: `%LOCALAPPDATA%\cptools\data\<name>\` / `~/.local/share/cptools/data/<name>/`
- Cache: `%LOCALAPPDATA%\cptools\cache\<name>\` / `~/.cache/cptools/<name>/`

User plugins override builtin plugins with the same name.

## Development

```
pip install -e ".[gui,dev]"
python -m pytest
```

Run GUI tests on Linux require `xvfb`:

```
xvfb-run -a python -m pytest
```

## License

MIT