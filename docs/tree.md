# tree

Shows a directory tree with include/exclude filters.

## Commands

```
cpt tree [path] [opts]                show tree of path (default: .)
cpt tree --pick [opts]                pick a folder interactively
cpt tree config <subcommand>          manage settings
```

## Options

```
-s, --simple           use ASCII characters (+-- `-- |) instead of Unicode
-d, --depth N          limit recursion depth (0 = unlimited)
-e, --exclude PATTERN  exclude matching files/dirs (repeatable)
-a, --all              include hidden files (dotfiles)
--pick                 open a folder picker dialog
```

## Exclude patterns

Exclude patterns use `fnmatch`:

```
-e "*.pyc"             by name
-e "temp*"             by name prefix
-e "src/temp"          by relative path
-e "*/bin"             any folder named bin
```

## Config

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

Default excludes: `__pycache__`, `node_modules`, `.venv`, `venv`, `*.pyc`.

## Example

```
cpt tree
cpt tree D:\Projects\CP-Judge-2 -d 3
cpt tree . -e "*.pyc" -e "__pycache__" -s
cpt tree --pick
```