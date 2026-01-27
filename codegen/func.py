from __future__ import annotations

from typing import TypeAlias, TYPE_CHECKING

if TYPE_CHECKING:
    from structs.instruction import Instruction
    from lua_function import Proto, LocalVar

Const: TypeAlias = int | float | str | bool


class LocalVarInfo:
    name: str
    reg_idx: int
    scope_depth: int

    def __init__(self, name: str, reg_idx: int, scope_depth: int):
        self.name = name
        self.reg_idx = reg_idx
        self.scope_depth = scope_depth

    def to_local_var(self) -> LocalVar:
        from lua_function import LocalVar
        local_var = LocalVar()
        local_var.name = self.name
        local_var.start_pc = 0
        local_var.end_pc = 0
        return local_var


class UpvalueInfo:
    name: str
    loc_idx: int | None
    upval_idx: int | None
    idx: int

    def __init__(self, name: str, loc_idx: int | None, upval_idx: int | None, idx: int):
        self.name = name
        self.loc_idx = loc_idx
        self.upval_idx = upval_idx
        self.idx = idx


class FuncInfo:
    parent: FuncInfo | None
    sub_funcs: list[FuncInfo]

    num_params: int
    is_vararg: bool

    constants: list[Const]
    used_regs: int
    max_regs: int
    scope_depth: int

    loc_vars: list[LocalVarInfo]
    loc_names: dict[str, LocalVarInfo]
    upval_names: dict[str, UpvalueInfo]

    insts: list[Instruction]

    def __init__(self, parent: FuncInfo | None = None):
        self.parent = parent
        self.sub_funcs = []
        self.num_params = 0
        self.is_vararg = False
        self.scope_depth = 0
        self.loc_vars = []
        self.loc_names = {}
        self.upval_names = {}
        self.insts = []
        self.constants = []
        self.used_regs = 0
        self.max_regs = 0

    def to_proto(self) -> Proto:
        from lua_function import Proto, Debug
        from lua_value import Value
        proto = Proto()
        # proto.source = source
        proto.num_params = self.num_params
        proto.is_vararg = self.is_vararg
        proto.max_stack_size = self.max_regs
        proto.codes = self.insts.copy()
        for const in self.constants:
            proto.consts.append(Value(const))
        proto.protos = [sub.to_proto() for sub in self.sub_funcs]

        # Debug info
        debug = Debug()
        for local_var in self.loc_vars:
            debug.loc_vars.append(local_var.to_local_var())
        # debug.upvalues = list(self.upval_names.values())
        proto.debug = debug

        return proto

    def idx_of_const(self, const: Const) -> int:
        """Get index of constant, adding it if not present."""
        if const in self.constants:
            return self.constants.index(const)
        else:
            self.constants.append(const)
            return len(self.constants) - 1

    def idx_of_upval(self, name: str) -> int | None:
        """Get index of upvalue, adding it if not present."""
        if name in self.upval_names:
            return self.upval_names[name].idx

        loc_idx = None
        upval_idx = None
        if self.parent:
            loc_var = self.parent.get_local_var(name)
            if loc_var:
                loc_idx = loc_var.reg_idx
            else:
                upval_idx = self.parent.idx_of_upval(name)
        if loc_idx is not None or upval_idx is not None:
            upval_info = UpvalueInfo(name, loc_idx, upval_idx, len(self.upval_names))
            self.upval_names[name] = upval_info
            return upval_info.idx

        return None

    def alloc_reg(self) -> int:
        assert self.used_regs < 255, "Exceeded maximum register limit"
        self.used_regs += 1
        self.max_regs = max(self.max_regs, self.used_regs)
        return self.used_regs - 1

    def free_reg(self) -> None:
        assert self.used_regs > 0, "No registers to free"
        self.used_regs -= 1

    def alloc_regs(self, n: int) -> int:
        for _ in range(n):
            self.alloc_reg()
        return self.used_regs - n

    def free_regs(self, n: int) -> None:
        for _ in range(n):
            self.free_reg()

    def enter_scope(self) -> None:
        """Enter a new variable scope."""
        self.scope_depth += 1

    def exit_scope(self) -> None:
        """Exit the current variable scope."""
        assert self.scope_depth > 0, "No scope to exit"
        self.scope_depth -= 1

    def add_local_var(self, name: str) -> LocalVarInfo:
        """Add a new local variable to the current scope."""
        reg_idx = self.alloc_reg()
        local_var = LocalVarInfo(name, reg_idx, self.scope_depth)
        self.loc_vars.append(local_var)
        self.loc_names[name] = local_var
        return local_var

    def remove_local_var(self, name: str) -> None:
        """Remove a local variable from the current scope."""
        local_var = self.loc_names.get(name)
        if local_var and local_var.scope_depth == self.scope_depth:
            self.loc_vars.remove(local_var)
            del self.loc_names[name]
            self.free_reg()

    def get_local_var(self, name: str) -> LocalVarInfo | None:
        """Get local variable info by name."""
        return self.loc_names.get(name)

    def get_upval_info(self, name: str) -> UpvalueInfo | None:
        """Get upvalue info by name."""
        return self.upval_names.get(name)

    def emit_abc(self, opcode: int, a: int, b: int, c: int) -> None:
        from structs.instruction import Instruction
        """Emit an ABC format instruction."""
        inst = (opcode & 0x3F) | ((a & 0xFF) << 6) | ((b & 0x1FF) << 23) | ((c & 0x1FF) << 14)
        self.insts.append(Instruction(inst))

    def emit_abx(self, opcode: int, a: int, bx: int) -> None:
        from structs.instruction import Instruction
        """Emit an ABx format instruction."""
        inst = (opcode & 0x3F) | ((a & 0xFF) << 6) | ((bx & 0x3FFFF) << 14)
        self.insts.append(Instruction(inst))

    def emit_asbx(self, opcode: int, a: int, sbx: int) -> None:
        from structs.instruction import Instruction
        """Emit an AsBx format instruction."""
        bias = 131071  # 2^18 - 1
        inst = (opcode & 0x3F) | ((a & 0xFF) << 6) | (((sbx + bias) & 0x3FFFF) << 14)
        self.insts.append(Instruction(inst))

    def emit_ax(self, opcode: int, ax: int) -> None:
        from structs.instruction import Instruction
        """Emit an Ax format instruction."""
        inst = (opcode & 0x3F) | ((ax & 0x3FFFFFF) << 6)
        self.insts.append(Instruction(inst))

    def current_pc(self) -> int:
        """Get the current program counter (instruction index)."""
        return len(self.insts)

    def __str__(self) -> str:
        """Generate a human-readable representation of the function info."""
        lines: list[str] = []
        lines.append(f"Function ({len(self.insts)} instructions)")
        lines.append(f"{self.num_params} params, {self.max_regs} slots, "
                     f"{len(self.upval_names)} upvalues, {len(self.loc_vars)} locals, "
                     f"{len(self.constants)} constants, {len(self.sub_funcs)} functions")

        # Instructions
        for i, inst in enumerate(self.insts, 1):
            lines.append(f'\t{i}\t{inst}')

        # Constants
        if self.constants:
            lines.append(f"constants ({len(self.constants)}):")
            for i, const in enumerate(self.constants, 1):
                if isinstance(const, str):
                    lines.append(f'\t{i}\t"{const}"')
                else:
                    lines.append(f'\t{i}\t{const}')

        # Locals
        if self.loc_vars:
            lines.append(f"locals ({len(self.loc_vars)}):")
            for i, var in enumerate(self.loc_vars):
                lines.append(f'\t{i}\t{var.name}\treg={var.reg_idx}\tscope={var.scope_depth}')

        # Up values
        if self.upval_names:
            lines.append(f"upvalues ({len(self.upval_names)}):")
            for name, info in self.upval_names.items():
                lines.append(f'\t{info.idx}\t{name}')

        # Sub-functions
        if self.sub_funcs:
            lines.append(f"\n--- Sub-functions ({len(self.sub_funcs)}) ---")
            for i, sub in enumerate(self.sub_funcs):
                lines.append(f"\n[{i}] {sub}")

        return '\n'.join(lines)
