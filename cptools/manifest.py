import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Plugin:
    name: str
    version: str
    exec: list[str]
    path: Path
    protocol: int = 1
    alias: list[str] = field(default_factory=list)
    commands: dict[str, str] = field(default_factory=dict)
    description: str = ""
    builtin: bool = False


def load(path: Path, builtin: bool = False) -> Plugin:
    manifest_file = path / "cptools-plugin.toml"
    with manifest_file.open("rb") as f:
        data = tomllib.load(f)
    p = data["plugin"]
    return Plugin(
        name=p["name"],
        version=p.get("version", "0.0.0"),
        exec=list(p["exec"]),
        path=path,
        protocol=int(p.get("protocol", 1)),
        alias=list(p.get("alias", [])),
        commands=dict(data.get("commands", {})),
        description=p.get("description", ""),
        builtin=builtin,
    )