from __future__ import annotations

from lua_io import Reader
from lua_value import LUA_TYPE, Value
from structs.instruction import Instruction
from lua_function import LocalVar, Debug, Proto
from lua_header import Header


def read_header(file: Reader) -> Header:
    header = Header()
    header.signature = file.read_bytes(4)
    if header.signature != b'\x1bLua':
        raise ValueError("Not a valid Lua bytecode file")
    header.version = file.read_uint8()
    header.format = file.read_uint8()
    header.endianness = file.read_uint8()
    header.int_len = file.read_uint8()
    header.size_len = file.read_uint8()
    header.inst_len = file.read_uint8()
    header.number_len = file.read_uint8()
    header.number_is_int = (file.read_uint8() != 0)
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

    size_line_infos = file.read_uint32()
    debug.line_infos = [file.read_uint32() for _ in range(size_line_infos)]

    size_loc_vars = file.read_uint32()
    debug.loc_vars = [read_local_var(file) for _ in range(size_loc_vars)]

    size_upvalues = file.read_uint32()
    debug.upvalues = [file.read_string() for _ in range(size_upvalues)]

    return debug


def read_value(file: Reader) -> Value:
    _type = LUA_TYPE(file.read_uint8())
    if _type == LUA_TYPE.NIL:
        return Value.nil()
    elif _type == LUA_TYPE.BOOLEAN:
        return Value.boolean(file.read_uint8() != 0)
    elif _type == LUA_TYPE.NUMBER:
        return Value.number(file.read_double())
    elif _type == LUA_TYPE.STRING:
        return Value.string(file.read_string())
    else:
        raise ValueError(f"Unknown constant type: {_type}")


def read_proto(file: Reader, parent: str | None = None) -> Proto:
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
    size_codes = file.read_uint32()
    proto.codes = [read_instruction(file) for _ in range(size_codes)]

    # Constants
    size_k = file.read_uint32()
    proto.consts = [read_value(file) for _ in range(size_k)]

    # Sub-protos
    size_p = file.read_uint32()
    proto.protos = [read_proto(file, proto.source) for _ in range(size_p)]

    # Debug info
    proto.debug = read_debug(file)

    for pc, code in enumerate(proto.codes):
        code.update_info(pc, proto.consts, proto.debug.upvalues)

    return proto
