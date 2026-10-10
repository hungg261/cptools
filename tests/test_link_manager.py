import json

CF_URL = "https://codeforces.com/contest/1923/problem/A"
ATC_URL = "https://atcoder.jp/contests/abc300/tasks/abc300_a"
UNKNOWN_URL = "https://example.com/problem/xyz"


class TestParse:
    def test_valid(self, run_plugin):
        r = run_plugin("parse", CF_URL)
        assert r.returncode == 0
        assert "oj:   codeforces" in r.stdout
        assert "id:   1923A" in r.stdout
        assert CF_URL in r.stdout

    def test_unknown(self, run_plugin):
        r = run_plugin("parse", UNKNOWN_URL)
        assert r.returncode == 1
        assert "unrecognized url" in r.stdout

    def test_missing_arg(self, run_plugin):
        r = run_plugin("parse")
        assert r.returncode == 2

    def test_json(self, run_plugin):
        r = run_plugin("parse", CF_URL, output="json")
        assert r.returncode == 0
        obj = json.loads(r.stdout)
        assert obj["ok"] is True
        assert obj["oj"] == "codeforces"
        assert obj["id"] == "1923A"


class TestNew:
    def test_creates_file(self, run_plugin, plugin_dirs):
        r = run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        files = list(plugin_dirs["work"].iterdir())
        assert len(files) == 1
        assert files[0].name == "1923A.cpp"

    def test_dedup(self, run_plugin, plugin_dirs):
        for _ in range(3):
            r = run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
            assert r.returncode == 0
        names = sorted(f.name for f in plugin_dirs["work"].iterdir())
        assert names == ["1923A.cpp", "1923A_v2.cpp", "1923A_v3.cpp"]

    def test_fills_gap(self, run_plugin, plugin_dirs):
        for _ in range(3):
            run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        (plugin_dirs["work"] / "1923A_v2.cpp").unlink()
        run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        assert (plugin_dirs["work"] / "1923A_v2.cpp").exists()
        assert (plugin_dirs["work"] / "1923A_v3.cpp").exists()
        assert not (plugin_dirs["work"] / "1923A_v4.cpp").exists()

    def test_custom_name(self, run_plugin, plugin_dirs):
        r = run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]), "-n", "myfile")
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "myfile.cpp").exists()

    def test_unknown_url_uses_tail(self, run_plugin, plugin_dirs):
        r = run_plugin("new", UNKNOWN_URL, "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "xyz.cpp").exists()

    def test_unknown_template(self, run_plugin, plugin_dirs):
        r = run_plugin(
            "new", CF_URL, "-d", str(plugin_dirs["work"]), "-t", "nonexistent"
        )
        assert r.returncode == 1
        assert "not found" in r.stderr

    def test_content_has_link(self, run_plugin, plugin_dirs):
        run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        content = (plugin_dirs["work"] / "1923A.cpp").read_text(encoding="utf-8")
        assert CF_URL in content
        assert "1923A" in content

    def test_json_output(self, run_plugin, plugin_dirs):
        r = run_plugin(
            "new", CF_URL, "-d", str(plugin_dirs["work"]), output="json"
        )
        assert r.returncode == 0
        obj = json.loads(r.stdout)
        assert obj["ok"] is True
        assert obj["oj"] == "codeforces"
        assert obj["id"] == "1923A"

    def test_missing_url(self, run_plugin):
        r = run_plugin("new")
        assert r.returncode == 2


class TestList:
    def test_empty(self, run_plugin):
        r = run_plugin("list")
        assert r.returncode == 0
        assert "no problems saved" in r.stdout

    def test_after_new(self, run_plugin, plugin_dirs):
        run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        run_plugin("new", ATC_URL, "-d", str(plugin_dirs["work"]))
        r = run_plugin("list")
        assert r.returncode == 0
        assert "codeforces" in r.stdout
        assert "atcoder" in r.stdout
        assert "1923A" in r.stdout
        assert "abc300_a" in r.stdout

    def test_json(self, run_plugin, plugin_dirs):
        run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        r = run_plugin("list", output="json")
        assert r.returncode == 0
        lines = [line for line in r.stdout.strip().splitlines() if line]
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["type"] == "item"
        assert obj["oj"] == "codeforces"


class TestDir:
    def test_basic(self, run_plugin):
        r = run_plugin("dir", CF_URL)
        assert r.returncode == 0
        assert r.stdout.strip()

    def test_missing_arg(self, run_plugin):
        r = run_plugin("dir")
        assert r.returncode == 2


class TestConfig:
    def test_show_default(self, run_plugin):
        r = run_plugin("config")
        assert r.returncode == 0
        cfg = json.loads(r.stdout)
        assert cfg["default_dir"] == ""
        assert cfg["oj_dirs"] == {}

    def test_set_get(self, run_plugin):
        r = run_plugin("config", "set", "default_dir", "D:/CP")
        assert r.returncode == 0
        r = run_plugin("config", "get", "default_dir")
        assert r.returncode == 0
        assert r.stdout.strip() == "D:/CP"

    def test_set_get_dotted(self, run_plugin):
        r = run_plugin("config", "set", "oj_dirs.codeforces", "D:/CF")
        assert r.returncode == 0
        r = run_plugin("config", "get", "oj_dirs.codeforces")
        assert r.returncode == 0
        assert r.stdout.strip() == "D:/CF"

    def test_unset(self, run_plugin):
        run_plugin("config", "set", "default_dir", "D:/X")
        r = run_plugin("config", "unset", "default_dir")
        assert r.returncode == 0
        r = run_plugin("config", "get", "default_dir")
        assert r.returncode == 0
        assert r.stdout.strip() == ""

    def test_get_missing(self, run_plugin):
        r = run_plugin("config", "get", "oj_dirs.nonexistent")
        assert r.returncode == 1

    def test_set_missing_args(self, run_plugin):
        r = run_plugin("config", "set", "default_dir")
        assert r.returncode == 2


class TestTemplate:
    def test_list_has_cpp_default(self, run_plugin):
        r = run_plugin("template", "list")
        assert r.returncode == 0
        assert "cpp_default" in r.stdout

    def test_show_cpp_default(self, run_plugin):
        r = run_plugin("template", "show", "cpp_default")
        assert r.returncode == 0
        assert "${link}" in r.stdout
        assert "${id}" in r.stdout

    def test_show_unknown(self, run_plugin):
        r = run_plugin("template", "show", "nonexistent")
        assert r.returncode == 1

    def test_add_and_remove(self, run_plugin, tmp_path):
        src = tmp_path / "mytpl.txt"
        src.write_text("custom $id\n", encoding="utf-8")

        r = run_plugin("template", "add", str(src), "mytpl")
        assert r.returncode == 0

        r = run_plugin("template", "list")
        assert "mytpl" in r.stdout

        r = run_plugin("template", "remove", "mytpl")
        assert r.returncode == 0

        r = run_plugin("template", "show", "mytpl")
        assert r.returncode == 1

    def test_add_missing_file(self, run_plugin, tmp_path):
        r = run_plugin("template", "add", str(tmp_path / "nope.py"), "nope")
        assert r.returncode == 1

    def test_remove_nonexistent(self, run_plugin):
        r = run_plugin("template", "remove", "nonexistent")
        assert r.returncode == 1


class TestNewWithTemplate:
    def test_user_template(self, run_plugin, plugin_dirs, tmp_path):
        src = tmp_path / "greet.txt"
        src.write_text("Hello $id\n", encoding="utf-8")
        run_plugin("template", "add", str(src), "greet")

        r = run_plugin(
            "new",
            CF_URL,
            "-t", "greet",
            "-e", ".py",
            "-d", str(plugin_dirs["work"]),
        )
        assert r.returncode == 0
        f = plugin_dirs["work"] / "1923A.py"
        assert f.read_text(encoding="utf-8") == "Hello 1923A\n"

    def test_user_overrides_builtin(self, run_plugin, plugin_dirs, tmp_path):
        src = tmp_path / "cpp_default.txt"
        src.write_text("// custom $id\n", encoding="utf-8")
        run_plugin("template", "add", str(src), "cpp_default")

        r = run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        content = (plugin_dirs["work"] / "1923A.cpp").read_text(encoding="utf-8")
        assert content == "// custom 1923A\n"


class TestOpen:
    def test_unknown_oj(self, run_plugin):
        r = run_plugin("open", "foobar")
        assert r.returncode == 1
        assert "not a URL" in r.stderr

    def test_help(self, run_plugin):
        r = run_plugin("open", "-h")
        assert r.returncode == 0
        assert "usage" in r.stdout


class TestDispatch:
    def test_help(self, run_plugin):
        r = run_plugin("-h")
        assert r.returncode == 0
        assert "link-manager" in r.stdout

    def test_no_args(self, run_plugin):
        r = run_plugin()
        assert r.returncode == 0
        assert "usage" in r.stdout

    def test_unknown_command(self, run_plugin):
        r = run_plugin("nonexistent")
        assert r.returncode == 2
        assert "unknown command" in r.stderr


class TestStore:
    def test_json_structure(self, run_plugin, plugin_dirs):
        run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        store = plugin_dirs["data"] / "problems.json"
        assert store.exists()
        items = json.loads(store.read_text(encoding="utf-8"))
        assert len(items) == 1
        item = items[0]
        assert item["oj"] == "codeforces"
        assert item["id"] == "1923A"
        assert item["link"] == CF_URL
        assert item["path"].endswith("1923A.cpp")

    def test_migrate_old_format(self, run_plugin, plugin_dirs):
        store = plugin_dirs["data"] / "problems.json"
        store.write_text(
            json.dumps([
                {"site": "codeforces", "id": "100A", "url": "https://x", "path": ""}
            ]),
            encoding="utf-8",
        )
        r = run_plugin("list", output="json")
        assert r.returncode == 0
        obj = json.loads(r.stdout.strip())
        assert obj["oj"] == "codeforces"
        assert obj["link"] == "https://x"
        assert "site" not in obj
        assert "url" not in obj

class TestTemplateEscape:
    def test_dollar_dollar_is_literal(self, run_plugin, plugin_dirs, tmp_path):
        src = tmp_path / "lit.txt"
        src.write_text("Literal: $$link\nActual: $id\n", encoding="utf-8")
        run_plugin("template", "add", str(src), "lit")

        r = run_plugin(
            "new", CF_URL, "-t", "lit", "-d", str(plugin_dirs["work"])
        )
        assert r.returncode == 0
        content = (plugin_dirs["work"] / "1923A.cpp").read_text(encoding="utf-8")
        assert content == "Literal: $link\nActual: 1923A\n"

    def test_unknown_var_kept(self, run_plugin, plugin_dirs, tmp_path):
        src = tmp_path / "unk.txt"
        src.write_text("keep $unknown here\n", encoding="utf-8")
        run_plugin("template", "add", str(src), "unk")

        r = run_plugin(
            "new", CF_URL, "-t", "unk", "-d", str(plugin_dirs["work"])
        )
        assert r.returncode == 0
        content = (plugin_dirs["work"] / "1923A.cpp").read_text(encoding="utf-8")
        assert content == "keep $unknown here\n"

    def test_braced_form(self, run_plugin, plugin_dirs, tmp_path):
        src = tmp_path / "br.txt"
        src.write_text("${id}suffix\n", encoding="utf-8")
        run_plugin("template", "add", str(src), "br")

        r = run_plugin(
            "new", CF_URL, "-t", "br", "-d", str(plugin_dirs["work"])
        )
        assert r.returncode == 0
        content = (plugin_dirs["work"] / "1923A.cpp").read_text(encoding="utf-8")
        assert content == "1923Asuffix\n"

class TestExt:
    def test_default_ext(self, run_plugin, plugin_dirs):
        r = run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "1923A.cpp").exists()

    def test_flag_ext(self, run_plugin, plugin_dirs):
        r = run_plugin(
            "new", CF_URL, "-e", ".py", "-d", str(plugin_dirs["work"])
        )
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "1923A.py").exists()

    def test_ext_without_dot(self, run_plugin, plugin_dirs):
        r = run_plugin(
            "new", CF_URL, "-e", "rs", "-d", str(plugin_dirs["work"])
        )
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "1923A.rs").exists()

    def test_config_default_ext(self, run_plugin, plugin_dirs):
        run_plugin("config", "set", "default_ext", ".py")
        r = run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "1923A.py").exists()

    def test_flag_overrides_config(self, run_plugin, plugin_dirs):
        run_plugin("config", "set", "default_ext", ".py")
        r = run_plugin(
            "new", CF_URL, "-e", ".rs", "-d", str(plugin_dirs["work"])
        )
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "1923A.rs").exists()

