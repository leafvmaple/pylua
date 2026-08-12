from __future__ import annotations

from structs.function import Debug, LocalVar, Proto
from structs.instruction import Instruction
from structs.value import LuaType, Value

from .header import Header
from .io import Reader

MAX_ITEMS = 1_000_000
MAX_PROTO_DEPTH = 200


def _read_count(file: Reader, label: str) -> int:
    count = file.read_uint32()
    if count > MAX_ITEMS:
        raise ValueError(f"Too many {label} in bytecode: {count}")
    return count


def read_header(file: Reader) -> Header:
    header = Header()
    header.signature = file.read_bytes(4)
    if header.signature != b"\x1bLua":
        raise ValueError("Not a valid Lua bytecode file")
    header.version = file.read_uint8()
    if header.version not in Header.SUPPORTED_VERSIONS:
        version_str = f"{header.version >> 4}.{header.version & 0xF}"
        raise ValueError(f"Unsupported Lua version: {version_str} (expected 5.1)")
    header.format = file.read_uint8()
    header.endianness = file.read_uint8()
    header.int_len = file.read_uint8()
    header.size_len = file.read_uint8()
    header.inst_len = file.read_uint8()
    header.number_len = file.read_uint8()
    header.number_is_int = file.read_uint8() != 0
    if header.format != 0:
        raise ValueError(f"Unsupported Lua bytecode format: {header.format}")
    if header.endianness not in (0, 1):
        raise ValueError(f"Invalid bytecode endianness: {header.endianness}")
    if header.int_len != 4 or header.inst_len != 4:
        raise ValueError("Only 32-bit Lua integers and instructions are supported")
    if header.size_len not in (4, 8):
        raise ValueError(f"Unsupported size_t width: {header.size_len}")
    if header.number_len != 8 or header.number_is_int:
        raise ValueError("Only double-precision Lua numbers are supported")
    file.configure(header.endianness, header.size_len)
    return header


def read_instruction(file: Reader) -> Instruction:
    code = file.read_uint32()
    return Instruction(code)


def read_local_var(file: Reader) -> LocalVar:
    loc_var = LocalVar()
    loc_var.name = file.read_string()
    loc_var.start_pc = file.read_uint32()
    loc_var.end_pc = file.read_uint32()
    return loc_var


def read_debug(file: Reader) -> Debug:
    debug = Debug()

    size_line_infos = _read_count(file, "line records")
    debug.line_infos = [file.read_uint32() for _ in range(size_line_infos)]

    size_loc_vars = _read_count(file, "local variables")
    debug.loc_vars = [read_local_var(file) for _ in range(size_loc_vars)]

    size_upvalues = _read_count(file, "upvalues")
    debug.upvalues = [file.read_string() for _ in range(size_upvalues)]

    return debug


def read_value(file: Reader) -> Value:
    _type = LuaType(file.read_uint8())
    if _type == LuaType.NIL:
        return Value.nil()
    elif _type == LuaType.BOOLEAN:
        return Value.boolean(file.read_uint8() != 0)
    elif _type == LuaType.NUMBER:
        return Value.number(file.read_double())
    elif _type == LuaType.STRING:
        return Value.string(file.read_string())
    else:
        raise ValueError(f"Unknown constant type: {_type}")


def read_proto(file: Reader, parent: str | None = None, depth: int = 0) -> Proto:
    if depth > MAX_PROTO_DEPTH:
        raise ValueError("Bytecode prototype nesting is too deep")
    proto = Proto()
    proto.source = file.read_string()
    if parent is not None:
        proto.source = parent
        proto.type = "function"
    else:
        proto.type = "main"

    proto.line_defined = file.read_uint32()
    proto.last_line_defined = file.read_uint32()
    proto.num_upvalues = file.read_uint8()
    proto.num_params = file.read_uint8()
    proto.is_vararg = file.read_uint8() != 0
    proto.max_stack_size = file.read_uint8()

    # Code
    size_codes = _read_count(file, "instructions")
    proto.codes = [read_instruction(file) for _ in range(size_codes)]

    # Constants
    size_k = _read_count(file, "constants")
    proto.consts = [read_value(file) for _ in range(size_k)]

    # Sub-protos
    size_p = _read_count(file, "nested prototypes")
    proto.protos = [read_proto(file, proto.source, depth + 1) for _ in range(size_p)]

    # Debug info
    proto.debug = read_debug(file)

    for pc, code in enumerate(proto.codes):
        code.update_info(pc, proto.consts, proto.debug.upvalues)

    return proto
