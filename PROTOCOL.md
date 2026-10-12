# CPTools Protocol v1

Specification for plugin developers.

## Overview

CPTools discovers plugins and runs them as subprocesses.

The host does NOT:

- import plugin code
- parse plugin arguments
- manage plugin GUI

The host DOES:

- discover plugins from disk
- resolve names and aliases
- set environment variables
- spawn the plugin as a subprocess
- propagate the exit code

## Plugin layout

A plugin is any directory containing `cptools-plugin.toml` and an executable:

```
my-plugin/
├── cptools-plugin.toml
└── main.py
```

Any language works. `exec` in the manifest points to the entry point.

## Manifest

File: `cptools-plugin.toml`.

### Required

```toml
[plugin]
name = "my-plugin"               # unique, lowercase, no spaces
exec = ["python", "main.py"]     # argv to invoke the plugin
```

`exec` is a list of strings. Host runs it directly (no shell). Relative paths
resolve against the plugin directory.

On Windows, `.py` entry points are auto-prefixed with the current Python
interpreter. Prefer `exec = ["python", "main.py"]` over `exec = ["main.py"]`
for portability.

### Optional

```toml
[plugin]
alias = ["mp", "m"]              # alternative names
version = "0.1.0"
description = "Short description"
protocol = 1                     # protocol version, default 1

[commands]
hello = "Say hi"                 # command name -> help text
```

## Aliases

- Each alias must be unique across all loaded plugins.
- Aliases cannot be reserved names: `plugin`, `self`, `help`, `version`,
  `--json`, `--help`, `-h`, `-v`.
- If an alias collides with a plugin name, the plugin name wins.
- If two plugins declare the same alias, the first loaded wins. A warning
  is printed to stderr.

## Environment variables

The host sets these before spawning the plugin:

| Variable | Meaning |
|---|---|
| `CPTOOLS_PLUGIN_NAME` | canonical plugin name |
| `CPTOOLS_INVOKED_AS` | name or alias the user typed |
| `CPTOOLS_PLUGIN_CONFIG_DIR` | user-editable config |
| `CPTOOLS_PLUGIN_DATA_DIR` | persistent data |
| `CPTOOLS_PLUGIN_CACHE_DIR` | cache, safe to delete |
| `CPTOOLS_OUTPUT` | `human` or `json` |
| `CPTOOLS_PROTOCOL` | protocol version |
| `CPTOOLS_CWD` | directory where the user invoked `cpt` |
| `PYTHONIOENCODING` | forced to `utf-8` if not already set |

All three directories exist before the plugin runs.

Use `CPTOOLS_CWD` when relative paths (from user input) need to resolve
against the user's shell, not the plugin's own directory.

## Arguments

The host forwards remaining `argv` to the plugin unchanged. The plugin is
responsible for parsing its own arguments.

Example:

```
cpt my-plugin hello world
```

Spawns:

```
my-plugin-exec hello world
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | user error |
| 2 | usage error |
| 127 | plugin could not be run |

Other codes are plugin-defined. The host propagates the exit code unchanged.

## Output

Default (`CPTOOLS_OUTPUT=human`): free-form text. The host passes it through
unchanged.

When `CPTOOLS_OUTPUT=json`: JSON Lines recommended, one object per line:

```
{"type": "item", "id": "1923A", "url": "..."}
{"type": "message", "level": "info", "text": "saved 2 items"}
```

This is not enforced. Plain text is always accepted and shown as-is.

## Discovery

The host scans two locations in order:

1. User plugins: `<data_root>/plugins/<name>/`
2. Builtin plugins: `<package>/cptools/builtin/<name>/`

User plugins override builtin plugins with the same name.

Platform-specific paths (via `platformdirs`):

- Windows: `%LOCALAPPDATA%\cptools\plugins\`
- Linux: `~/.local/share/cptools/plugins/`
- macOS: `~/Library/Application Support/cptools/plugins/`

Run `cpt self paths` to see the exact paths on your machine.

## Protocol version

The `protocol` field in the manifest declares the protocol version.
The host supports protocol 1.

Plugins declaring `protocol > 1` are skipped with a warning on stderr.

## Guarantees

The host guarantees:

- All `CPTOOLS_*` variables are set.
- Config, data, and cache directories exist.
- The working directory is the plugin directory.
- Arguments after the plugin name are forwarded unchanged.
- Exit code is propagated unchanged.

The plugin must:

- Not require the host to parse its arguments.
- Return a meaningful exit code.
- Not assume a current working directory other than its own.