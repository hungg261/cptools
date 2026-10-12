import sys
import threading
import time
from pathlib import Path

import pytest

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
    if "store" in sys.modules:
        del sys.modules["store"]
    if "loop" in sys.modules:
        del sys.modules["loop"]
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.insert(0, str(PLUGIN_DIR))


@pytest.fixture
def loop():
    import importlib
    import store
    import loop as loop_mod
    importlib.reload(store)
    importlib.reload(loop_mod)
    return loop_mod


class TestClassify:
    def test_ok(self, loop):
        assert loop._classify(0.5, 1.0, 1.0, 2.0, 3.0) == "OK"
        assert loop._classify(0.99, 1.0, 1.0, 2.0, 3.0) == "OK"

    def test_warn(self, loop):
        assert loop._classify(1.0, 1.0, 1.0, 2.0, 3.0) == "WARN"
        assert loop._classify(1.5, 1.0, 1.0, 2.0, 3.0) == "WARN"
        assert loop._classify(1.99, 1.0, 1.0, 2.0, 3.0) == "WARN"

    def test_slow(self, loop):
        assert loop._classify(2.0, 1.0, 1.0, 2.0, 3.0) == "SLOW"
        assert loop._classify(2.9, 1.0, 1.0, 2.0, 3.0) == "SLOW"

    def test_tle(self, loop):
        assert loop._classify(3.0, 1.0, 1.0, 2.0, 3.0) == "TLE"
        assert loop._classify(10.0, 1.0, 1.0, 2.0, 3.0) == "TLE"

    def test_custom_tl(self, loop):
        assert loop._classify(0.5, 2.0, 1.0, 2.0, 3.0) == "OK"
        assert loop._classify(2.0, 2.0, 1.0, 2.0, 3.0) == "WARN"

    def test_custom_factors(self, loop):
        assert loop._classify(1.5, 1.0, 2.0, 3.0, 4.0) == "OK"
        assert loop._classify(2.5, 1.0, 2.0, 3.0, 4.0) == "WARN"
        assert loop._classify(3.5, 1.0, 2.0, 3.0, 4.0) == "SLOW"


class TestCompare:
    def test_exact_match(self, loop):
        assert loop._compare("1 2 3\n", "1 2 3\n", "exact") is True

    def test_exact_trailing_ws(self, loop):
        assert loop._compare("1 2 3\n", "1 2 3", "exact") is True

    def test_exact_different(self, loop):
        assert loop._compare("1 2 3\n", "1 2 4\n", "exact") is False

    def test_token_match(self, loop):
        assert loop._compare("1\n2\n3\n", "1 2 3", "token") is True
        assert loop._compare("1   2   3", "1 2 3", "token") is True

    def test_token_different(self, loop):
        assert loop._compare("1 2 3", "1 2", "token") is False
        assert loop._compare("1 2 3", "1 2 4", "token") is False

    def test_whitespace(self, loop):
        assert loop._compare("1  2\n\n3\n", "1 2 3", "whitespace") is True
        assert loop._compare("1 2 3", "1  2  3", "whitespace") is True


class TestRunProc:
    def test_simple_output(self, loop):
        tracker = set()
        cancel = threading.Event()
        r = loop._run_proc(
            [sys.executable, "-c", "print('hello')"],
            stdin_bytes=None,
            timeout=5.0,
            cancel_event=cancel,
            tracker=tracker,
            cwd=Path.cwd(),
        )
        assert r["rc"] == 0
        assert r["stdout"].strip() == "hello"
        assert not r["timeout"]
        assert not r["cancelled"]
        assert tracker == set()

    def test_stdin(self, loop):
        tracker = set()
        cancel = threading.Event()
        code = "import sys; print(sys.stdin.read().strip().upper())"
        r = loop._run_proc(
            [sys.executable, "-c", code],
            stdin_bytes=b"hello world",
            timeout=5.0,
            cancel_event=cancel,
            tracker=tracker,
            cwd=Path.cwd(),
        )
        assert r["rc"] == 0
        assert r["stdout"].strip() == "HELLO WORLD"

    def test_nonzero_rc(self, loop):
        tracker = set()
        cancel = threading.Event()
        r = loop._run_proc(
            [sys.executable, "-c", "import sys; sys.exit(3)"],
            stdin_bytes=None,
            timeout=5.0,
            cancel_event=cancel,
            tracker=tracker,
            cwd=Path.cwd(),
        )
        assert r["rc"] == 3

    def test_timeout(self, loop):
        tracker = set()
        cancel = threading.Event()
        r = loop._run_proc(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdin_bytes=None,
            timeout=0.3,
            cancel_event=cancel,
            tracker=tracker,
            cwd=Path.cwd(),
        )
        assert r["timeout"] is True
        assert r["rc"] is None

    def test_cancel(self, loop):
        tracker = set()
        cancel = threading.Event()
        cancel.set()
        r = loop._run_proc(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdin_bytes=None,
            timeout=5.0,
            cancel_event=cancel,
            tracker=tracker,
            cwd=Path.cwd(),
        )
        assert r["cancelled"] is True

    def test_missing_command(self, loop):
        tracker = set()
        cancel = threading.Event()
        r = loop._run_proc(
            ["/nonexistent/binary_xyz"],
            stdin_bytes=None,
            timeout=1.0,
            cancel_event=cancel,
            tracker=tracker,
            cwd=Path.cwd(),
        )
        assert r.get("error") is True
        assert r["rc"] is None