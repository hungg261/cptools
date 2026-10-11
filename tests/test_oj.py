import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).parent.parent / "cptools" / "builtin" / "link-manager"
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from oj import parse, oj_names  # noqa: E402


COMMON_CASES = [
    # (url, oj_name, expected_id)
    ("https://codeforces.com/contest/1923/problem/A", "codeforces", "1923A"),
    ("http://codeforces.com/contest/1923/problem/A", "codeforces", "1923A"),
    ("https://codeforces.com/contest/1923/problem/A/", "codeforces", "1923A"),
    ("https://codeforces.com/problemset/problem/1923/A", "codeforces", "1923A"),
    ("https://codeforces.com/gym/123456/problem/B", "codeforces", "Gym_123456B"),
    ("https://codeforces.com/group/abc123/contest/100/problem/C", "codeforces", "Group_abc123_100C"),
    ("https://atcoder.jp/contests/abc300/tasks/abc300_a", "atcoder", "abc300_a"),
    ("https://atcoder.jp/contests/abc300/tasks/abc300_a/", "atcoder", "abc300_a"),
    ("https://www.codechef.com/problems/FLOW001", "codechef", "FLOW001"),
    ("https://codechef.com/problems/HELLO_WORLD", "codechef", "HELLO_WORLD"),
    ("https://cses.fi/problemset/task/1068", "cses", "1068"),
    ("https://open.kattis.com/problems/fizzbuzz", "kattis", "fizzbuzz"),
    ("https://open.kattis.com/problems/some-problem/", "kattis", "some-problem"),
    ("https://leetcode.com/problems/two-sum", "leetcode", "two-sum"),
    ("https://leetcode.com/problems/two-sum/", "leetcode", "two-sum"),
    ("https://leetcode.com/problems/two-sum/description/", "leetcode", "two-sum"),
    ("https://lqdoj.edu.vn/problem/abc123", "lqdoj", "abc123"),
    ("https://marisaoj.com/problem/123", "marisaoj", "123"),
    ("https://nloj.org/problems/42", "nloj", "42"),
    ("https://oj.uz/problem/view/ioi15_boxes", "ojuz", "ioi15_boxes"),
    ("https://www.spoj.com/problems/TEST/", "spoj", "TEST"),
    ("https://spoj.com/problems/FCTRL", "spoj", "FCTRL"),
    ("https://oj.vnoi.info/problem/nktick", "vnoj", "nktick"),
    ("https://judge.yosupo.jp/problem/aplusb", "yosupo", "aplusb"),
    ("https://judge.yosupo.jp/problem/static_range_sum", "yosupo", "static_range_sum"),
    ("https://www.acmicpc.net/problem/1000", "baekjoon", "1000"),
    ("https://boj.kr/problem/1000", "baekjoon", "1000"),
    ("https://dmoj.ca/problem/aplusb", "dmoj", "aplusb"),
    ("https://www.hackerrank.com/challenges/solve-me-first", "hackerrank", "solve-me-first"),
    ("https://www.hackerearth.com/problem/algorithm/hello-world", "hackerearth", "hello-world"),
    ("https://onlinejudge.org/index.php?option=com_onlinejudge&Itemid=8&page=show_problem&problem=100", "uva", "100"),
    ("https://onlinejudge.org/problem/100", "uva", "100"),
    ("https://acm.timus.ru/problem.aspx?space=1&num=1000", "timus", "1000"),
    ("https://acm.timus.ru/problem.aspx?num=1000", "timus", "1000"),
    ("https://onlinejudge.u-aizu.ac.jp/problems/0000", "aizu", "0000"),
    ("https://judge.u-aizu.ac.jp/onlinejudge/review.jsp?id=12345", "aizu", "12345"),
    ("http://poj.org/problem?id=1000", "poj", "1000"),
    ("https://eolymp.com/problems/1", "eolymp", "1"),
    ("https://lightoj.com/problem/discovering-permutations", "lightoj", "discovering-permutations"),
    ("https://toph.co/problem/hello-world", "toph", "hello-world"),
]


@pytest.mark.parametrize("url, oj_name, expected_id", COMMON_CASES)
def test_parse_common(url, oj_name, expected_id):
    obj = parse(url)
    assert obj is not None, f"failed to parse: {url}"
    assert obj.name == oj_name, f"wrong oj for {url}: {obj.name} != {oj_name}"
    assert obj.id == expected_id, f"wrong id for {url}: {obj.id} != {expected_id}"


