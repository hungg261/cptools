# stress

Auto stress-test competitive programming solutions. Generates random inputs,
runs solution against a brute force / checker / interactor, and stops on the
first mismatch.

Aliases: none (use `cpt stress ...`).

## Requirements

- A C++ compiler in PATH (`g++` or `clang++`)
- `tkinter` for the GUI (bundled with most Python installs; on Linux may
  need `python3-tk`)
- Optional: `tkinterdnd2` for drag-and-drop (`pip install cptools[gui]`)

## Commands

```
cpt stress run <source> --gen GEN.cpp --brute B.cpp [opts]
cpt stress run <source> --gen GEN.cpp --brute B.cpp --checker C.cpp
cpt stress run <source> --gen GEN.cpp --interactor I.cpp
cpt stress gui [source]
cpt stress config [show|get|set|reset]
cpt stress install-testlib [--force]
```

## Modes

### Standard

Solution + Generator + Brute force. Compares solution output against brute
output.

```
cpt stress run sol.cpp --gen gen.cpp --brute brute.cpp
cpt stress run sol.cpp --gen gen.cpp --brute brute.cpp --match token
```

Match modes:

- `token` (default) - split by whitespace, compare token lists
- `exact` - exact string match after stripping trailing whitespace
- `whitespace` - collapse whitespace, strip each line

### Checker

Solution + Generator + Brute + Checker. Checker follows the testlib.h
convention:

```
./checker <input_file> <participant_output> <jury_output>
```

Return codes: 0 = AC, 1 = WA, 2 = Partial (treated as WA), 3 = PE (treated
as WA), anything else = RTE.

```
cpt stress run sol.cpp --gen gen.cpp --brute brute.cpp --checker checker.cpp
```

### Interactive

Solution + Generator + Interactor. Interactor and solution talk via
stdin/stdout pipes. Mediator runs both in parallel and logs every message.

Interactor convention:

```
./interactor <input_file> <output_file> <answer_file> [extra_args]
```

- `input_file` - generated input (test input for the interaction)
- `output_file` - copy of solver stdout (for debugging)
- `answer_file` - copy of interactor stdout (for debugging)

Return code: 0 = AC, 1 = WA, 2 = Partial, 3 = PE, else RTE.

```
cpt stress run sol.cpp --gen gen.cpp --interactor interactor.cpp
```

## CLI options for `run`

```
-g, --gen FILE         generator source (required)
-b, --brute FILE       brute force source (standard / checker modes)
-c, --checker FILE     checker source (implies --mode checker)
--interactor FILE      interactor source (implies --mode interactive)
-m, --mode MODE        standard | checker | interactive
-s, --seed N           starting seed
--randomize-seed       randomize seed per iteration
--gen-args ARGS        extra args passed to generator after seed
--match MODE           token | exact | whitespace
--max-fails N          stop after N fails
--no-stop-on-fail      keep going after fails
--time-limit SEC       override time limit
```

## Generator and interactor conventions

Generator:

```
./gen <test_id> <seed> [extra_args]
```

- `test_id` - 1-based iteration number
- `seed` - deterministic seed (from `--seed N` + iteration, or random)
- `extra_args` - whatever passed via `--gen-args`

Interactor:

```
./interactor <input_file> <output_file> <answer_file> [extra_args]
```

Both interactor and solution run with stdin/stdout as pipes. The mediator
forwards bytes between them and captures transcripts to files.

## Config

Global config: `%APPDATA%\cptools\plugins\stress\config.json`
(Linux/macOS: `~/.config/cptools/plugins/stress/config.json`).

```json
{
  "compiler": "g++",
  "compiler_flags": ["-O2", "-std=c++17"],
  "compile_timeout": 60,
  "time_limit": 1.0,
  "warn_factor": 1.0,
  "slow_factor": 2.0,
  "fail_factor": 3.0,
  "gen_timeout": 5.0,
  "match_mode": "token",
  "stop_on_fail": true,
  "max_fails": 50,
  "no_compile": false
}
```

Keys:

- `compiler` - compiler executable (default `g++`)
- `compiler_flags` - list of flags (default `-O2 -std=c++17`)
- `compile_timeout` - seconds (default 60)
- `time_limit` - per-run time limit in seconds (default 1.0)
- `warn_factor` - WARN threshold multiplier (default 1.0)
- `slow_factor` - SLOW threshold multiplier (default 2.0)
- `fail_factor` - TLE threshold multiplier (default 3.0)
- `gen_timeout` - generator timeout in seconds (default 5.0)
- `match_mode` - default match mode
- `stop_on_fail` - stop on first fail (default true)
- `max_fails` - max fails to collect (default 50)
- `no_compile` - skip compilation, use existing binaries (default false)

CLI:

```
cpt stress config show
cpt stress config get time_limit
cpt stress config set time_limit 2.5
cpt stress config set compiler_flags "-O2 -std=c++20"
cpt stress config reset
```

## Timing levels

Each iteration is classified by elapsed time against the time limit `TL`:

