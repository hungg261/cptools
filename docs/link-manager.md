# link-manager

Manages competitive programming problem URLs and source files.

Aliases: `link`, `gen`.

## Commands

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
cpt link editors [list|detect|known|set|unset|default]
                                         manage editors
cpt link oj [list|show|add|remove|test]  manage OJs (builtin + custom)
cpt link config [show|get|set|unset|reset]
                                         manage settings
cpt link template [list|add|remove|show] manage templates
```

## Options

### `new`

```
-t, --template NAME    template name (default: config.default_template)
-e, --ext EXT          output extension (default: config.default_ext)
-d, --dir PATH         override target directory
-n, --name NAME        override file name (default: problem id)
--open [EDITOR]        open after creating (optionally pick editor)
--no-open              never prompt or open
```

### `open-file`

```
--with EDITOR          open with a specific editor
--folder               reveal file in file manager
-D, --delete           delete file + entry instead of opening
-y, --yes              skip confirmation (with --delete)
```

### `rm`

```
-y, --yes              skip confirmation
--keep-entry           delete file only, keep store entry
--all                  delete every file with this id
```

## Supported OJs

Builtin: codeforces, atcoder, codechef, cses, kattis, leetcode, lqdoj,
marisaoj, nloj, ojuz, spoj, vnoj, yosupo, baekjoon, dmoj, hackerrank,
hackerearth, uva, timus, aizu, poj, eolymp, lightoj, toph.

Run `cpt link oj list` to see all.

## Config keys

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

## Directory resolution

For a recognized OJ:

1. `oj_dirs.<oj>` if set
2. `default_dir/<oj>` if `auto_oj_subdir` is true
3. `default_dir` if `auto_oj_subdir` is false
4. plugin data dir as last resort

For an unrecognized URL:

1. `fallback_dir` if set
2. `default_dir` if set
3. plugin data dir

## Templates

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

## Custom OJs

Define your own OJ with a regex:

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

## Editors

Editor registry is shared with other plugins. Config lives in the host
config file (`cpt self paths` shows where).

```
cpt link editors list                list detected + configured editors
cpt link editors detect              show what was found on this system
cpt link editors known               list known editor names
cpt link editors set myedit /path    add or override an editor
cpt link editors unset myedit        remove
cpt link editors default vscode      set default editor
```

## Example

```
cpt link config set default_dir "D:/CP"
cpt link config set auto_oj_subdir true

cpt link new https://codeforces.com/contest/1923/problem/A
# -> D:/CP/codeforces/1923A.cpp

cpt link new https://atcoder.jp/contests/abc300/tasks/abc300_a
# -> D:/CP/atcoder/abc300_a.cpp
```