# snippet

Manage code snippets and copy them to the clipboard.

Aliases: `snip`.

## Commands

```
cpt snip list                       list all snippets
cpt snip show <name>                print a snippet to stdout
cpt snip copy <name>                copy a snippet to clipboard
cpt snip add <file> [--name N]      add a file to the snippets root
cpt snip remove <name>              delete a snippet
cpt snip rename <old> <new>         rename a snippet
cpt snip edit <name>                open a snippet in the editor
cpt snip folder                     open the snippets root in file manager
cpt snip root [show|set|reset]      manage root directory
cpt snip gui                        open the GUI browser
cpt snip config [show|get|set|reset]
```

## Storage

A snippet is just a file. Any extension, any content. The plugin reads
whatever is in the root folder; no database, no metadata.

Default root:

- Windows: `%APPDATA%\cptools\plugins\snippet\snippets\`
- Linux: `~/.config/cptools/plugins/snippet/snippets/`
- macOS: `~/Library/Application Support/cptools/plugins/snippet/snippets/`

The root is fully configurable. Point it at a git repo or a Dropbox folder
to keep snippets in sync across machines.

Subdirectories are supported and become part of the name:

```
D:\CP\snippets\
├── ds\
│   ├── segtree.cpp
│   └── dsu.cpp
├── misc\
│   └── io\
│       └── fastio.cpp
└── debug.h
```

Names:

```
ds/segtree.cpp
ds/segtree
segtree               (only if unique)
```

Resolution order: exact path, then without extension, then unique stem.

Files and folders starting with `.` (`.git`, `.vscode`, etc.) are ignored
automatically. Additional folder names can be ignored via config:

```
cpt snip config set ignore "private test-fixtures"
```

## Config keys

- `root_dir` — snippets root folder (empty = default)
- `ignore` — extra folder names to skip

Manage root:

```
cpt snip root show
cpt snip root set "D:/CP/snippets"
cpt snip root reset
```

## GUI

Launch with `cpt snip gui`.

Features:

- Search box filters by name
- Live preview with horizontal + vertical scroll
- Copy / Edit / Rename / Delete / Reveal buttons
- Ctrl+C copies the selected snippet when focus is on the list
- When focus is on the preview, Ctrl+C copies the text selection
- File → Change root folder

Default hotkeys:

| Action | Binding |
|---|---|
| Copy snippet | Ctrl+C |
| Edit snippet | Ctrl+E |
| Rename | F2 |
| Delete | Delete |
| Add file | Ctrl+N |
| Focus search | Ctrl+F |
| Refresh | F5 |
| Settings | Ctrl+, |
| Quit | Ctrl+Q |

Change hotkeys in Settings dialog.

## Editing

The Edit action opens the file in the editor configured in the shared
editor registry (see `link-manager` docs, section "Editors"). If no editor
is configured, the system default is used.

Changes made in the editor are saved directly to disk — there is no
separate buffer.

## Example

```
cpt snip add D:\segtree.cpp --name ds/segtree.cpp
cpt snip list
cpt snip copy ds/segtree
cpt snip show ds/segtree | clip
cpt snip rename ds/segtree ds/segtree_lazy.cpp
cpt snip remove ds/dsu
```