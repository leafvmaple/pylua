from __future__ import annotations

from structs.value import LUA_TYPE, Value
from structs.instruction import Instruction
from structs.function import LocalVar, Debug, Proto
from .header import Header
from .io import Writer


def write_header(file: Writer, header: Header) -> None:
    file.write_bytes(header.signature)
    file.write_uint8(header.version)
    file.write_uint8(header.format)
    file.write_uint8(header.endianness)
    file.write_uint8(header.int_len)
    file.write_uint8(header.size_len)
    file.write_uint8(header.inst_len)
    file.write_uint8(header.number_len)
    file.write_uint8(1 if header.number_is_int else 0)


def write_instruction(file: Writer, inst: Instruction) -> None:
    file.write_uint32(inst.to_bitset())


def write_local_var(file: Writer, loc_var: LocalVar) -> None:
    file.write_string(loc_var.name)
    file.write_uint32(loc_var.start_pc)
    file.write_uint32(loc_var.end_pc)


def write_debug(file: Writer, debug: Debug) -> None:
    file.write_uint32(len(debug.line_infos))
    for line in debug.line_infos:
        file.write_uint32(line)

    file.write_uint32(len(debug.loc_vars))
    for loc_var in debug.loc_vars:
        write_local_var(file, loc_var)

    file.write_uint32(len(debug.upvalues))
    for upvalue in debug.upvalues:
        file.write_string(upvalue)


def write_value(file: Writer, value: Value) -> None:
    if value.is_nil():
        file.write_uint8(LUA_TYPE.NIL.value)
    elif value.is_boolean():
        file.write_uint8(LUA_TYPE.BOOLEAN.value)
        file.write_uint8(1 if value.value else 0)
    elif value.is_number():
        file.write_uint8(LUA_TYPE.NUMBER.value)
        file.write_double(value.value)
    elif value.is_string():
        file.write_uint8(LUA_TYPE.STRING.value)
        file.write_string(value.value)
    else:
        raise ValueError(f"Cannot serialize value type: {type(value.value)}")


def write_proto(file: Writer, proto: Proto) -> None:
    file.write_string(proto.source)
    file.write_uint32(proto.line_defined)
    file.write_uint32(proto.last_line_defined)
    file.write_uint8(proto.num_upvalues)
    file.write_uint8(proto.num_params)
    file.write_uint8(1 if proto.is_vararg else 0)
    file.write_uint8(proto.max_stack_size)

    # Code
    file.write_uint32(len(proto.codes))
    for code in proto.codes:
        write_instruction(file, code)

    # Constants
    file.write_uint32(len(proto.consts))
    for const in proto.consts:
        write_value(file, const)

    # Sub-protos
    file.write_uint32(len(proto.protos))
    for sub_proto in proto.protos:
        write_proto(file, sub_proto)

    # Debug info
    write_debug(file, proto.debug)


def write_bytecode(proto: Proto, output_file: str) -> None:
    """Write a Proto to a bytecode file.
    
    Args:
        proto: The Proto to write
        output_file: The path to the output file
    """
    # Create a default header
    header = Header()
    header.signature = b'\x1bLua'
    header.version = 0x53  # Lua 5.3
    header.format = 0
    header.endianness = 1  # Little endian
    header.int_len = 4
    header.size_len = 4
    header.inst_len = 4
    header.number_len = 8
    header.number_is_int = 0

    # Write to file
    with open(output_file, 'wb') as f:
        writer = Writer(f)
        write_header(writer, header)
        write_proto(writer, proto)
