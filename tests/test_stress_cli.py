import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "stress"
HAS_GXX = shutil.which("g++") is not None


@pytest.fixture
def env(tmp_path):
    cfg = tmp_path / "cfg"
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    for d in (cfg, data, cache):
        d.mkdir()
    e = os.environ.copy()
    e["CPTOOLS_PLUGIN_CONFIG_DIR"] = str(cfg)
    e["CPTOOLS_PLUGIN_DATA_DIR"] = str(data)
    e["CPTOOLS_PLUGIN_CACHE_DIR"] = str(cache)
    e["CPTOOLS_PLUGIN_NAME"] = "stress"
    e["CPTOOLS_INVOKED_AS"] = "stress"
    e["CPTOOLS_PROTOCOL"] = "1"
    e["CPTOOLS_OUTPUT"] = "human"
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def run_stress(env, *args, timeout=60):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=PLUGIN_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


# ---------- C++ fixtures ----------

@pytest.fixture
def gen_cpp(tmp_path):
    f = tmp_path / "gen.cpp"
    f.write_text(
        "#include <iostream>\n"
        "#include <random>\n"
        "using namespace std;\n"
        "int main(int argc, char** argv) {\n"
        "    unsigned seed = argc > 2 ? (unsigned)stoul(argv[2]) : 0u;\n"
        "    mt19937 rng(seed);\n"
        "    cout << (rng() % 10 + 1) << endl;\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def brute_cpp(tmp_path):
    f = tmp_path / "brute.cpp"
    f.write_text(
        "#include <iostream>\n"
        "using namespace std;\n"
        "int main() { int n; cin >> n; cout << n << endl; return 0; }\n",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def sol_good_cpp(tmp_path):
    f = tmp_path / "sol_good.cpp"
    f.write_text(
        "#include <iostream>\n"
        "using namespace std;\n"
        "int main() { int n; cin >> n; cout << n << endl; return 0; }\n",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def sol_bad_cpp(tmp_path):
    f = tmp_path / "sol_bad.cpp"
    f.write_text(
        "#include <iostream>\n"
        "using namespace std;\n"
        "int main() { int n; cin >> n; cout << n + 1 << endl; return 0; }\n",
        encoding="utf-8",
    )
    return f


# ---------- config ----------

class TestConfigCLI:
    def test_show_default(self, env):
        r = run_stress(env, "config", "show")
        assert r.returncode == 0
        cfg = json.loads(r.stdout)
        assert cfg["time_limit"] == 1.0
        assert cfg["compiler"] == "g++"

    def test_set_get(self, env):
        r = run_stress(env, "config", "set", "time_limit", "2.5")
        assert r.returncode == 0
        r = run_stress(env, "config", "get", "time_limit")
        assert r.stdout.strip() == "2.5"

    def test_set_int(self, env):
        run_stress(env, "config", "set", "max_fails", "99")
        r = run_stress(env, "config", "get", "max_fails")
        assert r.stdout.strip() == "99"

    def test_set_bool(self, env):
        run_stress(env, "config", "set", "stop_on_fail", "false")
        r = run_stress(env, "config", "get", "stop_on_fail")
        assert r.stdout.strip() == "False"

    def test_set_bad_float(self, env):
        r = run_stress(env, "config", "set", "time_limit", "abc")
        assert r.returncode == 2

    def test_set_bad_match(self, env):
        r = run_stress(env, "config", "set", "match_mode", "nonsense")
        assert r.returncode == 2

    def test_reset(self, env):
        run_stress(env, "config", "set", "time_limit", "5.0")
        r = run_stress(env, "config", "reset")
        assert r.returncode == 0
        r = run_stress(env, "config", "get", "time_limit")
        assert r.stdout.strip() == "1.0"


# ---------- run: error cases ----------

class TestRunErrors:
    def test_missing_source(self, env, tmp_path, gen_cpp, brute_cpp):
        r = run_stress(
            env, "run", str(tmp_path / "nope.cpp"),
            "--gen", str(gen_cpp), "--brute", str(brute_cpp),
        )
        assert r.returncode == 1
        assert "source not found" in r.stderr

    def test_missing_gen(self, env, tmp_path, sol_good_cpp, brute_cpp):
        r = run_stress(
            env, "run", str(sol_good_cpp),
            "--gen", str(tmp_path / "nope.cpp"), "--brute", str(brute_cpp),
        )
        assert r.returncode == 1

    def test_checker_without_checker_file(self, env, sol_good_cpp, gen_cpp, brute_cpp):
        r = run_stress(
            env, "run", str(sol_good_cpp),
            "--gen", str(gen_cpp), "--brute", str(brute_cpp),
            "-m", "checker",
        )
        assert r.returncode == 2

    def test_no_gen_arg(self, env, sol_good_cpp):
        r = run_stress(env, "run", str(sol_good_cpp))
        assert r.returncode == 2


# ---------- dispatch ----------

class TestDispatch:
    def test_help(self, env):
        r = run_stress(env, "-h")
        assert r.returncode == 0
        assert "stress" in r.stdout

    def test_no_args(self, env):
        r = run_stress(env)
        assert r.returncode == 0

    def test_unknown_command(self, env):
        r = run_stress(env, "nonsense")
        assert r.returncode == 2


# ---------- run: success (bad solution, stops on fail) ----------

@pytest.mark.skipif(not HAS_GXX, reason="g++ not available")
class TestRunBadSolution:
    def test_stops_on_first_fail(
        self, env, gen_cpp, brute_cpp, sol_bad_cpp,
    ):
        r = run_stress(
            env, "run", str(sol_bad_cpp),
            "--gen", str(gen_cpp), "--brute", str(brute_cpp),
            "--max-fails", "1",
        )
        assert r.returncode == 1
        assert "WA" in r.stdout
        assert "1 fails" in r.stdout or "1 fail" in r.stdout


class TestExitCodes:
    def test_missing_source(self, env, tmp_path, gen_cpp, brute_cpp):
        r = run_stress(
            env, "run", str(tmp_path / "nope.cpp"),
            "--gen", str(gen_cpp), "--brute", str(brute_cpp),
        )
        assert r.returncode == 1

    def test_bad_config_rejected(self, env, gen_cpp, brute_cpp, sol_good_cpp):
        # set invalid config: warn_factor > slow_factor
        r = run_stress(env, "config", "set", "warn_factor", "10")
        assert r.returncode == 1
        # running should still detect invalid config? config was saved so
        # subsequent run will refuse
        r = run_stress(
            env, "run", str(sol_good_cpp),
            "--gen", str(gen_cpp), "--brute", str(brute_cpp),
            "--max-fails", "1",
        )
        assert r.returncode == 2
        assert "invalid config" in r.stderr