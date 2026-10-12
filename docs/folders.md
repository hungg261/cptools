# folders

Manage named folders for quick access.

Aliases: `dir`.

## Commands

```
cpt folders list                          list all folders
cpt folders add <name> <path>             register a folder
cpt folders add <name> --pick             pick path via dialog
cpt folders pick                          dialog + name prompt
cpt folders remove <name>                 unregister (files are not touched)
cpt folders rename <old> <new>            rename
cpt folders show <name>                   print path
cpt folders open [<name> ...]             open one or more
cpt folders open-all                      open all at once
cpt folders default [<name>]              get or set default
cpt folders resolve <@name>[/sub]         resolve a reference
cpt folders config [show|reset]
```

## Fuzzy names

Every command that takes a folder name accepts fuzzy input:

- Exact match wins first.
- Then prefix match (`cod` → `codeforces`).
- Then substring match (`forces` → `codeforces`).
- Finally fuzzy match (`codeforcse` → `codeforces`).

If multiple names match, the command prints candidates and exits with an
error. Type more characters to disambiguate.

Example:

```
$ cpt folders list
* codeforces  D:/CP/cf
  codechef    D:/CP/cc
  vnoi        D:/CP/vnoi

$ cpt folders show cod
not found: cod
  ambiguous. candidates:
    codeforces
    codechef

$ cpt folders show codef
D:/CP/cf
```

## Interactive picker

`cpt folders open` with no arguments shows a checkbox menu. Select one or
more folders, press Enter, they all open.

Requires `questionary` (already a cptools dependency).

## Folder dialog

Two commands open the native folder picker:

- `cpt folders add <name> --pick` — name first, then pick path.
- `cpt folders pick` — pick path first, then prompt name.

Uses `tkinter.filedialog.askdirectory`. Requires `tkinter` and an
interactive terminal (won't run inside a script).

## Reference syntax

`@name` refers to a registered folder. It works in:

- `cpt folders resolve @name`
- `cpt folders resolve @name/sub`
- Any plugin that calls `cptools.lib.folders.resolve_ref()`.

`@name` is expanded at runtime. `@name/sub` is joined with `/` (or `\`).

Example: `@cp/cf` where `cp = D:/CP` resolves to `D:/CP/cf`.

## Config keys

- `folders` — mapping of name → raw path
- `default` — default folder name (used by some integrations)

Storage: `<config_root>/plugins/folders/folders.json`.

Manage via CLI:

```
cpt folders config show
cpt folders config reset
```

Or edit the JSON file directly. Paths may contain `~` and environment
variables (`$VAR` / `%VAR%`), expanded when resolved.

## Integration with link-manager

Link-manager accepts `@name` anywhere a directory is expected:

```
cpt link new <url> -d @cp/cf        # explicit target
cpt link config set default_dir "@cp"
cpt link config set oj_dirs.codeforces "@cf"
cpt link config set fallback_dir "@scratch"
```

Also for `parse`:

```
cpt link parse <url> -d @cp
```

The reference is resolved via `cptools.lib.folders.resolve_ref`. If the
name is not registered, the command fails with a clear error.

## Example

```
# register some folders
cpt folders add cp         "D:/CP"
cpt folders add cf         "D:/CP/cf"
cpt folders add atc        "D:/CP/atc"
cpt folders add scratch    "D:/tmp/cp"

# make one the default
cpt folders default cp

# open one or many
cpt folders open cf
cpt folders open cf atc
cpt folders open-all

# use @name in link-manager
cpt link new https://codeforces.com/contest/1923/problem/A -d @cf
# -> D:/CP/cf/1923A.cpp

# fuzzy
cpt folders show c          # ambiguous if both cp and cf exist
cpt folders show cod        # matches codeforces if that exists

# dialog
cpt folders pick
```

## See also

- [link-manager](link-manager.md) — uses `@name` for target directories