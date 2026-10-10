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
        re.compile(
            r"codeforces\.com/(?:contest|problemset/problem|gym)/"
            r"(?P<cid>\d+)/(?:problem/)?(?P<pid>[A-Z]\d?)"
        ),
    ]

    def build_id(self, m):
        return f"{m.group('cid')}{m.group('pid')}"


class AtCoder(BaseOJ):
    name = "atcoder"
    patterns = [
        re.compile(
            r"atcoder\.jp/contests/(?P<contest>[^/]+)/tasks/(?P<task>[^/?#]+)"
        ),
    ]

    def build_id(self, m):
        return m.group("task")


OJS = [Codeforces, AtCoder]


def parse(link):
    for cls in OJS:
        obj = cls.try_parse(link)
        if obj:
            return obj
    return None


def oj_names():
    return [cls.name for cls in OJS]