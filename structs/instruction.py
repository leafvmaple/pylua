from __future__ import annotations
from typing import TYPE_CHECKING
from codegen.inst import OpCode, OPCODES, iABC, iABx, iAsBx, OpArgN, OpArgK

if TYPE_CHECKING:
    from structs.value import Value


def a_to_bitset(a: int) -> int:
    return (a & 0xFF) << 6


def b_to_bitset(b: int) -> int:
    return (b & 0x1FF) << 23


def c_to_bitset(c: int) -> int:
    return (c & 0x1FF) << 14


def bx_to_bitset(bx: int) -> int:
    return (bx & 0x3FFFF) << 14


def sbx_to_bitset(sbx: int) -> int:
    bias = 0x3FFFF >> 1
    return ((sbx + bias) & 0x3FFFF) << 14


def bitset_to_abc(instruction: int) -> tuple[int, int, int]:
    """Decode instruction into A, B, C arguments."""
    a = (instruction >> 6) & 0xFF
    c = (instruction >> 14) & 0x1FF
    b = (instruction >> 23) & 0x1FF
    return a, b, c


def bitset_to_abx(instruction: int) -> tuple[int, int]:
    """Decode instruction into A, Bx arguments."""
    a = (instruction >> 6) & 0xFF
    bx = (instruction >> 14) & 0x3FFFF
    return a, bx


def bitset_to_asbx(instruction: int) -> tuple[int, int]:
    """Decode instruction into A, sBx arguments."""
    a = (instruction >> 6) & 0xFF
    bx = (instruction >> 14) & 0x3FFFF
    sbx = bx - (0x3FFFF >> 1)  # signed Bx (convert 18-bit unsigned to signed)
    return a, sbx


class Instruction:
    _opcode_idx: int
    _opcode: OpCode
    _a: int
    _b: int | None
    _c: int | None
    _bx: int | None
    _sbx: int | None
    _args: list[int]
    _comment: list[str]

    bias = 131071  # 2^18 - 1

    def __init__(self, instruction: int | None = None,
                 code_idx: int | None = None, a: int | None = None,
                 b: int | None = None, c: int | None = None,
                 bx: int | None = None,
                 sbx: int | None = None):
        self._args = []
        self._comment = []

        if instruction is not None:
            self._opcode_idx = instruction & 0x3F
            self._opcode = OPCODES[self._opcode_idx]
            if self._opcode.mode == iABC:
                self._a, self._b, self._c = bitset_to_abc(instruction)
            elif self._opcode.mode == iABx:
                self._a, self._bx = bitset_to_abx(instruction)
            elif self._opcode.mode == iAsBx:
                self._a, self._sbx = bitset_to_asbx(instruction)
        else:
            assert code_idx is not None and a is not None, "Must provide code_idx and a when instruction is None"
            self._opcode = OPCODES[self._opcode_idx]
            if b is not None and c is not None:
                self._opcode_idx = code_idx
                self._a = a
                self._b = b
                self._c = c
            elif bx is not None:
                self._opcode_idx = code_idx
                self._a = a
                self._bx = bx
            elif sbx is not None:
                self._opcode_idx = code_idx
                self._a = a
                self._sbx = sbx

    @classmethod
    def from_abc(cls, opcode_idx: int, a: int, b: int, c: int) -> Instruction:
        return cls(code_idx=opcode_idx, a=a, b=b, c=c)

    @classmethod
    def from_abx(cls, opcode_idx: int, a: int, bx: int) -> Instruction:
        return cls(code_idx=opcode_idx, a=a, bx=bx)

    @classmethod
    def from_asbx(cls, opcode_idx: int, a: int, sbx: int) -> Instruction:
        return cls(code_idx=opcode_idx, a=a, sbx=sbx)

    def op_name(self) -> str:
        return self._opcode.name

    def abc(self) -> tuple[int, int, int]:
        """Return A, B, C arguments, with None as default for missing values."""
        assert type(self._b) is int and type(self._c) is int, "Instruction is not in ABC format"
        return self._a, self._b, self._c

    def abx(self) -> tuple[int, int]:
        assert type(self._bx) is int, "Instruction is not in ABx format"
        return self._a, self._bx

    def asbx(self) -> tuple[int, int]:
        assert type(self._sbx) is int, "Instruction is not in ABx format"
        return self._a, self._sbx

    def set_sbx(self, sbx: int) -> None:
        assert self._opcode.mode == iAsBx, "Instruction is not in ABx format"
        self._sbx = sbx

    def _append_arg(self, arg_type: int, value: int, constants: list[Value]):
        """Get argument representation based on its type."""
        if arg_type != OpArgN:
            if arg_type == OpArgK and value > 255:
                self._comment.append(str(constants[value - 256]))
                value = 255 - value
            self._args.append(value)

    def update_info(self, pc: int, constants: list[Value], upvalues: list[str]):
        """Update instruction arguments with constant/upvalue info."""
        self._args.append(self._a)

        if self._opcode.mode == iABC:
            assert type(self._b) is int and type(self._c) is int, "Instruction is not in ABC format"
            self._append_arg(self._opcode.argb, self._b, constants)
            self._append_arg(self._opcode.argc, self._c, constants)
        elif self._opcode.mode == iABx:
            assert type(self._bx) is int, "Instruction is not in ABx format"
            if self._opcode.name in ["LOADK", "GETGLOBAL", "SETGLOBAL"]:
                self._comment.append(str(constants[self._bx]))
                self._args.append(-(self._bx + 1))
            else:
                self._args.append(self._bx)
        elif self._opcode.mode == iAsBx:
            assert type(self._sbx) is int, "Instruction is not in ABx format"
            self._args.append(self._sbx)
            self._comment.append(f"to {self._sbx + pc + 2}")

        # Special handling for specific opcodes
        if self._opcode.name in ["GETUPVAL", "SETUPVAL"]:
            if self._args[1] < len(upvalues):
                self._comment.append(upvalues[self._args[1]])

    def to_bitset(self) -> int:
        """Convert instruction back to its 32-bit integer representation."""
        if self._opcode.mode == iABC:
            return (self._opcode_idx & 0x3F) | a_to_bitset(self._a) | b_to_bitset(self._b or 0) | c_to_bitset(self._c or 0)
        elif self._opcode.mode == iABx:
            return (self._opcode_idx & 0x3F) | a_to_bitset(self._a) | bx_to_bitset(self._bx or 0)
        elif self._opcode.mode == iAsBx:
            return (self._opcode_idx & 0x3F) | a_to_bitset(self._a) | sbx_to_bitset(self._sbx or 0)
        else:
            raise ValueError("Invalid opcode mode")

    def __str__(self) -> str:
        parts = [self._opcode.name.ljust(10)]
        if self._args:
            parts.append(' '.join(str(arg) for arg in self._args))
            if self._comment:
                parts.append(f"; {' '.join(self._comment)}")
        else:
            parts.append(f"a = {self._a}")
            if self._opcode.mode == iABC:
                parts.append(f"b = {self._b}")
                parts.append(f"c = {self._c}")
            elif self._opcode.mode == iABx:
                parts.append(f"bx = {self._bx}")
            elif self._opcode.mode == iAsBx:
                parts.append(f"sbx = {self._sbx}")

        return '\t'.join(parts)

    def __repr__(self):
        return f"<Instruction {self._opcode.name} 0x{self.to_bitset():08X}>"
