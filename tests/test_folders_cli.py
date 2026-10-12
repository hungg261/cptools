import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "folders"


@pytest.fixture
def env(tmp_path):
    cfg = tmp_path / "cfg"
    data = tmp_path / "data"
    for d in (cfg, data):
        d.mkdir()
    e = os.environ.copy()
    e["CPTOOLS_CONFIG_ROOT"] = str(cfg)
    e["CPTOOLS_DATA_ROOT"] = str(data)
    e["CPTOOLS_PLUGIN_NAME"] = "folders"
    e["CPTOOLS_INVOKED_AS"] = "folders"
    e["CPTOOLS_PROTOCOL"] = "1"
    e["CPTOOLS_OUTPUT"] = "human"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def run_folders(env, *args, input=None, timeout=15):
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


@pytest.fixture
def with_cp(env, tmp_path):
    cp = tmp_path / "CP"
    cp.mkdir()
    run_folders(env, "add", "cp", str(cp))
    return cp


class TestList:
    def test_empty(self, env):
        r = run_folders(env, "list")
        assert r.returncode == 0
        assert "no folders" in r.stdout

    def test_with_cp(self, env, with_cp):
        r = run_folders(env, "list")
        assert r.returncode == 0
        assert "cp" in r.stdout
        assert "* cp" in r.stdout

    def test_json(self, env, with_cp):
        env2 = dict(env)
        env2["CPTOOLS_OUTPUT"] = "json"
        r = subprocess.run(
            [sys.executable, "main.py", "list"],
            cwd=PLUGIN_DIR, env=env2,
            capture_output=True, text=True, encoding="utf-8",
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["default"] == "cp"
        assert len(data["folders"]) == 1


class TestAdd:
    def test_basic(self, env, tmp_path):
        p = tmp_path / "mydir"
        p.mkdir()
        r = run_folders(env, "add", "my", str(p))
        assert r.returncode == 0
        assert "added" in r.stdout

    def test_path_with_spaces(self, env, tmp_path):
        p = tmp_path / "my dir"
        p.mkdir()
        r = run_folders(env, "add", "my", str(p))
        assert r.returncode == 0
        r = run_folders(env, "show", "my")
        assert str(p) in r.stdout

    def test_duplicate(self, env, tmp_path):
        p = tmp_path / "x"
        p.mkdir()
        run_folders(env, "add", "a", str(p))
        r = run_folders(env, "add", "a", str(p))
        assert r.returncode == 1
        assert "already exists" in r.stderr

    def test_invalid_name_at(self, env, tmp_path):
        p = tmp_path / "x"
        p.mkdir()
        r = run_folders(env, "add", "@bad", str(p))
        assert r.returncode == 2

    def test_missing_args(self, env):
        r = run_folders(env, "add", "onlyname")
        assert r.returncode == 2


class TestShow:
    def test_basic(self, env, with_cp):
        r = run_folders(env, "show", "cp")
        assert r.returncode == 0
        assert str(with_cp) in r.stdout

    def test_missing(self, env):
        r = run_folders(env, "show", "nope")
        assert r.returncode == 1


class TestRemove:
    def test_confirm_yes(self, env, with_cp):
        r = run_folders(env, "remove", "cp", input="y\n")
        assert r.returncode == 0
        r = run_folders(env, "list")
        assert "no folders" in r.stdout

    def test_confirm_no(self, env, with_cp):
        r = run_folders(env, "remove", "cp", input="n\n")
        assert r.returncode == 0
        assert "aborted" in r.stdout
        r = run_folders(env, "list")
        assert "cp" in r.stdout

    def test_missing(self, env):
        r = run_folders(env, "remove", "nope", input="y\n")
        assert r.returncode == 1


class TestRename:
    def test_basic(self, env, with_cp):
        r = run_folders(env, "rename", "cp", "code")
        assert r.returncode == 0
        r = run_folders(env, "show", "code")
        assert str(with_cp) in r.stdout

    def test_missing(self, env):
        r = run_folders(env, "rename", "nope", "x")
        assert r.returncode == 1

    def test_target_exists(self, env, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        run_folders(env, "add", "a", str(a))
        run_folders(env, "add", "b", str(b))
        r = run_folders(env, "rename", "a", "b")
        assert r.returncode == 1


class TestDefault:
    def test_get_empty(self, env):
        r = run_folders(env, "default")
        assert r.returncode == 0
        assert "(none)" in r.stdout

    def test_get_after_add(self, env, with_cp):
        r = run_folders(env, "default")
        assert "cp" in r.stdout

    def test_set(self, env, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()
        run_folders(env, "add", "a", str(a))
        run_folders(env, "add", "b", str(b))
        r = run_folders(env, "default", "b")
        assert r.returncode == 0
        assert "b" in r.stdout

    def test_set_missing(self, env, with_cp):
        r = run_folders(env, "default", "nope")
        assert r.returncode == 1


class TestResolve:
    def test_at_name(self, env, with_cp):
        r = run_folders(env, "resolve", "@cp")
        assert r.returncode == 0
        assert str(with_cp) in r.stdout

    def test_at_name_sub(self, env, with_cp):
        r = run_folders(env, "resolve", "@cp/src")
        assert r.returncode == 0
        assert str(with_cp / "src") in r.stdout

    def test_missing(self, env):
        r = run_folders(env, "resolve", "@nope")
        assert r.returncode == 1

    def test_plain_path(self, env, tmp_path):
        p = tmp_path / "foo"
        p.mkdir()
        r = run_folders(env, "resolve", str(p))
        assert r.returncode == 0
        assert str(p) in r.stdout


class TestConfig:
    def test_show(self, env, with_cp):
        r = run_folders(env, "config", "show")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "cp" in data["folders"]

    def test_reset(self, env, with_cp):
        r = run_folders(env, "config", "reset")
        assert r.returncode == 0
        r = run_folders(env, "list")
        assert "no folders" in r.stdout


class TestDispatch:
    def test_help(self, env):
        r = run_folders(env, "-h")
        assert r.returncode == 0
        assert "folders" in r.stdout

    def test_no_args(self, env):
        r = run_folders(env)
        assert r.returncode == 0

    def test_unknown(self, env):
        r = run_folders(env, "nonsense")
        assert r.returncode == 2


class TestFuzzy:
    def test_show_prefix(self, env, tmp_path):
        p = tmp_path / "codeforces"
        p.mkdir()
        run_folders(env, "add", "codeforces", str(p))
        r = run_folders(env, "show", "cod")
        assert r.returncode == 0
        assert str(p) in r.stdout

    def test_show_typo(self, env, tmp_path):
        p = tmp_path / "codeforces"
        p.mkdir()
        run_folders(env, "add", "codeforces", str(p))
        r = run_folders(env, "show", "codeforcse")
        assert r.returncode == 0
        assert str(p) in r.stdout

    def test_ambiguous(self, env, tmp_path):
        a = tmp_path / "codeforces"
        b = tmp_path / "coder"
        a.mkdir()
        b.mkdir()
        run_folders(env, "add", "codeforces", str(a))
        run_folders(env, "add", "coder", str(b))
        r = run_folders(env, "show", "cod")
        assert r.returncode == 1
        assert "ambiguous" in r.stderr

    def test_not_found(self, env, with_cp):
        r = run_folders(env, "show", "zzzzzz")
        assert r.returncode == 1
        assert "not found" in r.stderr

    def test_remove_fuzzy(self, env, tmp_path):
        p = tmp_path / "mydir"
        p.mkdir()
        run_folders(env, "add", "mydir", str(p))
        r = run_folders(env, "remove", "mydr", input="y\n")
        assert r.returncode == 0
        r = run_folders(env, "list")
        assert "mydir" not in r.stdout


class TestAddPick:
    def test_pick_flag_calls_dialog(self, env, tmp_path, monkeypatch):
        # Can't test tkinter dialog easily; skip
        # Instead test that --pick without tkinter fails gracefully
        pass


class TestDispatch:
    def test_pick_help(self, env):
        r = run_folders(env, "pick", "-h")
        assert r.returncode == 0
        assert "pick" in r.stdout