import pytest

from cptools.lib import config as host_config
from cptools.lib import editor_registry as reg


@pytest.fixture
def fake_config(tmp_path, monkeypatch):
    f = tmp_path / "config.json"
    monkeypatch.setattr(host_config, "_config_file", lambda: f)
    return f


@pytest.fixture
def fake_which(monkeypatch):
    found = {}

    def _which(name):
        return found.get(name)

    monkeypatch.setattr(reg.shutil, "which", _which)
    return found


class TestDetect:
    def test_empty(self, fake_which, monkeypatch):
        monkeypatch.setattr(reg.sys, "platform", "linux")
        monkeypatch.setattr(reg, "_resolve_exe", lambda e, p: None)
        assert reg.detect_editors() == {}

    def test_picks_up_which(self, fake_which):
        fake_which["code"] = "/usr/bin/code"
        fake_which["vim"] = "/usr/bin/vim"
        result = reg.detect_editors()
        assert result["vscode"] == "/usr/bin/code"
        assert result["vim"] == "/usr/bin/vim"


class TestListEditors:
    def test_detected_only(self, fake_config, monkeypatch):
        monkeypatch.setattr(reg, "detect_editors", lambda: {"vscode": "/c"})
        assert reg.list_editors() == {"vscode": "/c"}

    def test_user_overrides_detected(self, fake_config, monkeypatch):
        monkeypatch.setattr(reg, "detect_editors", lambda: {"vscode": "/detected"})
        host_config.set("editor_registry", {"vscode": "/user/path"})
        assert reg.list_editors() == {"vscode": "/user/path"}

    def test_user_adds_new(self, fake_config, monkeypatch):
        monkeypatch.setattr(reg, "detect_editors", lambda: {})
        host_config.set("editor_registry", {"myedit": "/custom"})
        assert reg.list_editors() == {"myedit": "/custom"}


class TestSetRemove:
    def test_set_new(self, fake_config, monkeypatch):
        monkeypatch.setattr(reg, "detect_editors", lambda: {})
        reg.set_editor("foo", "/bar")
        assert host_config.get("editor_registry") == {"foo": "/bar"}

    def test_set_preserves_others(self, fake_config):
        reg.set_editor("a", "/a")
        reg.set_editor("b", "/b")
        assert host_config.get("editor_registry") == {"a": "/a", "b": "/b"}

    def test_remove(self, fake_config):
        reg.set_editor("a", "/a")
        reg.set_editor("b", "/b")
        reg.remove_editor("a")
        assert host_config.get("editor_registry") == {"b": "/b"}

    def test_remove_missing(self, fake_config):
        reg.set_editor("a", "/a")
        reg.remove_editor("nonexistent")
        assert host_config.get("editor_registry") == {"a": "/a"}


class TestDefault:
    def test_default_empty(self, fake_config):
        assert reg.get_default() == ""

    def test_set_default(self, fake_config):
        reg.set_default("vscode")
        assert reg.get_default() == "vscode"


class TestOrdered:
    def test_known_first(self):
        eds = {"vim": "v", "codeblocks": "c", "vscode": "co"}
        assert reg.ordered_keys(eds) == ["codeblocks", "vscode", "vim"]

    def test_unknown_at_end(self):
        eds = {"vim": "v", "custom": "c", "codeblocks": "cb"}
        assert reg.ordered_keys(eds) == ["codeblocks", "vim", "custom"]


class TestLabel:
    def test_known(self):
        assert reg.label_for("vscode") == "VS Code"
        assert reg.label_for("codeblocks") == "Code::Blocks"

    def test_unknown(self):
        assert reg.label_for("custom") == "custom"