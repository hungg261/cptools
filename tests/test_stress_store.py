import os
import sys
from pathlib import Path

import pytest

# stress plugin dir
PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "stress"


@pytest.fixture(autouse=True)
def _setup_env(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    for d in (cfg, data, cache):
        d.mkdir()
    monkeypatch.setenv("CPTOOLS_PLUGIN_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("CPTOOLS_PLUGIN_DATA_DIR", str(data))
    monkeypatch.setenv("CPTOOLS_PLUGIN_CACHE_DIR", str(cache))
    # force reload of store with new env
    if "store" in sys.modules:
        del sys.modules["store"]
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.insert(0, str(PLUGIN_DIR))


@pytest.fixture
def store():
    import importlib
    mod = importlib.import_module("store")
    importlib.reload(mod)
    return mod


@pytest.fixture
def src(tmp_path):
    f = tmp_path / "sol.cpp"
    f.write_text("// x")
    return f


class TestGlobalConfig:
    def test_defaults(self, store):
        cfg = store.load_config()
        assert cfg["compiler"] == "g++"
        assert cfg["time_limit"] == 1.0
        assert cfg["warn_factor"] == 1.0
        assert cfg["slow_factor"] == 2.0
        assert cfg["fail_factor"] == 3.0
        assert cfg["stop_on_fail"] is True
        assert cfg["max_fails"] == 50

    def test_roundtrip(self, store):
        cfg = store.load_config()
        cfg["time_limit"] = 2.5
        cfg["compiler"] = "clang++"
        store.save_config(cfg)
        cfg2 = store.load_config()
        assert cfg2["time_limit"] == 2.5
        assert cfg2["compiler"] == "clang++"

    def test_int_coercion(self, store):
        store.save_config({"max_fails": "99"})
        cfg = store.load_config()
        assert cfg["max_fails"] == 99


class TestPerSolution:
    def test_defaults(self, store, src):
        data = store.load_solution(src)
        assert data["source"] == str(src.resolve())
        assert data["mode"] == "standard"
        assert data["seed"] == 0
        assert data["randomize_per_iter"] is False
        assert data["standard"]["match_mode"] == "token"

    def test_roundtrip(self, store, src):
        data = store.load_solution(src)
        data["generator"] = "/gen.cpp"
        data["seed"] = 42
        store.save_solution(data)
        data2 = store.load_solution(src)
        assert data2["generator"] == "/gen.cpp"
        assert data2["seed"] == 42

    def test_partial_data_filled(self, store, src):
        data = store.load_solution(src)
        data["standard"] = {"extra": "/brute.cpp"}  # no match_mode
        store.save_solution(data)
        data2 = store.load_solution(src)
        assert data2["standard"]["match_mode"] == "token"
        assert data2["standard"]["extra"] == "/brute.cpp"


class TestWorkDir:
    def test_deterministic(self, store, src):
        a = store.work_root(src)
        b = store.work_root(src)
        assert a == b

    def test_bin_dir_created(self, store, src):
        p = store.bin_dir(src)
        assert p.exists()
        assert p.name == "bin"


class TestFails:
    def test_save_and_clear(self, store, src):
        d = store.save_fail(
            src, 1, 12345, "WA",
            input_text="1 2\n",
            expected="3\n",
            got="4\n",
        )
        assert d.exists()
        assert (d / "input.txt").read_text() == "1 2\n"
        assert (d / "expected.txt").read_text() == "3\n"
        assert (d / "got.txt").read_text() == "4\n"

        store.clear_fails(src)
        assert not d.exists()

    def test_meta_json(self, store, src):
        import json
        d = store.save_fail(src, 7, 999, "TLE", input_text="x\n")
        meta = json.loads((d / "meta.json").read_text())
        assert meta["index"] == 7
        assert meta["seed"] == 999
        assert meta["status"] == "TLE"

    def test_optional_fields_skipped(self, store, src):
        d = store.save_fail(src, 1, 1, "RTE", input_text="in")
        assert not (d / "expected.txt").exists()
        assert not (d / "got.txt").exists()
        assert not (d / "stderr.txt").exists()