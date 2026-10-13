import pytest
from pathlib import Path

from cptools.lib import folders


@pytest.fixture(autouse=True)
def fake_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CPTOOLS_CONFIG_ROOT", str(tmp_path / "cfg"))
    monkeypatch.setenv("CPTOOLS_DATA_ROOT", str(tmp_path / "data"))
    yield


@pytest.fixture
def cfg_file(tmp_path, monkeypatch):
    f = tmp_path / "folders.json"
    monkeypatch.setattr(folders, "_config_file", lambda: f)
    return f


class TestLoad:
    def test_missing(self, cfg_file):
        data = folders.load()
        assert data == {"folders": {}, "default": ""}

    def test_invalid_json(self, cfg_file):
        cfg_file.write_text("garbage", encoding="utf-8")
        assert folders.load() == {"folders": {}, "default": ""}

    def test_not_dict(self, cfg_file):
        cfg_file.write_text("[1,2,3]", encoding="utf-8")
        assert folders.load() == {"folders": {}, "default": ""}

    def test_valid(self, cfg_file):
        cfg_file.write_text(
            '{"folders": {"a": "/x"}, "default": "a"}',
            encoding="utf-8",
        )
        data = folders.load()
        assert data["folders"] == {"a": "/x"}
        assert data["default"] == "a"

    def test_filters_bad_entries(self, cfg_file):
        cfg_file.write_text(
            '{"folders": {"a": "/x", "b": 1, "": "/y", "c": ""}}',
            encoding="utf-8",
        )
        data = folders.load()
        assert data["folders"] == {"a": "/x"}


class TestSave:
    def test_roundtrip(self, cfg_file):
        folders.save({"folders": {"a": "/x"}, "default": "a"})
        data = folders.load()
        assert data["folders"] == {"a": "/x"}


class TestNames:
    def test_empty(self, cfg_file):
        assert folders.list_names() == []

    def test_sorted(self, cfg_file):
        folders.save({"folders": {"b": "/x", "a": "/y"}, "default": ""})
        assert folders.list_names() == ["a", "b"]


class TestGetPath:
    def test_basic(self, cfg_file):
        folders.save({"folders": {"a": "/x"}, "default": ""})
        assert folders.get_path("a") == Path("/x")

    def test_missing(self, cfg_file):
        assert folders.get_path("nope") is None

    def test_env_var_expansion(self, cfg_file, monkeypatch):
        monkeypatch.setenv("MYVAR", "/expanded")
        folders.save({"folders": {"a": "$MYVAR/x"}, "default": ""})
        assert folders.get_path("a") == Path("/expanded/x")


class TestResolveRef:
    def test_plain_absolute(self, tmp_path):
        abs_path = tmp_path / "abs" / "path"
        abs_path.mkdir(parents=True)
        p = folders.resolve_ref(str(abs_path))
        assert p == abs_path.resolve()

    def test_at_name(self, cfg_file):
        folders.save({"folders": {"cp": "/CP"}, "default": ""})
        assert folders.resolve_ref("@cp") == Path("/CP")

    def test_at_name_sub(self, cfg_file):
        folders.save({"folders": {"cp": "/CP"}, "default": ""})
        assert folders.resolve_ref("@cp/src") == Path("/CP/src")

    def test_at_name_backslash(self, cfg_file):
        folders.save({"folders": {"cp": "/CP"}, "default": ""})
        assert folders.resolve_ref("@cp\\src") == Path("/CP/src")

    def test_at_missing(self, cfg_file):
        assert folders.resolve_ref("@nope") is None

    def test_empty(self, cfg_file):
        assert folders.resolve_ref("") is None


class TestSetFolder:
    def test_adds(self, cfg_file):
        folders.set_folder("cp", "/CP")
        assert folders.get_path("cp") == Path("/CP")

    def test_first_becomes_default(self, cfg_file):
        folders.set_folder("cp", "/CP")
        assert folders.get_default() == "cp"

    def test_second_does_not_change_default(self, cfg_file):
        folders.set_folder("cp", "/CP")
        folders.set_folder("atc", "/ATC")
        assert folders.get_default() == "cp"


class TestRemoveFolder:
    def test_basic(self, cfg_file):
        folders.set_folder("cp", "/CP")
        assert folders.remove_folder("cp") is True
        assert folders.get_path("cp") is None

    def test_missing(self, cfg_file):
        assert folders.remove_folder("nope") is False

    def test_default_cleared(self, cfg_file):
        folders.set_folder("cp", "/CP")
        folders.remove_folder("cp")
        assert folders.get_default() == ""

    def test_default_moves(self, cfg_file):
        folders.set_folder("a", "/A")
        folders.set_folder("b", "/B")
        folders.set_default("a")
        folders.remove_folder("a")
        assert folders.get_default() == "b"


class TestRenameFolder:
    def test_basic(self, cfg_file):
        folders.set_folder("cp", "/CP")
        assert folders.rename_folder("cp", "code") is True
        assert folders.get_path("code") == Path("/CP")
        assert folders.get_path("cp") is None

    def test_missing(self, cfg_file):
        assert folders.rename_folder("nope", "x") is False

    def test_target_exists(self, cfg_file):
        folders.set_folder("a", "/A")
        folders.set_folder("b", "/B")
        assert folders.rename_folder("a", "b") is False

    def test_default_follows(self, cfg_file):
        folders.set_folder("cp", "/CP")
        folders.rename_folder("cp", "code")
        assert folders.get_default() == "code"


