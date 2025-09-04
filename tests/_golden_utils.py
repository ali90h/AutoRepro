from __future__ import annotations

import difflib
import json
import subprocess
import sys
from pathlib import Path


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def canon_md(s: str) -> str:
    # normalize CRLF→LF, strip trailing spaces on each line, ensure trailing newline
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    return (s + "\n") if not s.endswith("\n") else s


def canon_json_bytes(b: bytes) -> str:
    obj = json.loads(b.decode("utf-8"))
    # stable dump (sorted keys, compact separators)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def run_cli(args: list[str], cwd: Path) -> tuple[str, str, int]:
    import os

    # Get the autorepro root directory (parent of tests/)
    autorepro_root = Path(__file__).parent.parent

    # Set up environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(autorepro_root)

    cp = subprocess.run(
        [sys.executable, "-m", "autorepro", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
    )
    return cp.stdout, cp.stderr, cp.returncode


# tiny helpers used by tests
def touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")


def write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def unified_diff(
    expected: str, actual: str, fromfile: str = "expected", tofile: str = "actual"
) -> str:
    return "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
        )
    )
