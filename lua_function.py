from __future__ import annotations

from typing import TYPE_CHECKING

from structs.instruction import Instruction

if TYPE_CHECKING:
    from lua_value import Value


class LocalVar:
    name: str
    startpc: int
    endpc: int

    def __str__(self) -> str:
        return f"{self.name}\t{self.startpc + 1}\t{self.endpc + 1}"


class Debug:
    lineinfos: list[int]
    locvars: list[LocalVar]
    upvalues: list[str]

    def __str__(self) -> str:
        parts = []
        parts.append(f'locals ({len(self.locvars)}):')
        parts.extend(f"\t{i}\t{value}" for i, value in enumerate(self.locvars))

        parts.append(f'upvalues ({len(self.upvalues)}):')
        parts.extend(f"\t{i}\t{value}" for i, value in enumerate(self.upvalues))

        return '\n'.join(parts)


class Proto:
    source: str
    type: str = "main"
    linedefined: int
    lastlinedefined: int
    nups: int
    numparams: int
    is_vararg: bool
    maxstacksize: int
    codes: list[Instruction]
    consts: list[Value]
    protos: list[Proto]
    debug: Debug

    def __str__(self) -> str:
        parts = []
        parts.append(f"{self.type} <{self.source}:{self.linedefined},{self.lastlinedefined}> ({len(self.codes)} instructions)")
        parts.append(f"{self.numparams} params, {self.maxstacksize} slots, {len(self.debug.upvalues)} upvalues, \
                     {len(self.debug.locvars)} locals, {len(self.consts)} constants, {len(self.protos)} functions")
        parts.extend(f"\t{pc + 1}\t{code}" for pc, code in enumerate(self.codes))
        parts.append(f'constants ({len(self.consts)}):')
        parts.extend(f"\t{i + 1}\t{value}" for i, value in enumerate(self.consts))
        parts.append(str(self.debug))
        parts.extend(str(sub) for sub in self.protos)

        return '\n' + '\n'.join(parts)


class Closure:
    stack: list[Value]
    upvalues: list[Value]


class LClosure(Closure):
    varargs: list[Value]
    func: Proto
    nrets: int  # number of expected return values
    ret_idx: int
    pc: int

    def __init__(self, func: Proto):
        from lua_value import Value
        self.stack = [Value()] * func.maxstacksize
        self.upvalues = [Value()] * func.nups  # Initialize upvalues based on function prototype
        self.varargs = []
        self.func = func
        self.nrets = 0
        self.pc = 0

    @classmethod
    def from_proto(cls, func: Proto):
        return cls(func)

    def fetch(self) -> Instruction | None:
        if self.pc >= len(self.func.codes):
            return None
        instrution = self.func.codes[self.pc]
        self.pc += 1
        return instrution

    # debug
    def print_stack(self):
        pass


class PClosure(Closure):
    func: callable

    def __init__(self, func: callable):
        self.func = func
        self.stack = []
        self.upvalues = []

    @classmethod
    def from_function(cls, func: callable):
        return cls(func)
