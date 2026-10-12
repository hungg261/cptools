import json
from pathlib import Path

import pytest

from cptools.lib import history


@pytest.fixture
def fake_history_file(tmp_path, monkeypatch):
    f = tmp_path / "shared" / "history.json"
    monkeypatch.setattr(history, "_history_file", lambda: f)
    return f


class TestLoad:
    def test_missing_file(self, fake_history_file):
        assert history.load() == []

    def test_valid(self, fake_history_file):
        fake_history_file.parent.mkdir(parents=True, exist_ok=True)
        fake_history_file.write_text(
            json.dumps({"recent": [
                {"path": "/a.cpp", "opened_at": "2026-01-01T00:00:00"},
                {"path": "/b.cpp", "opened_at": "2026-01-02T00:00:00"},
            ]}),
            encoding="utf-8",
        )
        items = history.load()
        assert len(items) == 2
        assert items[0]["path"] == "/a.cpp"

    def test_legacy_list_format(self, fake_history_file):
        fake_history_file.parent.mkdir(parents=True, exist_ok=True)
        fake_history_file.write_text(
            json.dumps([{"path": "/legacy.cpp"}]),
            encoding="utf-8",
        )
        items = history.load()
        assert len(items) == 1
        assert items[0]["path"] == "/legacy.cpp"

    def test_invalid_json(self, fake_history_file):
        fake_history_file.parent.mkdir(parents=True, exist_ok=True)
        fake_history_file.write_text("garbage", encoding="utf-8")
        assert history.load() == []

    def test_filters_items_without_path(self, fake_history_file):
        fake_history_file.parent.mkdir(parents=True, exist_ok=True)
        fake_history_file.write_text(
            json.dumps({"recent": [
                {"path": "/a.cpp"},
                {"opened_at": "x"},  # no path
                "not a dict",
                {"path": "/b.cpp"},
            ]}),
            encoding="utf-8",
        )
        items = history.load()
        assert len(items) == 2


class TestAdd:
    def test_first_add(self, fake_history_file, tmp_path):
        p = tmp_path / "x.cpp"
        p.write_text("// x")
        history.add(p)
        items = history.load()
        assert len(items) == 1
        assert items[0]["path"] == str(p.resolve())

    def test_moves_to_top(self, fake_history_file, tmp_path):
        a = tmp_path / "a.cpp"; a.write_text("")
        b = tmp_path / "b.cpp"; b.write_text("")
        c = tmp_path / "c.cpp"; c.write_text("")

        history.add(a)
        history.add(b)
        history.add(c)
        history.add(a)  # re-open a

        items = history.load()
        assert [it["path"] for it in items] == [
            str(a.resolve()),
            str(c.resolve()),
            str(b.resolve()),
        ]

    def test_dedup(self, fake_history_file, tmp_path):
        p = tmp_path / "x.cpp"
        p.write_text("")
        history.add(p)
        history.add(p)
        assert len(history.load()) == 1

    def test_cap(self, fake_history_file, tmp_path):
        for i in range(20):
            f = tmp_path / f"f{i}.cpp"
            f.write_text("")
            history.add(f)
        assert len(history.load()) == history.MAX_ENTRIES


class TestClear:
    def test_clear(self, fake_history_file, tmp_path):
        p = tmp_path / "x.cpp"
        p.write_text("")
        history.add(p)
        assert len(history.load()) == 1
        history.clear()
        assert history.load() == []


class TestRemove:
    def test_remove_existing(self, fake_history_file, tmp_path):
        a = tmp_path / "a.cpp"; a.write_text("")
        b = tmp_path / "b.cpp"; b.write_text("")
        history.add(a)
        history.add(b)
        history.remove(a)
        items = history.load()
        assert len(items) == 1
        assert items[0]["path"] == str(b.resolve())

    def test_remove_missing(self, fake_history_file, tmp_path):
        a = tmp_path / "a.cpp"; a.write_text("")
        history.add(a)
        history.remove(tmp_path / "ghost.cpp")
        assert len(history.load()) == 1