import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from cptools import paths
from cptools.commands import plugin as plugin_cmd


@pytest.fixture
def fake_paths(tmp_path, monkeypatch):
    plugins = tmp_path / "plugins"
    config = tmp_path / "config"
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    builtin = tmp_path / "builtin"
    for d in (plugins, config, data, cache, builtin):
        d.mkdir()

    monkeypatch.setattr(paths, "user_plugins_dir", lambda: plugins)
    monkeypatch.setattr(paths, "builtin_plugins_dir", lambda: builtin)
    monkeypatch.setattr(paths, "plugin_config_dir", lambda n: config / n)
    monkeypatch.setattr(paths, "plugin_data_dir", lambda n: data / n)
    monkeypatch.setattr(paths, "plugin_cache_dir", lambda n: cache / n)

    return {
        "plugins": plugins,
        "config": config,
        "data": data,
        "cache": cache,
        "builtin": builtin,
    }


def make_plugin_src(root: Path, name="demo", version="0.1.0"):
    root.mkdir(parents=True, exist_ok=True)
    (root / "cptools-plugin.toml").write_text(
        f'[plugin]\nname = "{name}"\nversion = "{version}"\n'
        f'exec = ["python", "main.py"]\n\n[commands]\nhi = "Say hi"\n',
        encoding="utf-8",
    )
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    return root


def make_zip(src_dir: Path, zip_path: Path, arc_prefix=""):
    with zipfile.ZipFile(zip_path, "w") as z:
        for f in src_dir.rglob("*"):
            if f.is_file():
                arc = str(Path(arc_prefix) / f.relative_to(src_dir))
                z.write(f, arc)


def make_tar(src_dir: Path, tar_path: Path, arc_prefix=""):
    with tarfile.open(tar_path, "w:gz") as t:
        for f in src_dir.rglob("*"):
            if f.is_file():
                arc = str(Path(arc_prefix) / f.relative_to(src_dir))
                t.add(f, arcname=arc)


class TestInstallFromDir:
    def test_basic(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "src" / "demo")
        rc = plugin_cmd.cmd_install([str(src)])
        assert rc == 0
        target = fake_paths["plugins"] / "demo"
        assert (target / "cptools-plugin.toml").exists()
        assert (target / "main.py").exists()

    def test_renames_to_manifest_name(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "weird-folder-name", name="actual")
        rc = plugin_cmd.cmd_install([str(src)])
        assert rc == 0
        assert (fake_paths["plugins"] / "actual").is_dir()
        assert not (fake_paths["plugins"] / "weird-folder-name").exists()

    def test_force_overwrites(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "src", version="0.1.0")
        plugin_cmd.cmd_install([str(src)])

        src2 = make_plugin_src(tmp_path / "src2", version="0.2.0")
        rc = plugin_cmd.cmd_install([str(src2), "-f"])
        assert rc == 0

        manifest = (fake_paths["plugins"] / "demo" / "cptools-plugin.toml")
        assert '0.2.0' in manifest.read_text(encoding="utf-8")

    def test_prompt_decline_aborts(self, fake_paths, tmp_path, monkeypatch):
        src = make_plugin_src(tmp_path / "src")
        plugin_cmd.cmd_install([str(src)])

        monkeypatch.setattr(
            "cptools.commands.plugin.questionary.confirm",
            lambda *a, **k: type("Q", (), {"ask": lambda self: False})(),
        )
        rc = plugin_cmd.cmd_install([str(src)])
        assert rc == 0

    def test_builtin_collision_allowed(self, fake_paths, tmp_path):
        (fake_paths["builtin"] / "demo").mkdir()
        src = make_plugin_src(tmp_path / "src")
        rc = plugin_cmd.cmd_install([str(src)])
        assert rc == 0
        assert (fake_paths["plugins"] / "demo").is_dir()


class TestInstallFromArchive:
    def test_zip_flat(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "src")
        zip_path = tmp_path / "plugin.zip"
        make_zip(src, zip_path)
        rc = plugin_cmd.cmd_install([str(zip_path)])
        assert rc == 0
        assert (fake_paths["plugins"] / "demo" / "main.py").exists()

    def test_zip_with_prefix(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "src")
        zip_path = tmp_path / "plugin.zip"
        make_zip(src, zip_path, arc_prefix="demo-1.0.0")
        rc = plugin_cmd.cmd_install([str(zip_path)])
        assert rc == 0
        assert (fake_paths["plugins"] / "demo" / "main.py").exists()

    def test_tar_gz(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "src")
        tar_path = tmp_path / "plugin.tar.gz"
        make_tar(src, tar_path, arc_prefix="demo-1.0.0")
        rc = plugin_cmd.cmd_install([str(tar_path)])
        assert rc == 0
        assert (fake_paths["plugins"] / "demo" / "main.py").exists()

    def test_unsupported_format(self, fake_paths, tmp_path):
        bogus = tmp_path / "plugin.xyz"
        bogus.write_text("nope", encoding="utf-8")
        rc = plugin_cmd.cmd_install([str(bogus)])
        assert rc == 1

    def test_no_manifest_in_archive(self, fake_paths, tmp_path):
        d = tmp_path / "src"
        d.mkdir()
        (d / "random.txt").write_text("hi", encoding="utf-8")
        zip_path = tmp_path / "plugin.zip"
        make_zip(d, zip_path)
        rc = plugin_cmd.cmd_install([str(zip_path)])
        assert rc == 1


