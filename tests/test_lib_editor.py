import pytest


@pytest.fixture
def fake_which(monkeypatch):
    found = {}

    def _which(name):
        return found.get(name)

    monkeypatch.setattr(cptools_editor.shutil, "which", _which)
    return found


@pytest.fixture
def fake_popen(monkeypatch):
    calls = []

    def _popen(cmd, *args, **kwargs):
        calls.append(cmd)

    monkeypatch.setattr(cptools_editor.subprocess, "Popen", _popen)
    return calls


from cptools.lib import editor as cptools_editor


class TestDetect:
    def test_none_found(self, fake_which, monkeypatch):
        monkeypatch.setattr(cptools_editor.sys, "platform", "linux")
        monkeypatch.setattr(cptools_editor, "_resolve_exe", lambda exe, extra: None)
        result = cptools_editor.detect_editors()
        assert result == {}

    def test_code_and_vim(self, fake_which, monkeypatch):
        monkeypatch.setattr(cptools_editor.sys, "platform", "linux")
        fake_which["code"] = "/usr/bin/code"
        fake_which["vim"] = "/usr/bin/vim"
        result = cptools_editor.detect_editors()
        assert result["vscode"].exe == "/usr/bin/code"
        assert result["vim"].exe == "/usr/bin/vim"

    def test_extra_path_used(self, fake_which, monkeypatch, tmp_path):
        monkeypatch.setattr(cptools_editor.sys, "platform", "linux")
        fake_exe = tmp_path / "codeblocks.exe"
        fake_exe.write_text("")
        monkeypatch.setattr(
            cptools_editor, "KNOWN",
            [("codeblocks", "Code::Blocks", "codeblocks", [str(fake_exe)])],
        )
        result = cptools_editor.detect_editors()
        assert result["codeblocks"].exe == str(fake_exe)


class TestGetEditors:
    def test_user_override(self, fake_which, monkeypatch):
        monkeypatch.setattr(cptools_editor.sys, "platform", "linux")
        fake_which["code"] = "/usr/bin/code"
        result = cptools_editor.get_editors({"vscode": "/custom/code"})
        assert result["vscode"].exe == "/custom/code"

    def test_user_adds_undetected(self, fake_which, monkeypatch):
        monkeypatch.setattr(cptools_editor.sys, "platform", "linux")
        result = cptools_editor.get_editors({"codeblocks": "/usr/bin/cb"})
        assert result["codeblocks"].exe == "/usr/bin/cb"
        assert result["codeblocks"].label == "Code::Blocks"

    def test_empty_override_skipped(self, fake_which, monkeypatch):
        monkeypatch.setattr(cptools_editor, "detect_editors", lambda: {})
        result = cptools_editor.get_editors({"codeblocks": ""})
        assert "codeblocks" not in result


class TestOrderedKeys:
    def test_known_order_preserved(self):
        eds = {
            "vim": cptools_editor.Editor("vim", "Vim", "vim"),
            "codeblocks": cptools_editor.Editor("codeblocks", "Code::Blocks", "cb"),
            "vscode": cptools_editor.Editor("vscode", "VS Code", "code"),
        }
        assert cptools_editor.ordered_keys(eds) == ["codeblocks", "vscode", "vim"]

    def test_extra_keys_at_end(self):
        eds = {
            "vim": cptools_editor.Editor("vim", "Vim", "vim"),
            "custom": cptools_editor.Editor("custom", "custom", "custom"),
            "codeblocks": cptools_editor.Editor("codeblocks", "Code::Blocks", "cb"),
        }
        assert cptools_editor.ordered_keys(eds) == ["codeblocks", "vim", "custom"]


class TestLaunch:
    def test_basic(self, fake_popen, monkeypatch, tmp_path):
        monkeypatch.setattr(cptools_editor.sys, "platform", "linux")
        ed = cptools_editor.Editor("vim", "Vim", "vim")
        f = tmp_path / "a.cpp"
        cptools_editor.launch(ed, f)
        assert fake_popen == [["vim", str(f)]]

    def test_with_args(self, fake_popen, monkeypatch, tmp_path):
        monkeypatch.setattr(cptools_editor.sys, "platform", "linux")
        ed = cptools_editor.Editor("vim", "Vim", "vim", ["-p"])
        f = tmp_path / "a.cpp"
        cptools_editor.launch(ed, f)
        assert fake_popen == [["vim", "-p", str(f)]]

    def test_windows_cmd_wrapper(self, fake_popen, monkeypatch, tmp_path):
        monkeypatch.setattr(cptools_editor.sys, "platform", "win32")
        ed = cptools_editor.Editor("vscode", "VS Code", r"C:\code.CMD")
        f = tmp_path / "a.cpp"
        cptools_editor.launch(ed, f)
        assert fake_popen[0][:2] == ["cmd.exe", "/c"]


class TestKnownEditors:
    def test_contains_expected(self):
        result = cptools_editor.known_editors()
        assert ("codeblocks", "Code::Blocks") in result
        assert ("vscode", "VS Code") in result
        assert ("vim", "Vim") in result
