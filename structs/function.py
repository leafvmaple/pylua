from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeAlias

from structs.instruction import Instruction

if TYPE_CHECKING:
    from vm.state import LuaState
    from structs.value import Value
    PyFunction: TypeAlias = Callable[[LuaState], int]


class LocalVar:
    name: str
    start_pc: int
    end_pc: int

    def __str__(self) -> str:
        return f"{self.name}\t{self.start_pc + 1}\t{self.end_pc + 1}"


class Debug:
    line_infos: list[int]
    loc_vars: list[LocalVar]
    upvalues: list[str]

    def __init__(self):
        self.line_infos = []
        self.loc_vars = []
        self.upvalues = []

    def __str__(self) -> str:
        parts: list[str] = []
        parts.append(f'locals ({len(self.loc_vars)}):')
        parts.extend(f"\t{i}\t{value}" for i, value in enumerate(self.loc_vars))

        parts.append(f'upvalues ({len(self.upvalues)}):')
        parts.extend(f"\t{i}\t{value}" for i, value in enumerate(self.upvalues))

        return '\n'.join(parts)


class Proto:
    source: str
    type: str = "main"
    line_defined: int
    last_line_defined: int
    num_upvalues: int
    num_params: int
    is_vararg: bool
    max_stack_size: int
    codes: list[Instruction]
    consts: list[Value]
    protos: list[Proto]
    debug: Debug

    def __init__(self) -> None:
        self.source = ""
        self.line_defined = 0
        self.last_line_defined = 0
        self.num_upvalues = 0
        self.num_params = 0
        self.is_vararg = False
        self.max_stack_size = 0
        self.codes = []
        self.consts = []
        self.protos = []
        self.debug = Debug()

    def __str__(self) -> str:
        parts: list[str] = []
        parts.append(f"{self.type} <{self.source}:{self.line_defined},{self.last_line_defined}> ({len(self.codes)} instructions)")
        parts.append(f"{self.num_params} params, {self.max_stack_size} slots, {len(self.debug.upvalues)} upvalues, \
                     {len(self.debug.loc_vars)} locals, {len(self.consts)} constants, {len(self.protos)} functions")
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
    num_rets: int  # number of expected return values
    ret_idx: int
    pc: int

    def __init__(self, func: Proto):
        from structs.value import Value
        self.stack = [Value.nil()] * func.max_stack_size
        self.upvalues = [Value.nil()] * func.num_upvalues
        # Initialize upvalues based on function prototype
        self.varargs = []
        self.func = func
        self.num_rets = 0
        self.pc = 0

    @classmethod
    def from_proto(cls, func: Proto):
        return cls(func)

    def fetch(self) -> Instruction | None:
        if self.pc >= len(self.func.codes):
            return None
        instruction = self.func.codes[self.pc]
        self.pc += 1
        return instruction

    # debug
    def print_stack(self):
        pass


class PClosure(Closure):
    func: PyFunction

    def __init__(self, func: PyFunction):
        self.func = func
        self.stack = []
        self.upvalues = []

    @classmethod
    def from_function(cls, func: PyFunction):
        return cls(func)
