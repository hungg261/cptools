import pytest

from cptools.lib import config as lib_config


@pytest.fixture
def fake_config_file(tmp_path, monkeypatch):
    f = tmp_path / "config.json"
    monkeypatch.setattr(lib_config, "_config_file", lambda: f)
    return f


class TestLoad:
    def test_missing_file(self, fake_config_file):
        assert lib_config.load() == {}

    def test_valid_file(self, fake_config_file):
        fake_config_file.write_text(
            '{"a": 1, "b": "x"}', encoding="utf-8"
        )
        assert lib_config.load() == {"a": 1, "b": "x"}

    def test_invalid_json(self, fake_config_file):
        fake_config_file.write_text("not json", encoding="utf-8")
        assert lib_config.load() == {}

    def test_not_a_dict(self, fake_config_file):
        fake_config_file.write_text("[1, 2, 3]", encoding="utf-8")
        assert lib_config.load() == {}


class TestSave:
    def test_writes_file(self, fake_config_file):
        lib_config.save({"x": 42})
        assert fake_config_file.exists()
        assert '"x": 42' in fake_config_file.read_text(encoding="utf-8")

    def test_roundtrip(self, fake_config_file):
        data = {"editors": {"vscode": "/usr/bin/code"}, "n": 5}
        lib_config.save(data)
        assert lib_config.load() == data


class TestGetSet:
    def test_get_missing(self, fake_config_file):
        assert lib_config.get("nope") is None
        assert lib_config.get("nope", "default") == "default"

    def test_set_and_get(self, fake_config_file):
        lib_config.set("foo", "bar")
        assert lib_config.get("foo") == "bar"

    def test_set_preserves_others(self, fake_config_file):
        lib_config.save({"a": 1, "b": 2})
        lib_config.set("c", 3)
        assert lib_config.load() == {"a": 1, "b": 2, "c": 3}

    def test_set_overwrites(self, fake_config_file):
        lib_config.set("k", "old")
        lib_config.set("k", "new")
        assert lib_config.get("k") == "new"


class TestUpdate:
    def test_multiple_keys(self, fake_config_file):
        lib_config.save({"a": 1})
        lib_config.update(b=2, c=3)
        assert lib_config.load() == {"a": 1, "b": 2, "c": 3}


class TestDelete:
    def test_delete_existing(self, fake_config_file):
        lib_config.save({"a": 1, "b": 2})
        assert lib_config.delete("a") is True
        assert lib_config.load() == {"b": 2}

    def test_delete_missing(self, fake_config_file):
        lib_config.save({"a": 1})
        assert lib_config.delete("x") is False
        assert lib_config.load() == {"a": 1}