class TestInstallErrors:
    def test_missing_source(self, fake_paths, tmp_path):
        rc = plugin_cmd.cmd_install([str(tmp_path / "nope")])
        assert rc == 1

    def test_missing_arg(self, fake_paths):
        rc = plugin_cmd.cmd_install([])
        assert rc == 2

    def test_invalid_manifest(self, fake_paths, tmp_path):
        d = tmp_path / "src"
        d.mkdir()
        (d / "cptools-plugin.toml").write_text("not valid toml =", encoding="utf-8")
        rc = plugin_cmd.cmd_install([str(d)])
        assert rc == 1

    def test_zip_slip_rejected(self, fake_paths, tmp_path):
        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("../../../etc/passwd", "pwned")
            z.writestr("cptools-plugin.toml", "[plugin]\nname='x'\nexec=['x']\n")
        rc = plugin_cmd.cmd_install([str(zip_path)])
        assert rc == 1


class TestUninstall:
    def test_basic(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "src")
        plugin_cmd.cmd_install([str(src)])

        rc = plugin_cmd.cmd_uninstall(["demo", "-y"])
        assert rc == 0
        assert not (fake_paths["plugins"] / "demo").exists()

    def test_not_installed(self, fake_paths):
        rc = plugin_cmd.cmd_uninstall(["ghost", "-y"])
        assert rc == 1

    def test_builtin_refused(self, fake_paths):
        (fake_paths["builtin"] / "core").mkdir()
        rc = plugin_cmd.cmd_uninstall(["core", "-y"])
        assert rc == 1

    def test_purge_removes_config_data(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "src")
        plugin_cmd.cmd_install([str(src)])

        (fake_paths["config"] / "demo").mkdir()
        (fake_paths["config"] / "demo" / "settings.json").write_text("{}")
        (fake_paths["data"] / "demo").mkdir()
        (fake_paths["data"] / "demo" / "db.json").write_text("{}")

        rc = plugin_cmd.cmd_uninstall(["demo", "-y", "--purge"])
        assert rc == 0
        assert not (fake_paths["config"] / "demo").exists()
        assert not (fake_paths["data"] / "demo").exists()

    def test_keeps_config_without_purge(self, fake_paths, tmp_path):
        src = make_plugin_src(tmp_path / "src")
        plugin_cmd.cmd_install([str(src)])

        (fake_paths["config"] / "demo").mkdir()
        (fake_paths["config"] / "demo" / "settings.json").write_text("{}")

        rc = plugin_cmd.cmd_uninstall(["demo", "-y"])
        assert rc == 0
        assert (fake_paths["config"] / "demo" / "settings.json").exists()

    def test_prompt_decline_keeps(self, fake_paths, tmp_path, monkeypatch):
        src = make_plugin_src(tmp_path / "src")
        plugin_cmd.cmd_install([str(src)])

        monkeypatch.setattr(
            "cptools.commands.plugin.questionary.confirm",
            lambda *a, **k: type("Q", (), {"ask": lambda self: False})(),
        )
        rc = plugin_cmd.cmd_uninstall(["demo"])
        assert rc == 0
        assert (fake_paths["plugins"] / "demo").exists()

    def test_missing_arg(self, fake_paths):
        rc = plugin_cmd.cmd_uninstall([])
        assert rc == 2


class TestFindPluginDir:
    def test_shallowest_wins(self, tmp_path):
        root = tmp_path / "root"
        (root / "deep" / "nested").mkdir(parents=True)
        (root / "cptools-plugin.toml").write_text("x")
        (root / "deep" / "nested" / "cptools-plugin.toml").write_text("x")
        result = plugin_cmd._find_plugin_dir(root)
        assert result == root

    def test_none_when_missing(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        assert plugin_cmd._find_plugin_dir(root) is None


class TestSafeJoin:
    def test_normal(self, tmp_path):
        result = plugin_cmd._safe_join(tmp_path, "a/b.txt")
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_parent_traversal(self, tmp_path):
        with pytest.raises(ValueError):
            plugin_cmd._safe_join(tmp_path, "../escape.txt")

    def test_deep_traversal(self, tmp_path):
        with pytest.raises(ValueError):
            plugin_cmd._safe_join(tmp_path, "../../etc/passwd")