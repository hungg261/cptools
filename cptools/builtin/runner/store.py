import hashlib
import json
import os
from pathlib import Path

from cptools.lib import history as lib_history

DATA_DIR = Path(os.environ["CPTOOLS_PLUGIN_DATA_DIR"])
TESTS_DIR = DATA_DIR / "tests"

DEFAULT_IO = {
    "input": "stdin",
    "output": "stdout",
    "input_file": "input.txt",
    "output_file": "output.txt",
}


def _key(source_path):
    p = str(Path(source_path).resolve())
    return hashlib.sha1(p.encode("utf-8")).hexdigest()[:16]


def _file_for(source_path):
    return TESTS_DIR / f"{_key(source_path)}.json"


def load(source_path):
    f = _file_for(source_path)
    resolved = str(Path(source_path).resolve())
    if not f.exists():
        return {"source": resolved, "tests": [], "io": dict(DEFAULT_IO)}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {"source": resolved, "tests": [], "io": dict(DEFAULT_IO)}
    data.setdefault("source", resolved)
    data.setdefault("tests", [])
    io = dict(DEFAULT_IO)
    io.update(data.get("io") or {})
    data["io"] = io
    return data


def save(data):
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    f = _file_for(data["source"])
    f.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_test(data, input_text, expected):
    tests = data.setdefault("tests", [])
    tid = len(tests) + 1
    tests.append({"id": tid, "input": input_text, "expected": expected})
    return tid


def remove_test(data, test_id):
    tests = data.get("tests", [])
    before = len(tests)
    data["tests"] = [t for t in tests if t.get("id") != test_id]
    if len(data["tests"]) == before:
        return False
    for i, t in enumerate(data["tests"], start=1):
        t["id"] = i
    return True


def find_test(data, test_id):
    for t in data.get("tests", []):
        if t.get("id") == test_id:
            return t
    return None


def work_root_for(source_path):
    p = str(Path(source_path).resolve())
    h = hashlib.sha1(p.encode("utf-8")).hexdigest()[:8]
    stem = Path(source_path).stem
    return Path(os.environ["CPTOOLS_PLUGIN_CACHE_DIR"]) / "run" / f"{stem}_{h}"


# --- history (delegated to shared lib) ---

def load_history():
    return lib_history.load()


def add_to_history(path):
    return lib_history.add(path)


def clear_history():
    lib_history.clear()