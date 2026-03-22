from __future__ import annotations

import ast
import pathlib
import subprocess
import sys


def list_skipped_tests(path: pathlib.Path) -> list[str]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    tests: list[str] = []
    for cls in module.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            has_skip = any(
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and isinstance(dec.func.value, ast.Name)
                and dec.func.value.id == "unittest"
                and dec.func.attr == "skip"
                for dec in fn.decorator_list
            )
            if has_skip:
                tests.append(f"{cls.name}.{fn.name}")
    return tests


def run_one(test_name: str, timeout_s: int = 6) -> tuple[str, str]:
    cls, fn = test_name.split(".")
    code = (
        "import unittest,tests.test_comprehensive as tc;"
        f"tc.{cls}.{fn}=tc.{cls}.__dict__['{fn}'].__wrapped__;"
        f"s=unittest.defaultTestLoader.loadTestsFromName('tests.test_comprehensive.{cls}.{fn}');"
        "r=unittest.TextTestRunner(verbosity=0).run(s);"
        "print('RES',len(r.failures),len(r.errors),len(r.skipped))"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT", ""

    out_text = (r.stdout + r.stderr).strip()
    out = out_text.splitlines()
    tail = out[-1] if out else ""
    if r.returncode == 0 and "RES 0 0 0" in out_text:
        return "PASS", tail
    return "FAIL", tail


def main() -> int:
    path = pathlib.Path("tests/test_comprehensive.py")
    tests = list_skipped_tests(path)
    for name in tests:
        status, tail = run_one(name)
        print(f"{status}\t{name}\t{tail}")
    print(f"TOTAL\t{len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
