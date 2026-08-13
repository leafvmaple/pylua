import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from cli import PyLua, compile_lua, execute_lua, run_interactive


class TestCLI(unittest.TestCase):
    def test_script_arguments_are_exposed_in_arg_table(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False) as source:
            source.write("print(arg[0], arg[1], arg[2])")
            source_path = source.name
        try:
            output = io.StringIO()
            with redirect_stdout(output):
                status = execute_lua(source_file=source_path, args=["first", "second"])
            self.assertEqual(status, 0)
            self.assertEqual(output.getvalue().strip(), f"{source_path}\tfirst\tsecond")
        finally:
            os.remove(source_path)

    def test_strip_removes_nested_debug_records(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = os.path.join(directory, "source.lua")
            output_path = os.path.join(directory, "output.luac")
            with open(source_path, "w", encoding="utf-8") as source:
                source.write("local x = 1\nfunction f() local y = x return y end")
            proto = compile_lua(source_path, output_path, strip_debug=True)
            self.assertIsNotNone(proto)
            loaded = PyLua(output_path).main
            for current in [loaded, *loaded.protos]:
                self.assertEqual(current.source, "")
                self.assertEqual(current.debug.loc_vars, [])
                self.assertEqual(current.debug.upvalues, [])

    def test_compiler_populates_debug_records_before_strip(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False) as source:
            source.write("local x=1\nlocal function f() return x end\nprint(f())")
            source_path = source.name
        try:
            proto = compile_lua(source_path)
            self.assertIsNotNone(proto)
            assert proto is not None
            self.assertEqual(proto.source, source_path)
            self.assertEqual(len(proto.debug.line_infos), len(proto.codes))
            self.assertTrue(proto.debug.loc_vars)
            self.assertEqual(proto.protos[0].debug.upvalues, ["x"])
        finally:
            os.remove(source_path)

    def test_repl_preserves_globals_between_lines(self):
        output = io.StringIO()
        with (
            patch("builtins.input", side_effect=["x = 7", "print(x)", "exit()"]),
            redirect_stdout(output),
        ):
            status = run_interactive()
        self.assertEqual(status, 0)
        self.assertIn("\n7\n", output.getvalue())


if __name__ == "__main__":
    unittest.main()
