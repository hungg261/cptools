import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "snippet"


@pytest.fixture
def env(tmp_path):
    cfg = tmp_path / "cfg"
    data = tmp_path / "data"
    for d in (cfg, data):
        d.mkdir()
    e = os.environ.copy()
    e["CPTOOLS_CONFIG_ROOT"] = str(cfg)
    e["CPTOOLS_DATA_ROOT"] = str(data)
    e["CPTOOLS_PLUGIN_NAME"] = "snippet"
    e["CPTOOLS_INVOKED_AS"] = "snip"
    e["CPTOOLS_PROTOCOL"] = "1"
    e["CPTOOLS_OUTPUT"] = "human"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def run_snip(env, *args, timeout=15, input=None):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=PLUGIN_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        input=input,
    )


class TestConfig:
    def test_show(self, env):
        r = run_snip(env, "config", "show")
        assert r.returncode == 0
        cfg = json.loads(r.stdout)
        assert cfg["root_dir"] == ""
        assert cfg["ignore"] == []

    def test_set_ignore(self, env):
        r = run_snip(env, "config", "set", "ignore", "private test")
        assert r.returncode == 0
        r = run_snip(env, "config", "show")
        cfg = json.loads(r.stdout)
        assert cfg["ignore"] == ["private", "test"]


class TestRoot:
    def test_show_default(self, env):
        r = run_snip(env, "root")
        assert r.returncode == 0
        assert r.stdout.strip().endswith("snippets")

    def test_set(self, env, tmp_path):
        target = tmp_path / "my-snips"
        target.mkdir()
        r = run_snip(env, "root", "set", str(target))
        assert r.returncode == 0
        r = run_snip(env, "root")
        assert r.stdout.strip() == str(target)

    def test_reset(self, env, tmp_path):
        target = tmp_path / "x"
        target.mkdir()
        run_snip(env, "root", "set", str(target))
        r = run_snip(env, "root", "reset")
        assert r.returncode == 0
        r = run_snip(env, "root")
        assert r.stdout.strip().endswith("snippets")


class TestList:
    def test_empty(self, env):
        r = run_snip(env, "list")
        assert r.returncode == 0
        assert "no snippets" in r.stdout

    def test_basic(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "a.cpp").write_text("a")
        (root / "ds").mkdir()
        (root / "ds" / "segtree.cpp").write_text("x")
        run_snip(env, "root", "set", str(root))
        r = run_snip(env, "list")
        assert r.returncode == 0
        assert "a.cpp" in r.stdout
        assert "ds/segtree.cpp" in r.stdout


class TestShow:
    def test_basic(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "a.cpp").write_text("hello world\n")
        run_snip(env, "root", "set", str(root))
        r = run_snip(env, "show", "a")
        assert r.returncode == 0
        assert r.stdout == "hello world\n"

    def test_missing(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        run_snip(env, "root", "set", str(root))
        r = run_snip(env, "show", "nope")
        assert r.returncode == 1


class TestAdd:
    def test_basic(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        run_snip(env, "root", "set", str(root))
        src = tmp_path / "x.cpp"
        src.write_text("xyz")
        r = run_snip(env, "add", str(src))
        assert r.returncode == 0
        assert (root / "x.cpp").is_file()

    def test_as_name(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        run_snip(env, "root", "set", str(root))
        src = tmp_path / "x.cpp"
        src.write_text("xyz")
        r = run_snip(env, "add", str(src), "--name", "ds/x.cpp")
        assert r.returncode == 0
        assert (root / "ds" / "x.cpp").is_file()

    def test_missing_src(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        run_snip(env, "root", "set", str(root))
        r = run_snip(env, "add", str(tmp_path / "nope.cpp"))
        assert r.returncode == 1


class TestRemove:
    def test_confirm_yes(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "a.cpp").write_text("x")
        run_snip(env, "root", "set", str(root))
        r = run_snip(env, "remove", "a", input="y\n")
        assert r.returncode == 0
        assert not (root / "a.cpp").exists()

    def test_confirm_no(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "a.cpp").write_text("x")
        run_snip(env, "root", "set", str(root))
        r = run_snip(env, "remove", "a", input="n\n")
        assert r.returncode == 0
        assert (root / "a.cpp").exists()


class TestRename:
    def test_basic(self, env, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "a.cpp").write_text("x")
        run_snip(env, "root", "set", str(root))
        r = run_snip(env, "rename", "a", "b.cpp")
        assert r.returncode == 0
        assert (root / "b.cpp").exists()
        assert not (root / "a.cpp").exists()


class TestDispatch:
    def test_help(self, env):
        r = run_snip(env, "-h")
        assert r.returncode == 0
        assert "snippet" in r.stdout

    def test_unknown(self, env):
        r = run_snip(env, "nonsense")
        assert r.returncode == 2