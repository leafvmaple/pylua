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
    source = file.read_nullable_string()
    proto.source = source if source is not None else (parent or "")
    if parent is not None:
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

    validate_proto(proto)
    for pc, code in enumerate(proto.codes):
        code.update_info(pc, proto.consts, proto.debug.upvalues)

    return proto


def _validate_rk(proto: Proto, operand: int, pc: int, label: str) -> None:
    if operand >= 256:
        if operand - 256 >= len(proto.consts):
            raise ValueError(f"Invalid constant index in {label} at instruction {pc + 1}")
    elif operand >= proto.max_stack_size:
        raise ValueError(f"Invalid register in {label} at instruction {pc + 1}")


def validate_proto(proto: Proto) -> None:
    """Validate executable indices before a loaded prototype reaches the VM."""
    from codegen.inst import OpArgK, OpArgR, OpMode

    if proto.max_stack_size > 250:
        raise ValueError(f"Invalid max stack size: {proto.max_stack_size}")
    if proto.num_params > proto.max_stack_size:
        raise ValueError("Function parameters exceed max stack size")

    code_count = len(proto.codes)
    for pc, inst in enumerate(proto.codes):
        opcode = inst.opcode
        if opcode.mode == OpMode.iABC:
            a, b, c = inst.abc()
            uses_a_register = inst.op_name() not in ("RETURN", "CLOSE") or b != 1
            if uses_a_register and a >= proto.max_stack_size:
                raise ValueError(f"Invalid destination register at instruction {pc + 1}")
            for label, mode, operand in (("B", opcode.argb, b), ("C", opcode.argc, c)):
                if mode == OpArgR and operand >= proto.max_stack_size:
                    raise ValueError(f"Invalid register {label} at instruction {pc + 1}")
                if mode == OpArgK:
                    _validate_rk(proto, operand, pc, label)

            if inst.op_name() in ("GETUPVAL", "SETUPVAL") and b >= proto.num_upvalues:
                raise ValueError(f"Invalid upvalue index at instruction {pc + 1}")
            if inst.op_name() == "LOADNIL" and b >= proto.max_stack_size:
                raise ValueError(f"Invalid LOADNIL range at instruction {pc + 1}")
            if inst.op_name() == "SELF" and a + 1 >= proto.max_stack_size:
                raise ValueError(f"Invalid SELF register range at instruction {pc + 1}")
            if inst.op_name() == "CONCAT" and (
                b >= proto.max_stack_size or c >= proto.max_stack_size or b > c
            ):
                raise ValueError(f"Invalid CONCAT range at instruction {pc + 1}")
            if (
                inst.op_name() in ("CALL", "TAILCALL")
                and b != 0
                and a + b - 1 > proto.max_stack_size
            ):
                raise ValueError(f"Invalid call register range at instruction {pc + 1}")
            if inst.op_name() == "RETURN" and b > 1 and a + b - 1 > proto.max_stack_size:
                raise ValueError(f"Invalid return register range at instruction {pc + 1}")
            if inst.op_name() == "TFORLOOP" and a + 5 >= proto.max_stack_size:
                raise ValueError(f"Invalid TFORLOOP register range at instruction {pc + 1}")
            if inst.op_name() == "SETLIST" and b != 0 and a + b >= proto.max_stack_size:
                raise ValueError(f"Invalid SETLIST register range at instruction {pc + 1}")
            if inst.op_name() == "VARARG" and b > 1 and a + b - 2 >= proto.max_stack_size:
                raise ValueError(f"Invalid VARARG register range at instruction {pc + 1}")
        elif opcode.mode == OpMode.iABx:
            a, bx = inst.abx()
            if a >= proto.max_stack_size:
                raise ValueError(f"Invalid destination register at instruction {pc + 1}")
            if inst.op_name() in ("LOADK", "GETGLOBAL", "SETGLOBAL"):
                if bx >= len(proto.consts):
                    raise ValueError(f"Invalid constant index at instruction {pc + 1}")
                if inst.op_name() != "LOADK" and not proto.consts[bx].is_string():
                    raise ValueError(f"Global name must be a string at instruction {pc + 1}")
            elif inst.op_name() == "CLOSURE" and bx >= len(proto.protos):
                raise ValueError(f"Invalid prototype index at instruction {pc + 1}")
        elif opcode.mode == OpMode.iAsBx:
            a, sbx = inst.asbx()
            if inst.op_name() in ("FORLOOP", "FORPREP") and a + 3 >= proto.max_stack_size:
                raise ValueError(f"Invalid numeric-for register range at instruction {pc + 1}")
            if inst.op_name() == "JMP" and a > proto.max_stack_size:
                raise ValueError(f"Invalid JMP close register at instruction {pc + 1}")
            target = pc + 1 + sbx
            if target < 0 or target > code_count:
                raise ValueError(f"Invalid jump target at instruction {pc + 1}")

    for child in proto.protos:
        validate_proto(child)
