def _branch(is_last, simple):
    if simple:
        return "`-- " if is_last else "+-- "
    return "└── " if is_last else "├── "


def _vertical(simple):
    return "|   " if simple else "│   "


def render(entries, simple=False):
    lines = []
    for path, depth, is_last, ancestor_lasts in entries:
        if depth == 0:
            lines.append(str(path))
            continue
        prefix = "".join(
            "    " if last else _vertical(simple)
            for last in ancestor_lasts
        )
        lines.append(prefix + _branch(is_last, simple) + path.name)
    return "\n".join(lines)