from pathlib import Path

from cptools.manifest import Plugin
from cptools.registry import build_index


def _mk(name: str, alias: list[str] | None = None) -> Plugin:
    return Plugin(
        name=name,
        version="0.1.0",
        exec=["python", "main.py"],
        path=Path("/tmp") / name,
        alias=alias or [],
    )


def test_alias_basic():
    by_name, by_alias = build_index([_mk("demo", ["d", "dm"])])
    assert "demo" in by_name
    assert by_alias["d"].name == "demo"
    assert by_alias["dm"].name == "demo"


def test_alias_conflict_with_name():
    _, by_alias = build_index([_mk("demo", ["other"]), _mk("other")])
    assert "other" not in by_alias


def test_alias_conflict_between_plugins():
    _, by_alias = build_index([_mk("a", ["x"]), _mk("b", ["x"])])
    assert by_alias["x"].name == "a"


def test_reserved_alias_ignored():
    _, by_alias = build_index([_mk("demo", ["help", "plugin"])])
    assert "help" not in by_alias
    assert "plugin" not in by_alias