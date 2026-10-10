import textwrap
from pathlib import Path

from cptools.manifest import load


def test_load_basic(tmp_path: Path):
    (tmp_path / "cptools-plugin.toml").write_text(
        textwrap.dedent("""
            [plugin]
            name = "demo"
            version = "0.1.0"
            exec = ["python", "main.py"]
            protocol = 1
            alias = ["d"]

            [commands]
            hello = "Say hi"
        """),
        encoding="utf-8",
    )

    p = load(tmp_path)
    assert p.name == "demo"
    assert p.alias == ["d"]
    assert p.exec == ["python", "main.py"]
    assert p.commands == {"hello": "Say hi"}
    assert p.protocol == 1
    assert p.builtin is False