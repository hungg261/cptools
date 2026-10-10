import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "link-manager"
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from oj import parse, oj_names, Codeforces, AtCoder  # noqa: E402


class TestCodeforces:
    def test_contest_url(self):
        obj = parse("https://codeforces.com/contest/1923/problem/A")
        assert obj is not None
        assert obj.name == "codeforces"
        assert obj.id == "1923A"

    def test_problemset_url(self):
        obj = parse("https://codeforces.com/problemset/problem/1923/A")
        assert obj is not None
        assert obj.id == "1923A"

    def test_gym_url(self):
        obj = parse("https://codeforces.com/gym/123456/problem/B")
        assert obj is not None
        assert obj.id == "123456B"

    def test_trailing_slash(self):
        obj = parse("https://codeforces.com/contest/1923/problem/A/")
        assert obj is not None
        assert obj.id == "1923A"

    def test_subproblem(self):
        obj = parse("https://codeforces.com/contest/1923/problem/A1")
        assert obj is not None
        assert obj.id == "1923A1"


class TestAtCoder:
    def test_basic(self):
        obj = parse("https://atcoder.jp/contests/abc300/tasks/abc300_a")
        assert obj is not None
        assert obj.name == "atcoder"
        assert obj.id == "abc300_a"


class TestEdgeCases:
    def test_unknown_url(self):
        assert parse("https://example.com/problem/x") is None

    def test_empty_string(self):
        assert parse("") is None

    def test_oj_names(self):
        names = oj_names()
        assert "codeforces" in names
        assert "atcoder" in names


class TestDirectClass:
    def test_codeforces_class(self):
        obj = Codeforces.try_parse("https://codeforces.com/contest/100/problem/Z")
        assert obj.id == "100Z"

    def test_atcoder_class(self):
        obj = AtCoder.try_parse("https://atcoder.jp/contests/abc001/tasks/abc001_a")
        assert obj.id == "abc001_a"