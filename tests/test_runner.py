import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "runner"


@pytest.fixture
def run_runner(tmp_path):
    config_dir = tmp_path / "_config"
    data_dir = tmp_path / "_data"
    cache_dir = tmp_path / "_cache"
    for d in (config_dir, data_dir, cache_dir):
        d.mkdir()

    def _run(*args):
        env = os.environ.copy()
        env["CPTOOLS_PLUGIN_NAME"] = "runner"
        env["CPTOOLS_INVOKED_AS"] = "run"
        env["CPTOOLS_PLUGIN_CONFIG_DIR"] = str(config_dir)
        env["CPTOOLS_PLUGIN_DATA_DIR"] = str(data_dir)
        env["CPTOOLS_PLUGIN_CACHE_DIR"] = str(cache_dir)
        env["CPTOOLS_PROTOCOL"] = "1"
        env["CPTOOLS_OUTPUT"] = "human"
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, "main.py", *args],
            cwd=PLUGIN_DIR,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    return _run


@pytest.fixture
def sample_source(tmp_path):
    src = tmp_path / "aplusb.cpp"
    src.write_text(
        "#include <iostream>\n"
        "using namespace std;\n"
        "int main(){int a,b;cin>>a>>b;cout<<a+b<<endl;return 0;}\n",
        encoding="utf-8",
    )
    return src


class TestConfig:
    def test_show(self, run_runner):
        r = run_runner("config", "show")
        assert r.returncode == 0
        cfg = json.loads(r.stdout)
        assert cfg["compiler"] == "g++"
        assert cfg["timeout"] == 5

    def test_set_timeout(self, run_runner):
        r = run_runner("config", "set", "timeout", "10")
        assert r.returncode == 0
        r = run_runner("config", "get", "timeout")
        assert r.stdout.strip() == "10"

    def test_set_flags(self, run_runner):
        r = run_runner("config", "set", "compiler_flags", "-O2 -std=c++20")
        assert r.returncode == 0
        r = run_runner("config", "get", "compiler_flags")
        assert json.loads(r.stdout.strip()) == ["-O2", "-std=c++20"]

    def test_bad_rebuild(self, run_runner):
        r = run_runner("config", "set", "rebuild", "sometimes")
        assert r.returncode == 2

    def test_reset(self, run_runner):
        run_runner("config", "set", "timeout", "99")
        run_runner("config", "reset")
        r = run_runner("config", "get", "timeout")
        assert r.stdout.strip() == "5"


class TestStore:
    def test_add_list_rm(self, run_runner, sample_source, tmp_path):
        inf = tmp_path / "t1.in"
        outf = tmp_path / "t1.out"
        inf.write_text("2 3\n", encoding="utf-8")
        outf.write_text("5\n", encoding="utf-8")

        r = run_runner("test", "add", str(sample_source), str(inf), str(outf))
        assert r.returncode == 0

        r = run_runner("test", "list", str(sample_source))
        assert r.returncode == 0
        assert "input='2 3'" in r.stdout

        r = run_runner("test", "rm", str(sample_source), "1")
        assert r.returncode == 0

        r = run_runner("test", "list", str(sample_source))
        assert "1" not in r.stdout.strip()

    def test_rm_missing(self, run_runner, sample_source):
        r = run_runner("test", "rm", str(sample_source), "99")
        assert r.returncode == 1


class TestMissingSource:
    def test_build_missing(self, run_runner, tmp_path):
        r = run_runner("build", str(tmp_path / "nope.cpp"))
        assert r.returncode == 1


class TestDispatch:
    def test_help(self, run_runner):
        r = run_runner("-h")
        assert r.returncode == 0
        assert "runner" in r.stdout

    def test_unknown(self, run_runner):
        r = run_runner("nonsense")
        assert r.returncode == 2