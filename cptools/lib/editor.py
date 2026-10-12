"""Backward-compat shim. Prefer cptools.lib.editor_registry for new code."""

from dataclasses import dataclass

from .editor_registry import (  # noqa: F401
    KNOWN,
    detect_editors,
    get_default,
    label_for,
    launch,
    known_editors,
    list_editors,
    ordered_keys,
    remove_editor,
    set_default,
    set_editor,
)


@dataclass
class Editor:
    key: str
    label: str
    exe: str


def get_editors() -> dict[str, Editor]:
    raw = list_editors()
    return {
        key: Editor(key=key, label=label_for(key), exe=exe)
        for key, exe in raw.items()
    }