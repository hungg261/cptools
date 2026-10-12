from cptools.lib import clipboard


def test_returns_bool():
    r = clipboard.copy("test content")
    assert isinstance(r, bool)


def test_empty_string():
    r = clipboard.copy("")
    assert isinstance(r, bool)


def test_none():
    r = clipboard.copy(None)
    assert isinstance(r, bool)


def test_non_string():
    r = clipboard.copy(12345)
    assert isinstance(r, bool)