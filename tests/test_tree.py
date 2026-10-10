import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "tree"


@pytest.fixture
def run_tree(tmp_path):
    config_dir = tmp_path / "_config"
    data_dir = tmp_path / "_data"
    cache_dir = tmp_path / "_cache"
    for d in (config_dir, data_dir, cache_dir):
        d.mkdir()

    def _run(*args):
        env = os.environ.copy()
        env["CPTOOLS_PLUGIN_NAME"] = "tree"
        env["CPTOOLS_INVOKED_AS"] = "tree"
        env["CPTOOLS_PLUGIN_CONFIG_DIR"] = str(config_dir)
        env["CPTOOLS_PLUGIN_DATA_DIR"] = str(data_dir)
        env["CPTOOLS_PLUGIN_CACHE_DIR"] = str(cache_dir)
        env["CPTOOLS_PROTOCOL"] = "1"
        env["CPTOOLS_OUTPUT"] = "human"
        env["CPTOOLS_CWD"] = os.getcwd()
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, "main.py", *args],
            cwd=PLUGIN_DIR,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    return _run


@pytest.fixture
def sample_tree(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("a")
    (root / "b.txt").write_text("b")
    d1 = root / "dir1"
    d1.mkdir()
    (d1 / "c.txt").write_text("c")
    d2 = root / "dir2"
    d2.mkdir()
    (d2 / "sub").mkdir()
    (d2 / "sub" / "deep.txt").write_text("d")
    return root


class TestBasic:
    def test_empty_dir(self, run_tree, tmp_path):
        root = tmp_path / "empty"
        root.mkdir()
        r = run_tree(str(root))
        assert r.returncode == 0
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 1
        assert lines[0] == str(root.resolve())

    def test_fancy_default(self, run_tree, sample_tree):
        r = run_tree(str(sample_tree))
        assert r.returncode == 0
        out = r.stdout
        assert "├──" in out or "└──" in out
        assert "│" in out or "└──" in out
        assert "dir1" in out
        assert "c.txt" in out
        assert "a.txt" in out

    def test_simple_mode(self, run_tree, sample_tree):
        r = run_tree(str(sample_tree), "-s")
        assert r.returncode == 0
        out = r.stdout
        assert "+--" in out
        assert "`--" in out
        assert "├──" not in out
        assert "└──" not in out
        assert "│" not in out

    def test_dirs_first(self, run_tree, sample_tree):
        r = run_tree(str(sample_tree))
        lines = r.stdout.splitlines()[1:]
        # lines are: dir1, c.txt, dir2, sub, deep.txt, a.txt, b.txt
        # find positions of a.txt and dir1
        idx_dir = next(i for i, l in enumerate(lines) if "dir1" in l)
        idx_file = next(i for i, l in enumerate(lines) if "a.txt" in l)
        assert idx_dir < idx_file

    def test_relative_path(self, run_tree, sample_tree, monkeypatch):
        monkeypatch.chdir(sample_tree)
        r = run_tree(".")
        assert r.returncode == 0
        assert "dir1" in r.stdout


class TestDepth:
    def test_depth_1(self, run_tree, sample_tree):
        r = run_tree(str(sample_tree), "-d", "1")
        assert r.returncode == 0
        assert "dir1" in r.stdout
        assert "c.txt" not in r.stdout  # depth 2 not shown

    def test_depth_2(self, run_tree, sample_tree):
        r = run_tree(str(sample_tree), "-d", "2")
        assert r.returncode == 0
        assert "c.txt" in r.stdout
        assert "deep.txt" not in r.stdout


class TestExclude:
    def test_exclude_file_pattern(self, run_tree, sample_tree):
        r = run_tree(str(sample_tree), "-e", "*.txt")
        assert r.returncode == 0
        assert "a.txt" not in r.stdout
        assert "c.txt" not in r.stdout
        assert "dir1" in r.stdout

    def test_exclude_dir(self, run_tree, sample_tree):
        r = run_tree(str(sample_tree), "-e", "dir1")
        assert r.returncode == 0
        assert "dir1" not in r.stdout
        assert "c.txt" not in r.stdout
        assert "dir2" in r.stdout

    def test_exclude_multiple(self, run_tree, sample_tree):
        r = run_tree(str(sample_tree), "-e", "*.txt", "-e", "dir1")
        assert r.returncode == 0
        assert "a.txt" not in r.stdout
        assert "dir1" not in r.stdout
        assert "dir2" in r.stdout


class TestHidden:
    def test_hidden_by_default(self, run_tree, sample_tree):
        (sample_tree / ".secret").write_text("x")
        r = run_tree(str(sample_tree))
        assert ".secret" not in r.stdout

    def test_all_shows_hidden(self, run_tree, sample_tree):
        (sample_tree / ".secret").write_text("x")
        r = run_tree(str(sample_tree), "-a")
        assert ".secret" in r.stdout


class TestErrors:
    def test_not_found(self, run_tree, tmp_path):
        r = run_tree(str(tmp_path / "nope"))
        assert r.returncode == 1
        assert "not found" in r.stderr

    def test_file_as_path(self, run_tree, tmp_path):
        f = tmp_path / "single.txt"
        f.write_text("x")
        r = run_tree(str(f))
        assert r.returncode == 0
        assert "single.txt" in r.stdout


class TestConfig:
    def test_show_default(self, run_tree):
        r = run_tree("config", "show")
        assert r.returncode == 0
        cfg = json.loads(r.stdout)
        assert cfg["max_depth"] == 0
        assert cfg["show_hidden"] is False
        assert "__pycache__" in cfg["default_excludes"]

    def test_set_max_depth(self, run_tree):
        r = run_tree("config", "set", "max_depth", "3")
        assert r.returncode == 0
        r = run_tree("config", "show")
        cfg = json.loads(r.stdout)
        assert cfg["max_depth"] == 3

    def test_set_show_hidden(self, run_tree):
        r = run_tree("config", "set", "show_hidden", "true")
        assert r.returncode == 0
        r = run_tree("config", "show")
        cfg = json.loads(r.stdout)
        assert cfg["show_hidden"] is True

    def test_set_bad_key(self, run_tree):
        r = run_tree("config", "set", "unknown", "1")
        assert r.returncode == 2

    def test_reset(self, run_tree):
        run_tree("config", "set", "max_depth", "5")
        run_tree("config", "reset")
        r = run_tree("config", "show")
        cfg = json.loads(r.stdout)
        assert cfg["max_depth"] == 0

    def test_exclude_add_remove(self, run_tree):
        r = run_tree("config", "exclude", "add", "temp")
        assert r.returncode == 0
        r = run_tree("config", "exclude", "list")
        assert "temp" in r.stdout
        r = run_tree("config", "exclude", "remove", "temp")
        assert r.returncode == 0
        r = run_tree("config", "exclude", "list")
        assert "temp" not in r.stdout

    def test_exclude_remove_missing(self, run_tree):
        r = run_tree("config", "exclude", "remove", "nope")
        assert r.returncode == 1

    def test_exclude_clear(self, run_tree):
        r = run_tree("config", "exclude", "clear")
        assert r.returncode == 0
        r = run_tree("config", "exclude", "list")
        assert r.stdout.strip() == ""

    def test_config_from_file(self, run_tree, tmp_path, sample_tree):
        # set via config, then run tree, verify applied
        run_tree("config", "exclude", "add", "*.txt")
        r = run_tree(str(sample_tree))
        assert "a.txt" not in r.stdout
        assert "c.txt" not in r.stdout


class TestDispatch:
    def test_help(self, run_tree):
        r = run_tree("-h")
        assert r.returncode == 0
        assert "usage" in r.stdout

    def test_no_args(self, run_tree, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        r = run_tree()
        assert r.returncode == 0
        assert str(tmp_path.resolve()) in r.stdout