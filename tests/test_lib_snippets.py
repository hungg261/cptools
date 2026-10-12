import pytest
from pathlib import Path

from cptools.lib import snippets


@pytest.fixture(autouse=True)
def fake_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CPTOOLS_CONFIG_ROOT", str(tmp_path / "cfg"))
    monkeypatch.setenv("CPTOOLS_DATA_ROOT", str(tmp_path / "data"))
    yield


@pytest.fixture
def snippet_root(tmp_path):
    root = tmp_path / "snips"
    root.mkdir()
    cfg = snippets.load_config()
    cfg["root_dir"] = str(root)
    snippets.save_config(cfg)
    yield root
    cfg["root_dir"] = ""
    snippets.save_config(cfg)


class TestDefaultRoot:
    def test_empty_config(self):
        r = snippets.root_dir()
        assert r.name == "snippets"
        assert r.exists()


class TestIterAll:
    def test_empty(self, snippet_root):
        assert snippets.iter_all() == []

    def test_flat(self, snippet_root):
        (snippet_root / "a.cpp").write_text("a")
        (snippet_root / "b.py").write_text("b")
        files = snippets.iter_all()
        assert [p.name for p in files] == ["a.cpp", "b.py"]

    def test_nested(self, snippet_root):
        (snippet_root / "ds").mkdir()
        (snippet_root / "ds" / "segtree.cpp").write_text("x")
        (snippet_root / "misc" / "io").mkdir(parents=True)
        (snippet_root / "misc" / "io" / "fastio.cpp").write_text("y")
        names = [snippets.relpath(f) for f in snippets.iter_all()]
        assert "ds/segtree.cpp" in names
        assert "misc/io/fastio.cpp" in names

    def test_skip_dotfiles(self, snippet_root):
        (snippet_root / ".hidden").write_text("h")
        (snippet_root / ".git").mkdir()
        (snippet_root / ".git" / "config").write_text("c")
        (snippet_root / "visible.cpp").write_text("v")
        files = snippets.iter_all()
        assert [f.name for f in files] == ["visible.cpp"]

    def test_skip_ignored_dirs(self, snippet_root):
        (snippet_root / "__pycache__").mkdir()
        (snippet_root / "__pycache__" / "x.pyc").write_text("x")
        (snippet_root / "ok.cpp").write_text("y")
        files = snippets.iter_all()
        assert [f.name for f in files] == ["ok.cpp"]

    def test_custom_ignore(self, snippet_root):
        (snippet_root / "private").mkdir()
        (snippet_root / "private" / "x.cpp").write_text("x")
        (snippet_root / "public.cpp").write_text("p")
        cfg = snippets.load_config()
        cfg["ignore"] = ["private"]
        snippets.save_config(cfg)
        files = snippets.iter_all()
        assert [f.name for f in files] == ["public.cpp"]


class TestResolve:
    def test_exact(self, snippet_root):
        f = snippet_root / "ds" / "segtree.cpp"
        f.parent.mkdir()
        f.write_text("x")
        assert snippets.resolve("ds/segtree.cpp") == f

    def test_without_ext(self, snippet_root):
        f = snippet_root / "ds" / "segtree.cpp"
        f.parent.mkdir()
        f.write_text("x")
        assert snippets.resolve("ds/segtree") == f

    def test_unique_stem(self, snippet_root):
        f = snippet_root / "ds" / "segtree.cpp"
        f.parent.mkdir()
        f.write_text("x")
        assert snippets.resolve("segtree") == f

    def test_ambiguous_returns_none(self, snippet_root):
        (snippet_root / "ds").mkdir()
        (snippet_root / "ds" / "segtree.cpp").write_text("x")
        (snippet_root / "misc").mkdir()
        (snippet_root / "misc" / "segtree.cpp").write_text("y")
        assert snippets.resolve("segtree") is None

    def test_windows_separator(self, snippet_root):
        f = snippet_root / "ds" / "segtree.cpp"
        f.parent.mkdir()
        f.write_text("x")
        assert snippets.resolve("ds\\segtree.cpp") == f

    def test_not_found(self, snippet_root):
        assert snippets.resolve("nope") is None


class TestRead:
    def test_basic(self, snippet_root):
        (snippet_root / "a.cpp").write_text("hello")
        assert snippets.read("a") == "hello"

    def test_missing(self, snippet_root):
        assert snippets.read("nope") is None


class TestAddFile:
    def test_basic(self, snippet_root, tmp_path):
        src = tmp_path / "src.cpp"
        src.write_text("x")
        dest = snippets.add_file(src)
        assert dest.name == "src.cpp"
        assert dest.read_text() == "x"

    def test_as_name(self, snippet_root, tmp_path):
        src = tmp_path / "src.cpp"
        src.write_text("x")
        dest = snippets.add_file(src, as_name="ds/x.cpp")
        assert dest == snippet_root / "ds" / "x.cpp"

    def test_missing_src(self, snippet_root, tmp_path):
        with pytest.raises(FileNotFoundError):
            snippets.add_file(tmp_path / "nope.cpp")


class TestRemove:
    def test_basic(self, snippet_root):
        (snippet_root / "a.cpp").write_text("x")
        assert snippets.remove("a") is True
        assert not (snippet_root / "a.cpp").exists()

    def test_missing(self, snippet_root):
        assert snippets.remove("nope") is False


class TestRename:
    def test_basic(self, snippet_root):
        (snippet_root / "a.cpp").write_text("x")
        p = snippets.rename("a", "b.cpp")
        assert p == snippet_root / "b.cpp"
        assert p.read_text() == "x"

    def test_into_subfolder(self, snippet_root):
        (snippet_root / "a.cpp").write_text("x")
        p = snippets.rename("a", "ds/b.cpp")
        assert p == snippet_root / "ds" / "b.cpp"

    def test_missing_src(self, snippet_root):
        assert snippets.rename("nope", "x") is None

    def test_target_exists(self, snippet_root):
        (snippet_root / "a.cpp").write_text("x")
        (snippet_root / "b.cpp").write_text("y")
        assert snippets.rename("a", "b.cpp") is None