class TestConfigReset:
    def test_reset_all_with_y(self, run_plugin):
        run_plugin("config", "set", "default_dir", "D:/X")
        run_plugin("config", "set", "default_ext", ".py")
        r = run_plugin("config", "reset", "-y")
        assert r.returncode == 0
        assert "reset" in r.stdout

        r = run_plugin("config")
        cfg = json.loads(r.stdout)
        assert cfg["default_dir"] == ""
        assert cfg["default_ext"] == ".cpp"

    def test_reset_all_prompt_yes(self, run_plugin):
        run_plugin("config", "set", "default_dir", "D:/X")
        r = run_plugin("config", "reset", input="y\n")
        assert r.returncode == 0
        r = run_plugin("config", "get", "default_dir")
        assert r.stdout.strip() == ""

    def test_reset_all_prompt_abort(self, run_plugin):
        run_plugin("config", "set", "default_dir", "D:/X")
        r = run_plugin("config", "reset", input="n\n")
        assert r.returncode == 0
        assert "aborted" in r.stdout
        r = run_plugin("config", "get", "default_dir")
        assert r.stdout.strip() == "D:/X"

    def test_reset_single_key(self, run_plugin):
        run_plugin("config", "set", "default_dir", "D:/X")
        run_plugin("config", "set", "default_ext", ".py")
        r = run_plugin("config", "reset", "default_dir")
        assert r.returncode == 0
        r = run_plugin("config", "get", "default_dir")
        assert r.stdout.strip() == ""
        r = run_plugin("config", "get", "default_ext")
        assert r.stdout.strip() == ".py"

    def test_reset_oj_dir(self, run_plugin):
        run_plugin("config", "set", "oj_dirs.codeforces", "D:/CF")
        r = run_plugin("config", "reset", "oj_dirs.codeforces")
        assert r.returncode == 0
        r = run_plugin("config", "get", "oj_dirs.codeforces")
        assert r.returncode == 1

    def test_reset_unknown_key(self, run_plugin):
        r = run_plugin("config", "reset", "nonexistent_key")
        assert r.returncode == 0

    def test_reset_all_clears_oj_dirs(self, run_plugin):
        run_plugin("config", "set", "oj_dirs.codeforces", "D:/CF")
        run_plugin("config", "set", "oj_dirs.atcoder", "D:/ATC")
        run_plugin("config", "reset", "-y")
        r = run_plugin("config")
        cfg = json.loads(r.stdout)
        assert cfg["oj_dirs"] == {}

