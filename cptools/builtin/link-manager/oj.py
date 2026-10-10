import re


class BaseOJ:
    name = ""
    patterns = []

    def __init__(self, link):
        self.link = link
        self.id = None

    @classmethod
    def try_parse(cls, link):
        link = link.strip().rstrip("/#")
        for pat in cls.patterns:
            m = pat.search(link)
            if m:
                obj = cls(link)
                obj.id = obj.build_id(m)
                return obj
        return None

    def build_id(self, m):
        return m.group("pid")

    def __repr__(self):
        return f"{self.name}:{self.id}"


class Codeforces(BaseOJ):
    name = "codeforces"
    patterns = [
        re.compile(r"codeforces\.com/group/(?P<group>[A-Za-z0-9]+)/contest/(?P<cid>\d+)/problem/(?P<pid>[A-Za-z0-9]+)"),
        re.compile(r"codeforces\.com/contest/(?P<cid>\d+)/problem/(?P<pid>[A-Za-z0-9]+)"),
        re.compile(r"codeforces\.com/problemset/problem/(?P<cid>\d+)/(?P<pid>[A-Za-z0-9]+)"),
        re.compile(r"codeforces\.com/gym/(?P<cid>\d+)/problem/(?P<pid>[A-Za-z0-9]+)"),
    ]

    def build_id(self, m):
        cid = m.group("cid")
        pid = m.group("pid")
        group = m.groupdict().get("group")
        if group:
            return f"Group_{group}_{cid}{pid}"
        if "/gym/" in self.link:
            return f"Gym_{cid}{pid}"
        return cid + pid


class AtCoder(BaseOJ):
    name = "atcoder"
    patterns = [
        re.compile(r"atcoder\.jp/contests/(?P<contest>[^/]+)/tasks/(?P<pid>[A-Za-z0-9_]+)"),
    ]


class CodeChef(BaseOJ):
    name = "codechef"
    patterns = [
        re.compile(r"codechef\.com/problems/(?P<pid>[A-Z0-9_]+)"),
    ]


class CSES(BaseOJ):
    name = "cses"
    patterns = [
        re.compile(r"cses\.fi/problemset/task/(?P<pid>[0-9]+)"),
    ]


class Kattis(BaseOJ):
    name = "kattis"
    patterns = [
        re.compile(r"open\.kattis\.com/problems/(?P<pid>[A-Za-z0-9\-]+)"),
    ]


class LeetCode(BaseOJ):
    name = "leetcode"
    patterns = [
        re.compile(r"leetcode\.com/problems/(?P<pid>[A-Za-z0-9\-]+)"),
    ]


class LQDOJ(BaseOJ):
    name = "lqdoj"
    patterns = [
        re.compile(r"lqdoj\.edu\.vn/problem/(?P<pid>[A-Za-z0-9_]+)"),
    ]


class MarisaOJ(BaseOJ):
    name = "marisaoj"
    patterns = [
        re.compile(r"marisaoj\.com/problem/(?P<pid>[0-9]+)"),
    ]


class NLOJ(BaseOJ):
    name = "nloj"
    patterns = [
        re.compile(r"nloj\.org/problems/(?P<pid>[0-9]+)"),
    ]


class ojuz(BaseOJ):
    name = "ojuz"
    patterns = [
        re.compile(r"oj\.uz/problem/view/(?P<pid>[A-Za-z0-9_]+)"),
    ]


class SPOJ(BaseOJ):
    name = "spoj"
    patterns = [
        re.compile(r"spoj\.com/problems/(?P<pid>[A-Za-z0-9_]+)"),
    ]


class VNOJ(BaseOJ):
    name = "vnoj"
    patterns = [
        re.compile(r"oj\.vnoi\.info/problem/(?P<pid>[A-Za-z0-9_]+)"),
    ]


class Yosupo(BaseOJ):
    name = "yosupo"
    patterns = [
        re.compile(r"judge\.yosupo\.jp/problem/(?P<pid>[A-Za-z0-9_]+)"),
    ]


class Baekjoon(BaseOJ):
    name = "baekjoon"
    patterns = [
        re.compile(r"acmicpc\.net/problem/(?P<pid>\d+)"),
        re.compile(r"boj\.kr/problem/(?P<pid>\d+)"),
    ]


class DMOJ(BaseOJ):
    name = "dmoj"
    patterns = [
        re.compile(r"dmoj\.ca/problem/(?P<pid>[A-Za-z0-9_]+)"),
    ]


class HackerRank(BaseOJ):
    name = "hackerrank"
    patterns = [
        re.compile(r"hackerrank\.com/challenges/(?P<pid>[A-Za-z0-9\-]+)"),
    ]


class HackerEarth(BaseOJ):
    name = "hackerearth"
    patterns = [
        re.compile(r"hackerearth\.com/problem/algorithm/(?P<pid>[A-Za-z0-9\-]+)"),
    ]


class UVa(BaseOJ):
    name = "uva"
    patterns = [
        re.compile(r"onlinejudge\.org/index\.php\?.*?problem=(?P<pid>\d+)"),
        re.compile(r"onlinejudge\.org/problem/(?P<pid>\d+)"),
    ]


class Timus(BaseOJ):
    name = "timus"
    patterns = [
        re.compile(r"acm\.timus\.ru/problem\.aspx\?(?:.*?&)?num=(?P<pid>\d+)"),
    ]


class Aizu(BaseOJ):
    name = "aizu"
    patterns = [
        re.compile(r"onlinejudge\.u-aizu\.ac\.jp/problems/(?P<pid>[A-Za-z0-9_]+)"),
        re.compile(r"judge\.u-aizu\.ac\.jp/onlinejudge/review\.jsp\?id=(?P<pid>\d+)"),
    ]


class POJ(BaseOJ):
    name = "poj"
    patterns = [
        re.compile(r"poj\.org/problem\?id=(?P<pid>\d+)"),
    ]


class Eolymp(BaseOJ):
    name = "eolymp"
    patterns = [
        re.compile(r"eolymp\.com/problems/(?P<pid>\d+)"),
    ]


class LightOJ(BaseOJ):
    name = "lightoj"
    patterns = [
        re.compile(r"lightoj\.com/problem/(?P<pid>[A-Za-z0-9\-]+)"),
    ]


class Toph(BaseOJ):
    name = "toph"
    patterns = [
        re.compile(r"toph\.co/problem/(?P<pid>[A-Za-z0-9\-]+)"),
    ]


OJS = [
    Codeforces,
    AtCoder,
    CodeChef,
    CSES,
    Kattis,
    LeetCode,
    LQDOJ,
    MarisaOJ,
    NLOJ,
    ojuz,
    SPOJ,
    VNOJ,
    Yosupo,
    Baekjoon,
    DMOJ,
    HackerRank,
    HackerEarth,
    UVa,
    Timus,
    Aizu,
    POJ,
    Eolymp,
    LightOJ,
    Toph,
]


def parse(link):
    for cls in OJS:
        obj = cls.try_parse(link)
        if obj:
            return obj
    return None


def oj_names():
    return [cls.name for cls in OJS]