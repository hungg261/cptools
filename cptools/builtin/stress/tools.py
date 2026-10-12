import urllib.request
from pathlib import Path

from store import testlib_dir


TESTLIB_URL = (
    "https://raw.githubusercontent.com/MikeMirzayanov/testlib/"
    "refs/heads/master/testlib.h"
)


def download_testlib():
    """Download testlib.h to the plugin's testlib dir.

    Returns (path, None) on success, (None, error_string) on failure.
    """
    d = testlib_dir()
    d.mkdir(parents=True, exist_ok=True)
    target = d / "testlib.h"

    try:
        req = urllib.request.Request(
            TESTLIB_URL,
            headers={"User-Agent": "cptools-stress/0.1"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        if not content:
            return None, "empty response"
        target.write_bytes(content)
        return target, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"