import fnmatch
from pathlib import Path


def _match_any(path, root, patterns):
    name = path.name
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = name
    for pat in patterns:
        if not pat:
            continue
        if fnmatch.fnmatch(name, pat):
            return True
        if "/" in pat or "\\" in pat:
            if fnmatch.fnmatch(rel, pat):
                return True
    return False


def _sort_key(path):
    try:
        is_dir = path.is_dir()
    except OSError:
        is_dir = False
    return (not is_dir, path.name.lower())


def _visible(path, root, excludes, show_hidden):
    if not show_hidden and path.name.startswith("."):
        return False
    if _match_any(path, root, excludes):
        return False
    return True


def walk(root, excludes=None, max_depth=0, show_hidden=False):
    """Yield (path, depth, is_last, ancestor_lasts) tuples in pre-order."""
    root = Path(root).resolve()
    excludes = [p for p in (excludes or []) if p]
    yield (root, 0, True, [])
    if not root.is_dir():
        return
    yield from _recurse(root, root, 1, [], excludes, max_depth, show_hidden)


def _recurse(path, root, depth, ancestor_lasts, excludes, max_depth, show_hidden):
    if max_depth and depth > max_depth:
        return
    try:
        children = sorted(path.iterdir(), key=_sort_key)
    except OSError:
        return
    children = [c for c in children if _visible(c, root, excludes, show_hidden)]
    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        yield (child, depth, is_last, list(ancestor_lasts))
        try:
            is_dir = child.is_dir() and not child.is_symlink()
        except OSError:
            is_dir = False
        if is_dir:
            yield from _recurse(
                child, root, depth + 1, ancestor_lasts + [is_last],
                excludes, max_depth, show_hidden,
            )