class TestShortcut:
    def test_url_as_first_arg(self, run_plugin, plugin_dirs):
        r = run_plugin(CF_URL, "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "1923A.cpp").exists()

    def test_url_with_template(self, run_plugin, plugin_dirs):
        r = run_plugin(CF_URL, "-t", "cpp_default", "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "1923A.cpp").exists()

    def test_unknown_url_tail_used(self, run_plugin, plugin_dirs):
        r = run_plugin("https://example.com/problem/xyz", "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "xyz.cpp").exists()

    def test_non_url_unknown_command(self, run_plugin):
        r = run_plugin("foobar")
        assert r.returncode == 2
        assert "unknown command" in r.stderr


class TestConfigMigration:
    def test_old_cpp_migrates_to_cpp_default(self, run_plugin, plugin_dirs):
        cfg_file = plugin_dirs["config"] / "config.json"
        cfg_file.write_text(
            json.dumps({
                "default_dir": "",
                "fallback_dir": "",
                "oj_dirs": {},
                "default_template": "cpp",
                "default_ext": ".cpp",
            }),
            encoding="utf-8",
        )
        r = run_plugin("new", CF_URL, "-d", str(plugin_dirs["work"]))
        assert r.returncode == 0
        assert (plugin_dirs["work"] / "1923A.cpp").exists()

        r = run_plugin("config")
        cfg = json.loads(r.stdout)
        assert cfg["default_template"] == "cpp_default"