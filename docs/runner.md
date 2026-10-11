# runner

Compile and test competitive programming solutions, with a Tkinter GUI.

Aliases: `run`.

## Commands

```
cpt run build <source> [-o BIN]              compile only
cpt run run <source> [-i FILE] [--raw TEXT]  compile if needed + run
cpt run test <source> [-i ID] [--rebuild]    run stored tests
cpt run test add <source> <in_file> <exp_file>
cpt run test list <source>
cpt run test rm <source> <id>
cpt run gui [source]                         open GUI
cpt run config [show|get|set|reset]
```

## Config keys

- `compiler` — compiler executable (default: `g++`)
- `compiler_flags` — list of flags (default: `-O2 -std=c++17`)
- `timeout` — run timeout in seconds (default: `5`)
- `compile_timeout` — compile timeout in seconds (default: `60`)
- `bin_dir` — output dir for binaries (default: plugin cache)
- `rebuild` — `auto` | `always` | `never` (default: `auto`)

Set values:

```
cpt run config set compiler "clang++"
cpt run config set compiler_flags "-O2 -std=c++20"
cpt run config set timeout 10
```

## GUI

Launch with `cpt run gui [source]`. Features:

- Multiple tabs (one per source file)
- Test cases stored per source
- Auto-save edits (400 ms debounce)
- File-based I/O mode (for solutions that use `freopen`)
- File drag and drop
- Recent files menu
- Customizable hotkeys (File → Settings)

### Default hotkeys

| Action | Binding |
|---|---|
| New tab | Ctrl+T |
| Open file | Ctrl+O |
| Close tab | Ctrl+W |
| Next / previous tab | Ctrl+Tab / Ctrl+Shift+Tab |
| Build | Ctrl+B |
| Run all | F5 |
| Add test | Ctrl+N |
| Delete test | Delete |
| Focus next field | Ctrl+Enter |
| Settings | Ctrl+, |
| Quit | Ctrl+Q |

Change hotkeys in Settings dialog. Bindings are saved in the plugin config.

### I/O mode

By default, the solution reads from stdin and writes to stdout. If your
solution uses `freopen("problem.inp", ...)`, switch to file mode in the
I/O panel and set the input/output file names.

Files are created in a per-source work directory under the plugin cache,
not next to the source file.

## Tests storage

Test cases are stored per source under:

- Windows: `%LOCALAPPDATA%\cptools\data\runner\tests\<hash>.json`
- Linux/macOS: `~/.local/share/cptools/data/runner/tests/<hash>.json`

Each entry contains `source`, `tests`, and `io` (mode + file names).

## Requirements

- Python 3.11+
- A C++ compiler in PATH (`g++` or `clang++`)
- `tkinter` (bundled with most Python installs; on Linux may need `python3-tk`)
- Optional: `tkinterdnd2` for drag-and-drop (`pip install cptools[gui]`)

## Example

```
cpt run build D:\CP\aplusb.cpp
cpt run run   D:\CP\aplusb.cpp --raw "2 3"
cpt run test add D:\CP\aplusb.cpp t1.in t1.out
cpt run test D:\CP\aplusb.cpp
cpt run gui   D:\CP\aplusb.cpp
```