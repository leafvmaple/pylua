"""Lua bytecode loader and VM entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from binary.io import Reader
from binary.reader import read_header, read_proto
from binary.header import Header
from structs.function import Proto
from parser.lexer import Lexer
from parser.block import Parser
from vm.state import LuaState
from vm.lua_vm import LuaVM


class PyLua:
    """Lua bytecode loader."""
    reader: Reader
    header: Header
    main: Proto

    def __init__(self, file_path: str):
        with open(file_path, 'rb') as f:
            self.reader = Reader(f)
            self.header = read_header(self.reader)
            self.main = read_proto(self.reader)

    def __str__(self) -> str:
        return f"{self.main}"


def compile_lua(source_file: str, output_file: str | None = None, 
                list_bytecode: bool = False, parse_only: bool = False,
                strip_debug: bool = False) -> Proto | None:
    """
    Compile a Lua source file to bytecode.
    
    Args:
        source_file: Path to the .lua source file
        output_file: Path for output .luac file (default: source_file with .luac extension)
        list_bytecode: Print bytecode listing (-l)
        parse_only: Parse only, don't generate code (-p)
        strip_debug: Strip debug information (-s)
    
    Returns:
        Proto object if successful, None otherwise
    """
    try:
        lexer = Lexer.from_file(source_file)
        parser = Parser.from_lexer(lexer)
        info = parser.to_info()
        
        if parse_only:
            print(f"luac: {source_file} parsed successfully")
            return None
        
        proto = info.to_proto()
        
        if list_bytecode:
            print(f"\nmain <{source_file}:0,0> ({len(proto.codes)} instructions)")
            print(info)
        
        # TODO: Implement bytecode serialization to output_file
        # if output_file:
        #     write_bytecode(proto, output_file)
        
        return proto
    except Exception as e:
        print(f"pyluac: {source_file}: {e}", file=sys.stderr)
        return None


def execute_lua(source_file: str | None = None, bytecode_file: str | None = None,
                args: list[str] | None = None, interactive: bool = False,
                execute_string: str | None = None, version: bool = False) -> int:
    """
    Execute a Lua script or bytecode file.
    
    Args:
        source_file: Path to the .lua source file
        bytecode_file: Path to the .luac bytecode file
        args: Command-line arguments to pass to the script
        interactive: Enter interactive mode after running script (-i)
        execute_string: Execute string as Lua code (-e)
        version: Show version information (-v)
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    if version:
        print("PyLua 0.1.0 -- A Lua implementation in Python")
        print("Copyright (C) 2024")
        if not source_file and not bytecode_file and not execute_string:
            return 0
    
    try:
        proto = None
        
        if execute_string:
            # Execute string directly
            lexer = Lexer.from_string(execute_string)
            parser = Parser.from_lexer(lexer)
            info = parser.to_info()
            proto = info.to_proto()
        elif bytecode_file:
            # Load precompiled bytecode
            pylua = PyLua(bytecode_file)
            proto = pylua.main
        elif source_file:
            # Compile and execute source file
            lexer = Lexer.from_file(source_file)
            parser = Parser.from_lexer(lexer)
            info = parser.to_info()
            proto = info.to_proto()
        else:
            # Interactive mode or stdin
            if interactive or sys.stdin.isatty():
                return run_interactive()
            else:
                # Read from stdin
                source = sys.stdin.read()
                lexer = Lexer.from_string(source)
                parser = Parser.from_lexer(lexer)
                info = parser.to_info()
                proto = info.to_proto()
        
        if proto:
            # Set up arguments (arg table)
            state = LuaState(proto)
            
            # Run the VM
            while LuaVM.execute(state):
                pass
        
        if interactive:
            return run_interactive()
        
        return 0
    except Exception as e:
        print(f"pylua: {e}", file=sys.stderr)
        return 1


