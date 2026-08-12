#!/usr/bin/env python3
"""Compare PyLua behavior with a reference Lua interpreter.

The runner compares successful programs by exact stdout and failing programs by
their success/error classification. Error text is intentionally not compared,
because it contains implementation-specific paths and stack traces.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "tests" / "lua_conformance.json"


@dataclass(frozen=True)
class LuaCase:
    name: str
    source: str


@dataclass(frozen=True)
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


def load_cases(path: Path = DEFAULT_CASES) -> list[LuaCase]:
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("conformance corpus must be a JSON array")

    cases: list[LuaCase] = []
    names: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("each conformance case must have a string name")
        if not isinstance(item.get("source"), str):
            raise ValueError(f"case {item['name']!r} must have string source")
        if item["name"] in names:
            raise ValueError(f"duplicate conformance case: {item['name']}")
        names.add(item["name"])
        cases.append(LuaCase(item["name"], item["source"]))
    return cases


def run_command(command: list[str], source: str) -> ExecutionResult:
    completed = subprocess.run(
        [*command, "-e", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return ExecutionResult(completed.returncode, completed.stdout, completed.stderr)


def compare_results(reference: ExecutionResult, pylua: ExecutionResult) -> str | None:
    if reference.succeeded != pylua.succeeded:
        return (
            f"outcome differs: reference={'ok' if reference.succeeded else 'error'}, "
            f"pylua={'ok' if pylua.succeeded else 'error'}"
        )
    if reference.succeeded and reference.stdout != pylua.stdout:
        return f"stdout differs: reference={reference.stdout!r}, pylua={pylua.stdout!r}"
    return None


def detect_lua(explicit: str | None) -> str:
    if explicit:
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
        candidate = Path(explicit)
        if candidate.is_file():
            return str(candidate.resolve())
        raise FileNotFoundError(f"Lua interpreter not found: {explicit}")

    for name in ("lua5.1", "lua51", "lua"):
        if resolved := shutil.which(name):
            return resolved
    raise FileNotFoundError("Lua interpreter not found; pass --lua /path/to/lua5.1")


def lua_version(lua: str) -> str:
    completed = subprocess.run(
        [lua, "-e", "io.write(_VERSION)"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"failed to query reference Lua version: {completed.stderr.strip()}")
    return completed.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lua", help="reference Lua executable (defaults to lua5.1/lua51/lua)")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="JSON corpus path")
    parser.add_argument("--case", action="append", dest="selected", help="run one named case")
    parser.add_argument("--list", action="store_true", help="list case names without running")
    parser.add_argument(
        "--allow-version-mismatch",
        action="store_true",
        help="allow a reference other than Lua 5.1 for preliminary checks",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_cases(args.cases)

    if args.list:
        for case in cases:
            print(case.name)
        return 0

    if args.selected:
        selected = set(args.selected)
        known = {case.name for case in cases}
        if unknown := selected - known:
            raise SystemExit(f"unknown case(s): {', '.join(sorted(unknown))}")
        cases = [case for case in cases if case.name in selected]

    lua = detect_lua(args.lua)
    version = lua_version(lua)
    if version != "Lua 5.1" and not args.allow_version_mismatch:
        raise SystemExit(
            f"reference is {version!r}, expected 'Lua 5.1'; "
            "pass --allow-version-mismatch only for preliminary checks"
        )

    pylua_command = [sys.executable, str(ROOT / "pylua.py")]
    failures = 0
    for case in cases:
        reference = run_command([lua], case.source)
        pylua = run_command(pylua_command, case.source)
        mismatch = compare_results(reference, pylua)
        if mismatch:
            failures += 1
            print(f"FAIL\t{case.name}\t{mismatch}")
        else:
            print(f"PASS\t{case.name}")

    print(f"TOTAL\t{len(cases)}\tFAILURES\t{failures}\tREFERENCE\t{version}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
