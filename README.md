# cptools

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
cpt --help                           show help
cpt --version                        show version
```

## Builtin plugins

### link-manager

Aliases: `link`, `gen`.

Manages competitive programming problem URLs and source files.

```
cpt link parse <url>                     show info for a URL
cpt link <url>                           shortcut for: new <url>
cpt link new <url> [opts]                create a source file
cpt link list                            list saved problems
cpt link dir <url>                       show target directory
cpt link open <url|oj|--data|--config|--problem>
                                         open a directory
cpt link config [show|get|set|unset]     manage settings
cpt link template [list|add|remove|show] manage templates
```

`new` options:

- `-t, --template NAME` — template name (default: `config.default_template`)
- `-e, --ext EXT` — output extension (default: `config.default_ext`)
- `-d, --dir PATH` — override target directory
- `-n, --name NAME` — override file name (default: problem ID)

Config keys:

- `default_dir` — directory for known OJs
- `fallback_dir` — directory for unknown URLs
- `oj_dirs.<oj>` — per-OJ directory (e.g. `oj_dirs.codeforces`)
- `default_template` — default template name
- `default_ext` — default output extension (e.g. `.cpp`)

Builtin template: `cpp_default` (stored as `cpp_default.txt`).

Template placeholders use `string.Template` syntax:

- `$link`, `$id`, `$oj`, `$name`
- `$date`, `$time`, `$datetime`, `$timestamp`
- Use `${var}` when followed by letters/digits: `${id}suffix`
- Use `$$` for a literal `$`: `$$link` to `$link`

Example:

```
cpt link config set default_dir "D:/CP"
cpt link config set oj_dirs.codeforces "D:/CP/cf"
cpt link config set oj_dirs.atcoder "D:/CP/atc"
cpt link new https://codeforces.com/contest/1923/problem/A
```

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
import os
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

Drop the directory under:

- Windows: `%LOCALAPPDATA%\cptools\plugins\<name>\`
- Linux/macOS: `~/.local/share/cptools/plugins/<name>/`

Then:

```
cpt my-plugin hello
cpt mp hello
```

See `PROTOCOL.md` for the full spec.
See `cptools/builtin/link-manager/` for a complete example.

## Layout

Runtime paths (created automatically):

- Config: `%APPDATA%\cptools\plugins\<name>\` / `~/.config/cptools/plugins/<name>/`
- Data: `%LOCALAPPDATA%\cptools\data\<name>\` / `~/.local/share/cptools/data/<name>/`
- Cache: `%LOCALAPPDATA%\cptools\cache\<name>\` / `~/.cache/cptools/<name>/`

## License

MIT