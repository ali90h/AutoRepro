#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a Mermaid mindmap of the repository into docs/MINDMAP.md.

- Root node = repo name
- Children = top-level folders/modules
- Files show LOC; big files (>500 LOC) marked 🔴
- Functions/classes listed with simple notes; big functions (>80 LOC) marked 🟠
"""
import os, sys, ast, textwrap, pathlib, re
from collections import defaultdict

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "docs" / "MINDMAP.md"
BIG_FILE = 500
BIG_FUNC = 80

INCLUDE_DIRS = None  # None = include all; or set like {"autorepro", "src"}
EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
}
def repo_name() -> str:
    return REPO_ROOT.name

def rel(p: pathlib.Path) -> str:
    return str(p.relative_to(REPO_ROOT))

def count_loc(path: pathlib.Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def parse_py_symbols(path: pathlib.Path):
    """Return (classes, functions) with simple size info."""
    classes, funcs = [], []
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
        # map node -> lines count using end_lineno if available (py3.8+)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                length = (getattr(node, "end_lineno", node.lineno) or 0) - (node.lineno or 0) + 1
                classes.append((node.name, max(length, 0)))
            elif isinstance(node, ast.FunctionDef):
                length = (getattr(node, "end_lineno", node.lineno) or 0) - (node.lineno or 0) + 1
                funcs.append((node.name, max(length, 0)))
    except Exception:
        pass
    # sort by length desc then name
    classes.sort(key=lambda x: (-x[1], x[0]))
    funcs.sort(key=lambda x: (-x[1], x[0]))
    # keep top few to avoid bloat
    return classes[:8], funcs[:10]

def should_skip_dir(d: str) -> bool:
    if d in EXCLUDE_DIRS: 
        return True
    if INCLUDE_DIRS and d not in INCLUDE_DIRS:
        return True
    return False

def collect_tree():
    tree = defaultdict(list)  # dir -> list of files
    for root, dirs, files in os.walk(REPO_ROOT):
        # prune
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        # optional INCLUDE filter at top-level
        if INCLUDE_DIRS and pathlib.Path(root) == REPO_ROOT:
            dirs[:] = [d for d in dirs if d in INCLUDE_DIRS]
        for f in files:
            if f.endswith(".py"):
                p = pathlib.Path(root) / f
                tree[str(pathlib.Path(root))].append(p)
    return tree

def indent(level: int) -> str:
    return "  " * level

def file_node_line(path: pathlib.Path, loc: int) -> str:
    mark = " 🔴" if loc > BIG_FILE else ""
    return f"{path.name} ({loc} LOC){mark}"

def symbol_line(kind: str, name: str, length: int) -> str:
    mark = " 🟠" if length > BIG_FUNC else ""
    if kind == "class":
        return f"{name} [class {length} LOC]{mark}"
    else:
        return f"{name} [fn {length} LOC]{mark}"

def build_mermaid(tree):
    lines = []
    lines.append("```mermaid")
    lines.append("mindmap")
    lines.append(f"  {repo_name()}")
    # gather top-level dirs
    top_dirs = sorted({
        pathlib.Path(d).parts[-1]
        for d in tree.keys()
        if pathlib.Path(d) != REPO_ROOT
    })
    for d in top_dirs:
        lines.append(f"    {d}")
        # collect sub-items under any folder with that tail
        for dir_abs, files in sorted(tree.items()):
            if pathlib.Path(dir_abs).parts[-1] != d: 
                continue
            # group by immediate subfolder for depth
            for fp in sorted(files, key=lambda p: rel(p)):
                loc = count_loc(fp)
                lines.append(f"      {file_node_line(fp, loc)}")
                classes, funcs = parse_py_symbols(fp)
                if classes:
                    lines.append("        Classes")
                    for cname, clen in classes:
                        lines.append(f"          {symbol_line('class', cname, clen)}")
                if funcs:
                    lines.append("        Functions")
                    for fname, flen in funcs:
                        lines.append(f"          {symbol_line('func', fname, flen)}")
    # also include top-level .py files at repo root
    root_py = list(REPO_ROOT.glob("*.py"))  # C416
    if root_py:
        lines.append("    __root__")
        for fp in sorted(root_py, key=lambda p: p.name):
            loc = count_loc(fp)
            lines.append(f"      {file_node_line(fp, loc)}")
            classes, funcs = parse_py_symbols(fp)
            if classes:
                lines.append("        Classes")
                for cname, clen in classes:
                    lines.append(f"          {symbol_line('class', cname, clen)}")
            if funcs:
                lines.append("        Functions")
                for fname, flen in funcs:
                    lines.append(f"          {symbol_line('func', fname, flen)}")
    lines.append("```")
    return "\n".join(lines) + "\n"

def main():
    # ensure docs/
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tree = collect_tree()
    content = build_mermaid(tree)
    header = (
        "# Repository Mindmap\n\n"
        "Generated automatically. Big files marked 🔴, big functions marked 🟠.\n\n"
    )
    OUT_PATH.write_text(header + content, encoding="utf-8")
    print(f"wrote {rel(OUT_PATH)}")

if __name__ == "__main__":
    sys.exit(main())