class TestEdgeCases:
    def test_unknown_url(self):
        assert parse("https://example.com/problem/x") is None

    def test_empty_string(self):
        assert parse("") is None

    def test_whitespace_stripped(self):
        obj = parse("  https://codeforces.com/contest/1923/problem/A  ")
        assert obj is not None
        assert obj.id == "1923A"

    def test_fragment_stripped(self):
        obj = parse("https://codeforces.com/contest/1923/problem/A#section")
        assert obj is not None
        assert obj.id == "1923A"


class TestOjNames:
    def test_all_expected_present(self):
        names = oj_names()
        expected = {
            "codeforces", "atcoder", "codechef", "cses", "kattis",
            "leetcode", "lqdoj", "marisaoj", "nloj", "ojuz", "spoj",
            "vnoj", "yosupo", "baekjoon", "dmoj", "hackerrank",
            "hackerearth", "uva", "timus", "aizu", "poj", "eolymp",
            "lightoj", "toph",
        }
        assert expected.issubset(set(names))

    def test_no_duplicates(self):
        names = oj_names()
        assert len(names) == len(set(names))


class TestCodeforcesVariants:
    def test_contest(self):
        obj = parse("https://codeforces.com/contest/100/problem/A1")
        assert obj.id == "100A1"

    def test_group(self):
        obj = parse("https://codeforces.com/group/xyz/contest/50/problem/B")
        assert obj.id == "Group_xyz_50B"

    def test_gym(self):
        obj = parse("https://codeforces.com/gym/999999/problem/Z")
        assert obj.id == "Gym_999999Z"

    def test_problemset(self):
        obj = parse("https://codeforces.com/problemset/problem/4/A")
        assert obj.id == "4A"


class TestAtCoderVariants:
    def test_abc(self):
        obj = parse("https://atcoder.jp/contests/abc001/tasks/abc001_a")
        assert obj.id == "abc001_a"

    def test_arc(self):
        obj = parse("https://atcoder.jp/contests/arc100/tasks/arc100_a")
        assert obj.id == "arc100_a"

class TestCustomOJ:
    def test_make_basic(self):
        from oj import make_custom_oj
        cls = make_custom_oj("myoj", [r"myoj\.com/p/(?P<pid>[A-Z0-9]+)"])
        obj = cls.try_parse("https://myoj.com/p/ABC123")
        assert obj is not None
        assert obj.id == "ABC123"

    def test_id_template(self):
        from oj import make_custom_oj
        cls = make_custom_oj(
            "myoj",
            [r"myoj\.com/c/(?P<cid>\d+)/p/(?P<pid>[A-Z]+)"],
            id_template="{cid}{pid}",
        )
        obj = cls.try_parse("https://myoj.com/c/100/p/A")
        assert obj.id == "100A"

    def test_parse_with_custom(self):
        from oj import make_custom_oj, parse
        cls = make_custom_oj("myoj", [r"myoj\.com/p/(?P<pid>\d+)"])
        obj = parse("https://myoj.com/p/42", [cls])
        assert obj.name == "myoj"
        assert obj.id == "42"

    def test_builtin_wins_first(self):
        from oj import parse, BUILTIN_OJS
        obj = parse("https://codeforces.com/contest/1/problem/A")
        assert obj.name == "codeforces"

    def test_invalid_name(self):
        from oj import make_custom_oj
        import pytest
        with pytest.raises(ValueError):
            make_custom_oj("Bad Name", [r"x\.com/(?P<pid>\d+)"])

    def test_duplicate_builtin_name(self):
        from oj import make_custom_oj
        import pytest
        with pytest.raises(ValueError, match="builtin"):
            make_custom_oj("codeforces", [r"x\.com/(?P<pid>\d+)"])

    def test_invalid_regex(self):
        from oj import make_custom_oj
        import pytest
        with pytest.raises(ValueError, match="invalid regex"):
            make_custom_oj("myoj", ["([unclosed"])

    def test_missing_pid(self):
        from oj import make_custom_oj
        import pytest
        with pytest.raises(ValueError, match="pid"):
            make_custom_oj("myoj", [r"x\.com/(?P<other>\d+)"])

    def test_bad_id_template(self):
        from oj import make_custom_oj
        import pytest
        with pytest.raises(ValueError, match="unknown group"):
            make_custom_oj(
                "myoj",
                [r"x\.com/(?P<pid>\d+)"],
                id_template="{nope}",
            )