import os
import tempfile
import unittest
from cli import compile_lua, execute_lua


class TestBasic(unittest.TestCase):
    """Basic tests for PyLua functionality."""
    
    def test_compile_and_execute(self):
        """Test compiling and executing a simple Lua script."""
        # Create a temporary Lua file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
            f.write('print("Hello, PyLua!")')
            lua_file = f.name
        
        try:
            # Test direct execution
            exit_code = execute_lua(source_file=lua_file)
            self.assertEqual(exit_code, 0)
            
            # Test compilation and execution
            luac_file = lua_file.replace('.lua', '.luac')
            proto = compile_lua(lua_file, output_file=luac_file)
            self.assertIsNotNone(proto)
            
            # Test executing compiled bytecode
            exit_code = execute_lua(bytecode_file=luac_file)
            self.assertEqual(exit_code, 0)
            
        finally:
            # Clean up
            if os.path.exists(lua_file):
                os.remove(lua_file)
            if os.path.exists(luac_file):
                os.remove(luac_file)
    
    def test_arithmetic(self):
        """Test arithmetic operations."""
        # Create a temporary Lua file with arithmetic operations
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
            f.write('print(1 + 2)\n')
            f.write('print(5 - 3)\n')
            f.write('print(2 * 4)\n')
            f.write('print(10 / 2)\n')
            lua_file = f.name
        
        try:
            exit_code = execute_lua(source_file=lua_file)
            self.assertEqual(exit_code, 0)
        finally:
            if os.path.exists(lua_file):
                os.remove(lua_file)
    
    def test_if_statement(self):
        """Test if statements."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as f:
            f.write('if 1 > 0 then\n')
            f.write('    print("1 is greater than 0")\n')
            f.write('end\n')
            lua_file = f.name
        
        try:
            exit_code = execute_lua(source_file=lua_file)
            self.assertEqual(exit_code, 0)
        finally:
            if os.path.exists(lua_file):
                os.remove(lua_file)


if __name__ == '__main__':
    unittest.main()
