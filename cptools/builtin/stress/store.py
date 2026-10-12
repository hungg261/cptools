import hashlib
import json
import os
import shutil
from pathlib import Path

CONFIG_DIR = Path(os.environ["CPTOOLS_PLUGIN_CONFIG_DIR"])
DATA_DIR = Path(os.environ["CPTOOLS_PLUGIN_DATA_DIR"])
CACHE_DIR = Path(os.environ["CPTOOLS_PLUGIN_CACHE_DIR"])

CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "compiler": "g++",
    "compiler_flags": "-O2 -std=c++17",
    "compile_timeout": 60,
    "time_limit": 1.0,
    "warn_factor": 1.0,
    "slow_factor": 2.0,
    "fail_factor": 3.0,
    "gen_timeout": 5.0,
    "match_mode": "token",
    "stop_on_fail": True,
    "max_fails": 50,
    "no_compile": False,
}

DEFAULT_IO = {
    "input": "stdin",
    "output": "stdout",
    "input_file": "input.txt",
    "output_file": "output.txt",
}

IO_TARGETS = ("sol", "brute")

DEFAULT_PER_SOLUTION = {
    "source": "",
    "generator": "",
    "mode": "standard",
    "standard": {"extra": "", "match_mode": "token"},
    "checker": {"extra": "", "checker": ""},
    "interactive": {"extra": "", "log_interactions": False},
    "io": {},
    "seed": 0,
    "randomize_per_iter": False,
    "gen_args": "",
}


def _sanitize_flags(raw):
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw
        for ch in "[]'\",":
            s = s.replace(ch, " ")
        return s.split()
    if isinstance(raw, (list, tuple)):
        parts = []
        for item in raw:
            s = str(item)
            for ch in "[]'\",":
                s = s.replace(ch, " ")
            parts.extend(s.split())
        return parts
    return str(raw).split()


# ---------- global config ----------

def load_config():
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    cfg = dict(DEFAULT_CONFIG)
    for k, v in data.items():
        if k in ("time_limit", "warn_factor", "slow_factor",
                 "fail_factor", "gen_timeout"):
            try:
                cfg[k] = float(v)
            except (TypeError, ValueError):
                pass
        elif k == "max_fails" or k == "compile_timeout":
            try:
                cfg[k] = int(v)
            except (TypeError, ValueError):
                pass
        elif k == "compiler_flags":
            cfg[k] = _sanitize_flags(v)
        elif k in ("stop_on_fail", "no_compile"):
            if isinstance(v, bool):
                cfg[k] = v
            else:
                cfg[k] = str(v).lower() in ("1", "true", "yes", "on")
        else:
            cfg[k] = v
    return cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------- per-solution ----------

def _key(source_path):
    p = str(Path(source_path).resolve())
    return hashlib.sha1(p.encode("utf-8")).hexdigest()[:16]


def _per_file(source_path):
    return DATA_DIR / "solutions" / f"{_key(source_path)}.json"


def _ensure_io_shape(data):
    io = data.get("io")
    if isinstance(io, dict) and ("input" in io or "output" in io):
        base = dict(DEFAULT_IO)
        base.update({k: v for k, v in io.items() if k in DEFAULT_IO})
        io = {t: dict(base) for t in IO_TARGETS}
    elif not isinstance(io, dict):
        io = {}
    for t in IO_TARGETS:
        tio = io.get(t)
        if not isinstance(tio, dict):
            tio = {}
        merged = dict(DEFAULT_IO)
        merged.update({k: v for k, v in tio.items() if k in DEFAULT_IO})
        io[t] = merged
    data["io"] = io


def get_target_io(data, target):
    _ensure_io_shape(data)
    return dict(data["io"][target])


def set_target_io(data, target, io_dict):
    _ensure_io_shape(data)
    data["io"][target] = {
        k: io_dict.get(k, DEFAULT_IO[k]) for k in DEFAULT_IO
    }


def infer_output_file(input_name):
    if not input_name:
        return ""
    s = str(input_name).replace("\\", "/")
    if "/" in s:
        folder, fname = s.rsplit("/", 1)
        folder = folder + "/"
    else:
        folder, fname = "", s
    if "." in fname:
        stem, ext = fname.rsplit(".", 1)
        if not stem:
            return folder + fname + ".out"
        if ext.lower() == "out":
            return f"{folder}{stem}.txt"
        if ext.isupper():
            return f"{folder}{stem}.OUT"
        return f"{folder}{stem}.out"
    return f"{folder}{fname}.out"


def load_solution(source_path):
    resolved = str(Path(source_path).resolve())
    f = _per_file(source_path)
    if not f.exists():
        data = json.loads(json.dumps(DEFAULT_PER_SOLUTION))
        data["source"] = resolved
        _ensure_io_shape(data)
        return data
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        data = json.loads(json.dumps(DEFAULT_PER_SOLUTION))
    data.setdefault("source", resolved)
    for mode in ("standard", "checker", "interactive"):
        sub = dict(DEFAULT_PER_SOLUTION[mode])
        sub.update(data.get(mode) or {})
        data[mode] = sub
    data.setdefault("generator", "")
    data.setdefault("mode", "standard")
    data.setdefault("seed", 0)
    data.setdefault("randomize_per_iter", False)
    data.setdefault("gen_args", "")
    _ensure_io_shape(data)
    return data


def save_solution(data):
    src = data.get("source")
    if not src:
        return
    f = _per_file(src)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------- work dir + fail storage ----------

def work_root(source_path):
    stem = Path(source_path).stem
    return CACHE_DIR / "run" / f"{stem}_{_key(source_path)}"


def bin_dir(source_path):
    p = work_root(source_path) / "bin"
    p.mkdir(parents=True, exist_ok=True)
    return p


def fails_dir(source_path):
    p = DATA_DIR / "solutions" / _key(source_path) / "fails"
    p.mkdir(parents=True, exist_ok=True)
    return p


def clear_fails(source_path):
    p = DATA_DIR / "solutions" / _key(source_path) / "fails"
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)


def save_fail(source_path, index, seed, status, input_text,
              expected="", got="", stderr="", log=""):
    d = fails_dir(source_path) / f"fail_{index:03d}_seed{seed}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "input.txt").write_text(input_text, encoding="utf-8")
    if expected:
        (d / "expected.txt").write_text(expected, encoding="utf-8")
    if got:
        (d / "got.txt").write_text(got, encoding="utf-8")
    if stderr:
        (d / "stderr.txt").write_text(stderr, encoding="utf-8")
    if log:
        (d / "interaction_log.txt").write_text(log, encoding="utf-8")

    meta = {"index": index, "seed": seed, "status": status}
    (d / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return d


def testlib_dir():
    p = DATA_DIR / "testlib"
    p.mkdir(parents=True, exist_ok=True)
    return p