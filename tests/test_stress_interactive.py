import sys
import threading
import textwrap
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
    for m in ("store", "loop", "interactive"):
        if m in sys.modules:
            del sys.modules[m]
    if str(PLUGIN_DIR) not in sys.path:
        sys.path.insert(0, str(PLUGIN_DIR))


@pytest.fixture
def interactive():
    import importlib
    mod = importlib.import_module("interactive")
    importlib.reload(mod)
    return mod


def _make_solver(tmp_path, name="sol.py", body=None):
    f = tmp_path / name
    if body is None:
        # waits for a line, then echoes back
        body = (
            "import sys\n"
            "line = sys.stdin.readline()\n"
            "print('received:' + line.strip(), flush=True)\n"
        )
    f.write_text(body, encoding="utf-8")
    return f


def _make_interactor(tmp_path, name="inter.py", body=None):
    f = tmp_path / name
    if body is None:
        # reads input file, sends greeting, reads reply, exits ok
        body = (
            "import sys\n"
            "open(sys.argv[1]).read()\n"
            "sys.stdout.write('start\\n')\n"
            "sys.stdout.flush()\n"
            "line = sys.stdin.readline()\n"
            "sys.stdout.write('reply-to-' + line)\n"
            "sys.stdout.flush()\n"
            "sys.exit(0)\n"
        )
    f.write_text(body, encoding="utf-8")
    return f


def _cancel():
    return threading.Event()


class TestBasic:
    def test_ok(self, interactive, tmp_path):
        sol = _make_solver(tmp_path)
        inter = _make_interactor(tmp_path)
        r = interactive.run_interactive(
            [sys.executable, str(sol)],
            [sys.executable, str(inter)],
            "hello\n",
            timeout=10.0,
            cancel_event=_cancel(),
            tracker=set(),
            work_dir=tmp_path / "work",
        )
        assert r["status"] == "OK", r
        assert r["rc"] == 0
        assert r["sol_rc"] == 0
        assert not r["timeout"]
        assert not r["cancelled"]

    def test_wa(self, interactive, tmp_path):
        sol = _make_solver(tmp_path)
        inter = _make_interactor(
            tmp_path,
            body=textwrap.dedent(
                """
                import sys
                open(sys.argv[1]).read()
                sys.stdout.write("start\\n")
                sys.stdout.flush()
                sys.stdin.readline()
                sys.stdout.write("no\\n")
                sys.stdout.flush()
                print("wrong answer", file=sys.stderr)
                sys.exit(1)
                """
            ),
        )
        r = interactive.run_interactive(
            [sys.executable, str(sol)],
            [sys.executable, str(inter)],
            "hello\n",
            timeout=3.0,
            cancel_event=_cancel(),
            tracker=set(),
            work_dir=tmp_path / "work",
        )
        assert r["status"] == "WA", r
        assert r["rc"] == 1
        assert "wrong answer" in r["stderr"]

    def test_solver_crash(self, interactive, tmp_path):
        sol = _make_solver(tmp_path, body="import sys; sys.exit(2)\n")
        inter = _make_interactor(
            tmp_path,
            body=textwrap.dedent(
                """
                import sys
                open(sys.argv[1]).read()
                try:
                    sys.stdin.readline()
                except Exception:
                    pass
                sys.exit(0)
                """
            ),
        )
        r = interactive.run_interactive(
            [sys.executable, str(sol)],
            [sys.executable, str(inter)],
            "hello\n",
            timeout=3.0,
            cancel_event=_cancel(),
            tracker=set(),
            work_dir=tmp_path / "work",
        )
        assert r["status"] == "RTE", r
        assert r["sol_rc"] == 2

    def test_timeout(self, interactive, tmp_path):
        sol = _make_solver(tmp_path, body="import time; time.sleep(30)\n")
        inter = _make_interactor(tmp_path, body="import time; time.sleep(30)\n")
        r = interactive.run_interactive(
            [sys.executable, str(sol)],
            [sys.executable, str(inter)],
            "hello\n",
            timeout=0.5,
            cancel_event=_cancel(),
            tracker=set(),
            work_dir=tmp_path / "work",
        )
        assert r["status"] == "TLE", r
        assert r["timeout"] is True

    def test_cancel(self, interactive, tmp_path):
        sol = _make_solver(tmp_path, body="import time; time.sleep(30)\n")
        inter = _make_interactor(tmp_path, body="import time; time.sleep(30)\n")
        cancel = _cancel()
        cancel.set()
        r = interactive.run_interactive(
            [sys.executable, str(sol)],
            [sys.executable, str(inter)],
            "hello\n",
            timeout=10.0,
            cancel_event=cancel,
            tracker=set(),
            work_dir=tmp_path / "work",
        )
        assert r["status"] == "CANCELLED", r
        assert r["cancelled"] is True


class TestLog:
    def test_log_captured(self, interactive, tmp_path):
        sol = _make_solver(tmp_path)
        inter = _make_interactor(tmp_path)
        r = interactive.run_interactive(
            [sys.executable, str(sol)],
            [sys.executable, str(inter)],
            "hi\n",
            timeout=10.0,
            cancel_event=_cancel(),
            tracker=set(),
            work_dir=tmp_path / "work",
        )
        assert "start" in r["log"]
        assert "received:start" in r["log"]
        assert "reply-to-received" in r["log"]

    def test_work_files_created(self, interactive, tmp_path):
        sol = _make_solver(tmp_path)
        inter = _make_interactor(tmp_path)
        work = tmp_path / "work"
        interactive.run_interactive(
            [sys.executable, str(sol)],
            [sys.executable, str(inter)],
            "hi\n",
            timeout=10.0,
            cancel_event=_cancel(),
            tracker=set(),
            work_dir=work,
        )
        assert (work / "input.txt").is_file()
        assert (work / "output.txt").is_file()
        assert (work / "answer.txt").is_file()


class TestErrors:
    def test_missing_solver(self, interactive, tmp_path):
        inter = _make_interactor(tmp_path)
        r = interactive.run_interactive(
            ["/nonexistent/binary_xyz"],
            [sys.executable, str(inter)],
            "hi\n",
            timeout=10.0,
            cancel_event=_cancel(),
            tracker=set(),
            work_dir=tmp_path / "work",
        )
        assert r["status"] == "RTE"

    def test_missing_interactor(self, interactive, tmp_path):
        sol = _make_solver(tmp_path)
        r = interactive.run_interactive(
            [sys.executable, str(sol)],
            ["/nonexistent/binary_xyz"],
            "hi\n",
            timeout=10.0,
            cancel_event=_cancel(),
            tracker=set(),
            work_dir=tmp_path / "work",
        )
        assert r["status"] == "RTE"