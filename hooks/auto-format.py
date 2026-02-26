#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""PostToolUse hook: find nearest mise.toml/package.json with 'format' task, run on single file."""

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


def extract_file_path() -> str | None:
    data = json.load(sys.stdin)
    return data.get("tool_input", {}).get("file_path")


def find_format_task(file_path: Path) -> tuple[str, Path] | None:
    """Walk up directories to find nearest mise.toml or package.json with a format task."""
    dir = file_path.parent
    while dir != dir.parent:
        mise = dir / "mise.toml"
        if mise.is_file():
            text = mise.read_text()
            if re.search(r"^\[tasks\.format\]", text, re.MULTILINE):
                return ("mise", dir)

        pkg = dir / "package.json"
        if pkg.is_file():
            data = json.loads(pkg.read_text())
            if "format" in data.get("scripts", {}):
                return ("pkg", dir)

        dir = dir.parent
    return None


def extract_format_cmd(kind: str, task_dir: Path) -> str | None:
    """Extract the raw format command string from config."""
    if kind == "pkg":
        data = json.loads((task_dir / "package.json").read_text())
        return data["scripts"]["format"]
    elif kind == "mise":
        text = (task_dir / "mise.toml").read_text()
        m = re.search(
            r'\[tasks\.format\].*?run\s*=\s*"([^"]+)"', text, re.DOTALL
        )
        return m.group(1) if m else None
    return None


def strip_file_args(cmd: str) -> str:
    """Keep tool + flags, drop positional file/glob args.

    'prettier --write .'              -> 'prettier --write'
    'sqlfluff format migrations/*.sql' -> 'sqlfluff format'
    """
    parts = shlex.split(cmd)
    base = []
    for p in parts:
        if p.startswith("-") or not any(c in p for c in "./*"):
            base.append(p)
        else:
            break
    return " ".join(base)


def main() -> None:
    file_path_str = extract_file_path()
    if not file_path_str:
        return

    file_path = Path(file_path_str)
    if not file_path.is_file():
        return

    result = find_format_task(file_path)
    if not result:
        return

    kind, task_dir = result
    fmt_cmd = extract_format_cmd(kind, task_dir)
    if not fmt_cmd:
        return

    base_cmd = strip_file_args(fmt_cmd)
    if not base_cmd:
        return

    subprocess.run(
        [*shlex.split(base_cmd), str(file_path)],
        cwd=task_dir,
        capture_output=True,
    )


if __name__ == "__main__":
    main()