class TestSetDefault:
    def test_basic(self, cfg_file):
        folders.set_folder("a", "/A")
        folders.set_folder("b", "/B")
        assert folders.set_default("b") is True
        assert folders.get_default() == "b"

    def test_missing(self, cfg_file):
        assert folders.set_default("nope") is False


class TestFindNames:
    def test_exact(self, cfg_file):
        folders.save({"folders": {"cp": "/CP"}, "default": ""})
        assert folders.find_names("cp") == ["cp"]

    def test_prefix(self, cfg_file):
        folders.save({
            "folders": {"codeforces": "/cf", "coder": "/c"},
            "default": "",
        })
        result = folders.find_names("cod")
        assert set(result) == {"codeforces", "coder"}

    def test_substring(self, cfg_file):
        folders.save({"folders": {"my-codeforces": "/cf"}, "default": ""})
        assert folders.find_names("code") == ["my-codeforces"]

    def test_typo_fuzzy(self, cfg_file):
        folders.save({"folders": {"codeforces": "/cf"}, "default": ""})
        result = folders.find_names("codeforcse")
        assert "codeforces" in result

    def test_no_match(self, cfg_file):
        folders.save({"folders": {"cp": "/CP"}, "default": ""})
        assert folders.find_names("zzzzzzz") == []

    def test_empty_query(self, cfg_file):
        folders.save({"folders": {"cp": "/CP"}, "default": ""})
        assert folders.find_names("") == []


class TestPathOf:
    def test_unique(self, cfg_file):
        folders.save({"folders": {"cp": "/CP"}, "default": ""})
        name, path = folders.path_of("cp")
        assert name == "cp"
        assert path == Path("/CP")

    def test_ambiguous(self, cfg_file):
        folders.save({
            "folders": {"codeforces": "/a", "coder": "/b"},
            "default": "",
        })
        name, result = folders.path_of("cod")
        assert name is None
        assert isinstance(result, list)
        assert len(result) == 2

    def test_missing(self, cfg_file):
        folders.save({"folders": {"cp": "/CP"}, "default": ""})
        name, result = folders.path_of("zzzzzzz")
        assert name is None
        assert result == []

    def test_fuzzy_typo(self, cfg_file):
        folders.save({"folders": {"codeforces": "/CF"}, "default": ""})
        name, path = folders.path_of("codeforcse")
        assert name == "codeforces"


class TestResolveUserPath:
    """resolve_user_path: expand, join with CPTOOLS_CWD, resolve."""

    def test_absolute(self, tmp_path):
        p = tmp_path / "abs"
        p.mkdir()
        assert folders.resolve_user_path(str(p)) == p.resolve()

    def test_relative_joins_env_cwd(self, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.setenv("CPTOOLS_CWD", str(cwd))
        result = folders.resolve_user_path("sub")
        assert result == (cwd / "sub").resolve()

    def test_dot_resolves_to_env_cwd(self, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.setenv("CPTOOLS_CWD", str(cwd))
        assert folders.resolve_user_path(".") == cwd.resolve()

    def test_dotdot_goes_up(self, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.setenv("CPTOOLS_CWD", str(cwd))
        result = folders.resolve_user_path("..")
        assert result == tmp_path.resolve()

    def test_fallback_to_process_cwd(self, tmp_path, monkeypatch):
        monkeypatch.delenv("CPTOOLS_CWD", raising=False)
        monkeypatch.chdir(tmp_path)
        assert folders.resolve_user_path(".") == tmp_path.resolve()

    def test_invalid_env_cwd_ignored(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CPTOOLS_CWD", str(tmp_path / "does-not-exist"))
        monkeypatch.chdir(tmp_path)
        assert folders.resolve_user_path(".") == tmp_path.resolve()

    def test_env_var_expansion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MYROOT", str(tmp_path))
        result = folders.resolve_user_path("$MYROOT/x")
        assert result == (tmp_path / "x").resolve()

    def test_none_returns_none(self):
        assert folders.resolve_user_path(None) is None


class TestResolveRefRelative:
    """resolve_ref accepts non-@ paths, resolves against CPTOOLS_CWD."""

    def test_absolute(self, tmp_path):
        p = tmp_path / "abs"
        p.mkdir()
        assert folders.resolve_ref(str(p)) == p.resolve()

    def test_dot(self, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.setenv("CPTOOLS_CWD", str(cwd))
        assert folders.resolve_ref(".") == cwd.resolve()

    def test_relative_sub(self, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.setenv("CPTOOLS_CWD", str(cwd))
        result = folders.resolve_ref("sub/dir")
        assert result == (cwd / "sub" / "dir").resolve()

    def test_at_still_wins(self, cfg_file, tmp_path, monkeypatch):
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.setenv("CPTOOLS_CWD", str(cwd))
        folders.save({"folders": {"cp": str(tmp_path / "CP")}, "default": ""})
        assert folders.resolve_ref("@cp") == tmp_path / "CP"