| Verdict | Condition | Behavior |
|---|---|---|
| OK | t < TL | continue |
| WARN | TL ≤ t < warn_factor × TL | continue (yellow) |
| SLOW | warn_factor × TL ≤ t < fail_factor × TL | continue (orange) |
| TLE | t ≥ fail_factor × TL | stop (red) |

Default factors give: OK < 1s, WARN 1-2s, SLOW 2-3s, TLE ≥ 3s.

The multipliers are adjustable in Settings. On slower machines, users may
want higher factors (e.g. `warn=2, slow=3, fail=5`).

## GUI

Launch with `cpt stress gui [source]`.

Features:

- Multi-mode tabs (Standard / Checker / Interactive)
- Drag-and-drop files onto path fields
- Solution switcher with recent history (File → Recent solutions)
- Custom hotkeys (File → Settings)
- Inline fail preview (Input / Expected / Got tabs)
- Add fail to runner tests (single or all)
- Download testlib.h (Tools menu)
- Skip compile option (reuse existing binaries)

Default hotkeys:

| Action | Binding |
|---|---|
| Start stress | F5 |
| Stop stress | Shift+F5 |
| Open solution | Ctrl+O |
| Settings | Ctrl+, |
| Quit | Ctrl+Q |

All bindings customizable in Settings.

### Path field menu

Each path field has a `▾` button that opens:

- Preview - jump to Preview tab with this file
- Open with - submenu of detected editors
- Reveal in folder
- Copy path
- Clear

### I/O mode

The tab "I/O" inside the GUI supports two modes for each iteration:

- **stdin/stdout** (default) - input passed via stdin pipe
- **file** - input written to a file, solution's `freopen()` reads it

Use file mode when your solution uses `freopen("problem.inp", "r", stdin)`.
Files are created in a per-solution work directory under the plugin cache,
not next to the source file.

## testlib.h

Download via:

```
cpt stress install-testlib
cpt stress install-testlib --force
```

Or from GUI: **Tools → Download testlib.h**.

Saved to `%LOCALAPPDATA%\cptools\data\stress\testlib\testlib.h`
(Linux/macOS: `~/.local/share/cptools/data/stress/testlib/testlib.h`).

Once present, the stress plugin auto-adds `-I<testlib_dir>` to compiler
flags, so any source with `#include "testlib.h"` compiles without extra
config.

Typical generator using testlib.h:

```cpp
#include "testlib.h"
using namespace std;

int main(int argc, char** argv) {
    registerGen(argc, argv, 1);
    int n = rnd.next(1, 100);
    println(n);
    for (int i = 0; i < n; ++i)
        println(rnd.next(1, 1000000000));
    return 0;
}
```

`registerGen(argc, argv, 1)` reads the seed from `argv[1]`, which the stress
plugin passes automatically.

## Fail storage

Fails are saved to:

```
%LOCALAPPDATA%\cptools\data\stress\solutions\<hash>\fails\
├── fail_001_seed12345\
│   ├── input.txt
│   ├── expected.txt
│   ├── got.txt
│   ├── stderr.txt         (if any)
│   ├── interaction_log.txt (interactive mode only)
│   └── meta.json          (index, seed, status)
├── fail_002_seed67890\
└── ...
```

`<hash>` is a SHA1 prefix of the absolute solution path. Each solution has
its own storage, so multiple solutions don't collide.

From the GUI, each fail can be:

- **Viewed** - full dialog with Input / Expected / Got side by side
- **Added to runner** - insert as a new test into the runner's test storage

"Add all to runner" inserts every fail at once. Existing tests are not
overwritten - new tests are appended.

## Compilation

Compilation happens before the loop starts. Each target (solution,
generator, brute, checker, interactor) is compiled separately.

- Compile progress is logged line by line: `compiling sol: sol.cpp`,
  `sol OK`, `compiling gen: gen.cpp`, etc.
- If any compile fails, the loop never starts. A **Compile error** dialog
  shows the full stderr.
- **Stop** during compile kills the compiler process immediately.
- **Skip compile** checkbox bypasses compilation and reuses existing
  binaries from the cache (useful when iterating on the same solution
  without changing code).

Binaries are stored in `%LOCALAPPDATA%\cptools\cache\stress\run\<stem>_<hash>\bin\`.

## Example workflow

Find a counterexample where `sol.cpp` produces wrong output:

```
# 1. Setup paths (once per solution)
cpt stress gui sol.cpp

# In GUI:
#   Generator: gen.cpp
#   Mode: Standard
#   Brute: brute.cpp
#   Match: token

# 2. Click Start. Watch log, wait for WA/TLE.

# 3. On fail, open Failures tab.
#    Select the fail, view Input / Expected / Got.

# 4. Click "Add to runner". Close stress GUI.

# 5. Debug with runner:
cpt run gui sol.cpp
# The new test appears in the test list.
```

## See also

- [runner](runner.md) - test solutions with manual input/output
- [link-manager](link-manager.md) - fetch problem links, create source files