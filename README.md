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
cpt --help                           show help
cpt --version                        show version
```

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

Git installs require `git` in PATH. RAR archives require `rarfile` and an `unrar`
binary (`pip install cptools[rar]`).

## Builtin plugins

### link-manager

Aliases: `link`, `gen`.

Manages competitive programming problem URLs and source files.

```
cpt link <url>                           shortcut for: new <url>
cpt link parse <url>                     show info for a URL
cpt link new <url> [opts]                create a source file
cpt link list                            list saved problems
cpt link dir <url>                       show target directory
cpt link open <url|oj|--data|--config|--problem>
                                         open a directory
cpt link open-file <id> [opts]           open or delete a saved file
cpt link rm <id> [opts]                  delete file(s) and entry
cpt link undo [-y] [--keep-entry]        delete the most recently created file
cpt link editors [list|detect|known|set|unset]
                                         manage editors
cpt link oj [list|show|add|remove|test]  manage OJs (builtin + custom)
cpt link config [show|get|set|unset|reset]
                                         manage settings
cpt link template [list|add|remove|show] manage templates
```

`new` options:

```
-t, --template NAME    template name (default: config.default_template)
-e, --ext EXT          output extension (default: config.default_ext)
-d, --dir PATH         override target directory
-n, --name NAME        override file name (default: problem id)
--open [EDITOR]        open after creating (optionally pick editor)
--no-open              never prompt or open
```

`open-file` options:

```
--with EDITOR          open with a specific editor
--folder               reveal file in file manager
-D, --delete           delete file + entry instead of opening
-y, --yes              skip confirmation (with --delete)
```

`rm` options:

```
-y, --yes              skip confirmation
--keep-entry           delete file only, keep store entry
--all                  delete every file with this id
```

Config keys:

- `default_dir` — base directory for known OJs
- `fallback_dir` — directory for unknown URLs
- `oj_dirs.<oj>` — per-OJ directory override
- `default_template` — default template name
- `default_ext` — default output extension
- `default_editor` — default editor name
- `editors.<name>` — path to editor executable
- `prompt_after_new` — prompt to open after `new` (`true` / `false`)
- `auto_oj_subdir` — auto-create a subdirectory per OJ (`true` / `false`)
- `custom_ojs` — user-defined OJ regexes (managed via `cpt link oj`)

Directory resolution for a recognized OJ:

1. `oj_dirs.<oj>` if set
2. `default_dir/<oj>` if `auto_oj_subdir` is true
3. `default_dir` if `auto_oj_subdir` is false
4. plugin data dir as last resort

For an unrecognized URL:

1. `fallback_dir` if set
2. `default_dir` if set
3. plugin data dir

Templates use `string.Template` syntax:

- `$link`, `$id`, `$oj`, `$name`
- `$date`, `$time`, `$datetime`, `$timestamp`
- Use `${var}` when followed by letters/digits: `${id}suffix`
- Use `$$` for a literal `$`: `$$link` → `$link`

Builtin template: `cpp_default` (stored as `cpp_default.txt`).

Add your own:

```
cpt link template add /path/to/mytemplate.txt mytemplate
cpt link new <url> -t mytemplate -e .cpp
```

Custom OJs:

```
cpt link oj add myoj "myoj\.com/problem/(?P<pid>[A-Z0-9]+)"
cpt link oj test "https://myoj.com/problem/HELLO"
cpt link new "https://myoj.com/problem/WORLD"
```

With custom ID format:

```
cpt link oj add myoj "myoj\.com/c/(?P<cid>\d+)/p/(?P<pid>[A-Z]+)" --id-template "{cid}_{pid}"
```

Manage OJs:

```
cpt link oj list                     list all OJs
cpt link oj show <name>              show details
cpt link oj remove <name>            remove a custom OJ
cpt link oj test <url> [--oj NAME]   test parsing without saving
```

Example:

```
cpt link config set default_dir "D:/CP"
cpt link config set auto_oj_subdir true

cpt link new https://codeforces.com/contest/1923/problem/A
# -> D:/CP/codeforces/1923A.cpp

cpt link new https://atcoder.jp/contests/abc300/tasks/abc300_a
# -> D:/CP/atcoder/abc300_a.cpp
```

### tree

Shows a directory tree with include/exclude filters.

```
cpt tree [path] [opts]                show tree of path (default: .)
cpt tree --pick [opts]                pick a folder interactively
cpt tree config <subcommand>          manage settings
```

Options:

```
-s, --simple           use ASCII characters (+-- `-- |) instead of Unicode
-d, --depth N          limit recursion depth (0 = unlimited)
-e, --exclude PATTERN  exclude matching files/dirs (repeatable)
-a, --all              include hidden files (dotfiles)
--pick                 open a folder picker dialog
```

Exclude patterns use `fnmatch`:

```
-e "*.pyc"             by name
-e "temp*"             by name prefix
-e "src/temp"          by relative path
-e "*/bin"             any folder named bin
```

Config:

```
cpt tree config show
cpt tree config set max_depth 3
cpt tree config set show_hidden true
cpt tree config reset
cpt tree config exclude list
cpt tree config exclude add "*.o"
cpt tree config exclude remove "*.o"
cpt tree config exclude clear
```

Example:

```
cpt tree
cpt tree D:\Projects\CP-Judge-2 -d 3
cpt tree . -e "*.pyc" -e "__pycache__" -s
cpt tree --pick
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

Install it:

```
cpt plugin install /path/to/my-plugin
cpt my-plugin hello
cpt mp hello
```

See `PROTOCOL.md` for the full spec.
See `cptools/builtin/link-manager/` for a complete example.
Run tests with `python -m pytest` to ensure the correct interpreter.

## Layout

Runtime paths (created automatically):

- Config: `%APPDATA%\cptools\plugins\<name>\` / `~/.config/cptools/plugins/<name>/`
- Data: `%LOCALAPPDATA%\cptools\data\<name>\` / `~/.local/share/cptools/data/<name>/`
- Cache: `%LOCALAPPDATA%\cptools\cache\<name>\` / `~/.cache/cptools/<name>/`

User plugins override builtin plugins with the same name.

## License

MIT