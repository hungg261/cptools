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

Source, binary, input, and expected-output paths may be relative to the
directory where `cpt` was invoked. For example:

```
cpt run build .\solutions\aplusb.cpp
cpt run test add .\solutions\aplusb.cpp .\tests\1.in .\tests\1.out
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
- I/O mode: stdin/stdout or file (per test tab)
- File drag and drop
- Recent files menu (shared with `stress`)
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

Each test tab has an I/O panel:

- **stdin/stdout** (default) — input via stdin pipe, output from stdout
- **file** — input written to a file, solution's `freopen()` reads it

Input and output file names are per-tab. Changing the input name auto-fills
the output name (`.inp` → `.out`, `.INP` → `.OUT`, unknown ext → `.out`).
Manual edits to the output name stop the auto-fill.

Files are created in a per-test work directory under the plugin cache, not
next to the source file.

### Match mode

Controls how solution output is compared to expected output. Set per
source, applies to all tests.

| Mode | Behavior |
|---|---|
| `line` (default) | strip trailing whitespace on each line, ignore trailing blank lines |
| `token` | split on whitespace, compare token lists (ignores all formatting) |
| `exact` | strip trailing whitespace of the whole output only |

`line` covers 95% of problems: `cout << a[i][j] << " "` works without
needing to suppress the last trailing space.

`token` is useful when the output format is not part of the problem
(interactive-style or when any valid permutation is accepted).

`exact` is for cases where line/column formatting matters.

## Test storage

Test cases are stored per source under `<data_root>/data/runner/tests/<hash>.json`.

Each entry contains `source`, `tests`, and `io`.

## Requirements

- Python 3.11+
- A C++ compiler in PATH (`g++` or `clang++`)
- `tkinter` (bundled with most Python installs; on Linux may need `python3-tk`)
- Optional: `tkinterdnd2` for drag-and-drop (`pip install cptools[gui]`)

## Example

```
cpt run build .\aplusb.cpp
cpt run run   .\aplusb.cpp --raw "2 3"
cpt run test add .\aplusb.cpp .\t1.in .\t1.out
cpt run test .\aplusb.cpp
cpt run gui   .\aplusb.cpp
```

## Integration

Fail cases from the `stress` plugin can be added to runner tests via the
stress GUI (Failures tab → "Add to runner" / "Add all to runner").