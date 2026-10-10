import pytest

from cptools.lib import open as cptools_open


@pytest.fixture
def fake_popen(monkeypatch):
    calls = []

    def _popen(cmd, *args, **kwargs):
        calls.append(cmd)
        return None

    monkeypatch.setattr(cptools_open.subprocess, "Popen", _popen)
    return calls


@pytest.fixture
def fake_startfile(monkeypatch):
    calls = []

    def _startfile(path):
        calls.append(path)

    monkeypatch.setattr(cptools_open.os, "startfile", _startfile, raising=False)
    return calls


@pytest.fixture
def fake_which(monkeypatch):
    found = {}

    def _which(name):
        return found.get(name)

    monkeypatch.setattr(cptools_open.shutil, "which", _which)
    return found


class TestOpenFile:
    def test_windows(self, monkeypatch, fake_startfile, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "win32")
        f = tmp_path / "a.cpp"
        cptools_open.open_file(f)
        assert fake_startfile == [str(f)]

    def test_mac(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "darwin")
        f = tmp_path / "a.cpp"
        cptools_open.open_file(f)
        assert fake_popen == [["open", str(f)]]

    def test_linux(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "linux")
        f = tmp_path / "a.cpp"
        cptools_open.open_file(f)
        assert fake_popen == [["xdg-open", str(f)]]


class TestOpenFolder:
    def test_windows(self, monkeypatch, fake_startfile, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "win32")
        cptools_open.open_folder(tmp_path)
        assert fake_startfile == [str(tmp_path)]

    def test_mac(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "darwin")
        cptools_open.open_folder(tmp_path)
        assert fake_popen == [["open", str(tmp_path)]]

    def test_linux(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "linux")
        cptools_open.open_folder(tmp_path)
        assert fake_popen == [["xdg-open", str(tmp_path)]]


class TestRevealFile:
    def test_windows(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "win32")
        f = tmp_path / "a.cpp"
        f.write_text("x")
        cptools_open.reveal_file(f)
        assert fake_popen == [["explorer", "/select,", str(f.resolve())]]

    def test_mac(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "darwin")
        f = tmp_path / "a.cpp"
        f.write_text("x")
        cptools_open.reveal_file(f)
        assert fake_popen == [["open", "-R", str(f.resolve())]]

    def test_linux_nautilus(self, monkeypatch, fake_popen, fake_which, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "linux")
        fake_which["nautilus"] = "/usr/bin/nautilus"
        f = tmp_path / "a.cpp"
        f.write_text("x")
        cptools_open.reveal_file(f)
        assert fake_popen == [["nautilus", "--select", str(f.resolve())]]

    def test_linux_dolphin(self, monkeypatch, fake_popen, fake_which, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "linux")
        fake_which["dolphin"] = "/usr/bin/dolphin"
        f = tmp_path / "a.cpp"
        f.write_text("x")
        cptools_open.reveal_file(f)
        assert fake_popen == [["dolphin", "--select", str(f.resolve())]]

    def test_linux_thunar(self, monkeypatch, fake_popen, fake_which, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "linux")
        fake_which["thunar"] = "/usr/bin/thunar"
        f = tmp_path / "a.cpp"
        f.write_text("x")
        cptools_open.reveal_file(f)
        assert fake_popen == [["thunar", str(f.resolve().parent)]]

    def test_linux_fallback(self, monkeypatch, fake_popen, fake_which, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "linux")
        f = tmp_path / "a.cpp"
        f.write_text("x")
        cptools_open.reveal_file(f)
        assert fake_popen == [["xdg-open", str(f.resolve().parent)]]


class TestOpenWith:
    def test_basic(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "linux")
        f = tmp_path / "a.cpp"
        cptools_open.open_with(f, "/usr/bin/code")
        assert fake_popen == [["/usr/bin/code", str(f)]]

    def test_with_args(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "linux")
        f = tmp_path / "a.cpp"
        cptools_open.open_with(f, "vim", ["-p"])
        assert fake_popen == [["vim", "-p", str(f)]]

    def test_windows_cmd_wrapper(self, monkeypatch, fake_popen, tmp_path):
        monkeypatch.setattr(cptools_open.sys, "platform", "win32")
        f = tmp_path / "a.cpp"
        cptools_open.open_with(f, r"C:\tools\code.CMD")
        assert fake_popen[0][:2] == ["cmd.exe", "/c"]