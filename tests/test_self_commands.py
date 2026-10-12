import json
from pathlib import Path

import pytest

from cptools import paths
from cptools.commands import self as self_cmd


@pytest.fixture
def fake_roots(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    data = tmp_path / "data"
    cfg.mkdir()
    data.mkdir()

    monkeypatch.setattr(paths, "config_root", lambda: cfg)
    monkeypatch.setattr(paths, "data_root", lambda: data)

    return {"config": cfg, "data": data}


@pytest.fixture
def populated(fake_roots):
    d = fake_roots["data"]
    c = fake_roots["config"]

    (d / "data" / "link-manager").mkdir(parents=True)
    (d / "data" / "link-manager" / "problems.json").write_text("[]")
    (d / "data" / "runner" / "tests").mkdir(parents=True)
    (d / "data" / "runner" / "tests" / "abc.json").write_text("{}")

    (d / "cache" / "runner" / "bin").mkdir(parents=True)
    (d / "cache" / "runner" / "bin" / "out.exe").write_bytes(b"x" * 100)

    (d / "shared").mkdir()
    (d / "shared" / "history.json").write_text("{}")

    (d / "plugins" / "myplugin").mkdir(parents=True)
    (d / "plugins" / "myplugin" / "main.py").write_text("print()")

    (c / "plugins" / "runner").mkdir(parents=True)
    (c / "plugins" / "runner" / "config.json").write_text("{}")
    (c / "config.json").write_text("{}")

    return fake_roots


# ---------------------------------------------------------------- paths

class TestPaths:
    def test_basic(self, fake_roots, capsys):
        rc = self_cmd.cmd_paths([])
        out = capsys.readouterr().out
        assert rc == 0
        assert str(fake_roots["config"]) in out
        assert str(fake_roots["data"]) in out


# ---------------------------------------------------------------- version

class TestVersion:
    def test_basic(self, capsys):
        rc = self_cmd.cmd_version([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "cptools" in out
        assert "python" in out
        assert "platform" in out


# ---------------------------------------------------------------- reset

class TestResetData:
    def test_data_only(self, populated):
        rc = self_cmd.cmd_reset(["--data", "-y"])
        assert rc == 0
        d = populated["data"]
        assert not (d / "data").exists()
        assert not (d / "shared").exists()
        # Cache and plugins must remain
        assert (d / "cache").exists()
        assert (d / "plugins").exists()
        # Config must remain
        assert populated["config"].exists()

    def test_cache_only(self, populated):
        rc = self_cmd.cmd_reset(["--cache", "-y"])
        assert rc == 0
        d = populated["data"]
        assert not (d / "cache").exists()
        assert (d / "data").exists()
        assert (d / "shared").exists()

    def test_config_only(self, populated):
        rc = self_cmd.cmd_reset(["--config", "-y"])
        assert rc == 0
        assert not populated["config"].exists()
        assert (populated["data"] / "data").exists()

    def test_all(self, populated):
        rc = self_cmd.cmd_reset(["--all", "-y"])
        assert rc == 0
        assert not populated["config"].exists()
        assert not populated["data"].exists()


class TestResetPlugin:
    def test_plugin_data_and_cache(self, populated):
        rc = self_cmd.cmd_reset(["--plugin", "link-manager", "-y"])
        assert rc == 0
        d = populated["data"]
        assert not (d / "data" / "link-manager").exists()
        # Other plugin data still there
        assert (d / "data" / "runner").exists()

    def test_plugin_with_config(self, populated):
        rc = self_cmd.cmd_reset(
            ["--plugin", "runner", "--with-config", "-y"]
        )
        assert rc == 0
        d = populated["data"]
        c = populated["config"]
        assert not (d / "data" / "runner").exists()
        assert not (d / "cache" / "runner").exists()
        assert not (c / "plugins" / "runner").exists()
        # Top-level config remains
        assert (c / "config.json").exists()


class TestResetErrors:
    def test_no_flags(self, populated, capsys):
        rc = self_cmd.cmd_reset([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "usage" in out.lower() or "reset" in out.lower()

    def test_unknown_flag(self, populated):
        rc = self_cmd.cmd_reset(["--nonsense"])
        assert rc == 2

    def test_plugin_and_data(self, populated):
        rc = self_cmd.cmd_reset(["--plugin", "x", "--data"])
        assert rc == 2

    def test_plugin_missing_name(self, populated):
        rc = self_cmd.cmd_reset(["--plugin"])
        assert rc == 2

    def test_nothing_to_delete(self, fake_roots, capsys):
        rc = self_cmd.cmd_reset(["--data", "-y"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "nothing to delete" in out


class TestResetConfirm:
    def test_abort(self, populated, monkeypatch, capsys):
        monkeypatch.setattr(self_cmd, "_confirm", lambda msg: False)
        rc = self_cmd.cmd_reset(["--data"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "aborted" in out
        # Nothing deleted
        assert (populated["data"] / "data").exists()

    def test_accept(self, populated, monkeypatch):
        monkeypatch.setattr(self_cmd, "_confirm", lambda msg: True)
        rc = self_cmd.cmd_reset(["--data"])
        assert rc == 0
        assert not (populated["data"] / "data").exists()


# ---------------------------------------------------------------- doctor

class TestDoctor:
    def test_runs(self, fake_roots, capsys):
        rc = self_cmd.cmd_doctor([])
        out = capsys.readouterr().out
        # Returns 0 if no warnings, 1 otherwise (compiler may be missing)
        assert rc in (0, 1)
        assert "python" in out
        assert "platformdirs" in out


# ---------------------------------------------------------------- dispatch

class TestDispatch:
    def test_help(self, capsys):
        rc = self_cmd.handle([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "usage" in out.lower()

    def test_unknown(self):
        rc = self_cmd.handle(["nonsense"])
        assert rc == 2