def run_interactive() -> int:
    """Run an interactive Lua REPL."""
    print("PyLua 0.1.0 -- A Lua implementation in Python")
    print("Copyright (C) 2024")
    print('Type "exit()" or Ctrl+C to quit.')
    
    while True:
        try:
            line = input("> ")
            if line.strip() in ("exit()", "quit()", "os.exit()"):
                break
            if not line.strip():
                continue
            
            # Try to execute the line
            lexer = Lexer.from_string(line)
            parser = Parser.from_lexer(lexer)
            info = parser.to_info()
            proto = info.to_proto()
            
            state = LuaState(proto)
            while LuaVM.execute(state):
                pass
                
        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except EOFError:
            print()
            break
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
    
    return 0


def pyluac_main():
    """Entry point for pyluac (Lua compiler)."""
    parser = argparse.ArgumentParser(
        prog='pyluac',
        description='PyLua Compiler - Compile Lua source files to bytecode',
        usage='pyluac [options] [filenames]'
    )
    parser.add_argument('files', nargs='*', metavar='filename',
                        help='Lua source files to compile')
    parser.add_argument('-l', '--list', action='store_true',
                        help='list bytecode')
    parser.add_argument('-o', '--output', metavar='file',
                        help='output to file (default: luac.out)')
    parser.add_argument('-p', '--parse', action='store_true',
                        help='parse only')
    parser.add_argument('-s', '--strip', action='store_true',
                        help='strip debug information')
    parser.add_argument('-v', '--version', action='store_true',
                        help='show version information')
    parser.add_argument('--', dest='stop', action='store_true',
                        help='stop handling options')
    
    args = parser.parse_args()
    
    if args.version:
        print("PyLuac 0.1.0 -- A Lua compiler in Python")
        print("Copyright (C) 2024")
        if not args.files:
            return 0
    
    if not args.files:
        parser.print_help()
        return 1
    
    output_file = args.output or "luac.out"
    
    for source_file in args.files:
        result = compile_lua(
            source_file,
            output_file=output_file,
            list_bytecode=args.list,
            parse_only=args.parse,
            strip_debug=args.strip
        )
        if result is None and not args.parse:
            return 1
    
    return 0


def pylua_main():
    """Entry point for pylua (Lua interpreter)."""
    parser = argparse.ArgumentParser(
        prog='pylua',
        description='PyLua Interpreter - Execute Lua scripts',
        usage='pylua [options] [script [args]]'
    )
    parser.add_argument('script', nargs='?', metavar='script',
                        help='Lua script to execute')
    parser.add_argument('args', nargs='*', metavar='args',
                        help='arguments passed to the script')
    parser.add_argument('-e', '--execute', metavar='stat',
                        help='execute string as Lua code')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='enter interactive mode after running script')
    parser.add_argument('-l', '--require', metavar='name', action='append',
                        help='require library before running script')
    parser.add_argument('-v', '--version', action='store_true',
                        help='show version information')
    parser.add_argument('-E', action='store_true',
                        help='ignore environment variables')
    parser.add_argument('-W', action='store_true',
                        help='turn warnings on')
    parser.add_argument('--', dest='stop', action='store_true',
                        help='stop handling options')
    
    args = parser.parse_args()
    
    # Determine if file is source or bytecode
    source_file = None
    bytecode_file = None
    
    if args.script:
        if args.script.endswith('.luac'):
            bytecode_file = args.script
        else:
            source_file = args.script
    
    return execute_lua(
        source_file=source_file,
        bytecode_file=bytecode_file,
        args=args.args,
        interactive=args.interactive,
        execute_string=args.execute,
        version=args.version
    )


def main():
    """
    Main entry point - determine mode based on how the script is called.
    """
    # Get the name used to call the script
    prog_name = Path(sys.argv[0]).stem.lower()
    
    if prog_name == 'pyluac' or (len(sys.argv) > 1 and sys.argv[1] == '--compile'):
        # Compiler mode
        if len(sys.argv) > 1 and sys.argv[1] == '--compile':
            sys.argv.pop(1)  # Remove --compile flag
        return pyluac_main()
    elif prog_name == 'pylua' or prog_name == 'main':
        # Interpreter mode (default)
        return pylua_main()
    else:
        # Default to interpreter mode
        return pylua_main()


if __name__ == "__main__":
    sys.exit(main())
