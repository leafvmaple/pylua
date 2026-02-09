"""Lua VM operators implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeAlias

from structs.instruction import Instruction
from structs.value import Value
from structs.table import Table
from structs.function import LClosure
from vm.protocols import LuaCheckable

if TYPE_CHECKING:
    from lua_state import LuaState


class CheckNumber(LuaCheckable):
    @staticmethod
    def check(val: Value) -> bool:
        return val.conv_str_to_number()

    @staticmethod
    def checks(va: Value, vb: Value) -> bool:
        return CheckNumber.check(va) and CheckNumber.check(vb)


class CompareCheck(LuaCheckable):
    @staticmethod
    def check(val: Value) -> bool:
        assert False, "CompareCheck.check should not be called"

    @staticmethod
    def checks(va: Value, vb: Value) -> bool:
        if va.is_number() and vb.is_number():
            return True
        if va.is_string() and vb.is_string():
            return True
        return False


UnaryFuncType: TypeAlias = Callable[[int | float | bool], int | float | bool]
BinaryFuncType: TypeAlias = Callable[[int | float, int | float], int | float]


class UnaryOperator:
    op: UnaryFuncType
    check: LuaCheckable
    meta: str

    def __init__(self, op: UnaryFuncType, check: LuaCheckable, meta: str):
        self.op = op
        self.meta = meta
        self.check = check

    def solve(self, L: LuaState, a: int) -> Value | bool:
        va = L.get_rk(a)
        mt = va.get_metatable()
        if self.check.check(va):
            assert isinstance(va.value, (int, float))
            return Value.number(self.op(va.value))
        else:
            if mt:
                meta_func = mt.get(Value.string(self.meta))
                if meta_func and meta_func.is_function():
                    assert type(meta_func.value) is LClosure
                    return L.lua_call(meta_func.value, va)
        return False

    def arith(self, L: LuaState, idx: int, a: int):
        res = self.solve(L, a)
        if res:
            assert type(res) is Value
            L.stack[idx] = res
        else:
            va = L.get_rk(a)
            raise TypeError(f"attempt to perform arithmetic on {va.type_name()}")


class BinaryOperator:
    op: BinaryFuncType
    check: LuaCheckable
    meta: str

    def __init__(self, op: BinaryFuncType, check: LuaCheckable, meta: str):
        self.op = op
        self.meta = meta
        self.check = check

    def solve(self, L: LuaState, a: int, b: int) -> Value | bool:
        va = L.get_rk(a)
        vb = L.get_rk(b)
        mt = va.get_metatable()
        if mt is None:
            mt = vb.get_metatable()
        if self.check.checks(va, vb):
            assert isinstance(va.value, (int, float)) and isinstance(vb.value, (int, float))
            return Value.number(self.op(va.value, vb.value))
        else:
            if mt:
                meta_func = mt.get(Value.string(self.meta))
                if meta_func and meta_func.is_function():
                    assert type(meta_func.value) is LClosure
                    return L.lua_call(meta_func.value, va, vb)
        return False
    
    def arith(self, L: LuaState, idx: int, a: int, b: int):
        res = self.solve(L, a, b)
        if type(res) is Value:
            L.stack[idx] = res
        else:
            va = L.stack[a]
            vb = L.stack[b]
            raise TypeError(f"attempt to perform arithmetic on {va.type_name()} and {vb.type_name()}")

    def compare(self, L: LuaState, a: int, b: int) -> bool:
        res = self.solve(L, a, b)
        if type(res) is Value:
            return bool(res.value)
        return False


UNARY_ARITH = {
    "UNM": UnaryOperator(lambda a: -a, CheckNumber, "__unm"),
    "BONA": UnaryOperator(lambda a: not a, CheckNumber, "__bnot")
}


BINARY_ARITH = {
    "ADD": BinaryOperator(lambda a, b: a + b, CheckNumber, "__add"),
    "SUB": BinaryOperator(lambda a, b: a - b, CheckNumber, "__sub"),
    "MUL": BinaryOperator(lambda a, b: a * b, CheckNumber, "__mul"),
    "DIV": BinaryOperator(lambda a, b: a / b, CheckNumber, "__div"),
    "MOD": BinaryOperator(lambda a, b: a % b, CheckNumber, "__mod"),
    "POW": BinaryOperator(lambda a, b: a ** b, CheckNumber, "__pow"),

    "EQ": BinaryOperator(lambda a, b: a == b, CompareCheck, "__eq"),
    "LT": BinaryOperator(lambda a, b: a < b, CompareCheck, "__lt"),
    "LE": BinaryOperator(lambda a, b: a <= b, CompareCheck, "__le"),
}


class Operator:
    @staticmethod
    def MOVE(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        state.stack[a] = state.stack[b]

    @staticmethod
    def LOADK(inst: Instruction, state: LuaState):
        a, bx = inst.abx()
        state.stack[a] = state.func.consts[bx]

    @staticmethod
    def LOADBOOL(inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        state.stack[a] = Value.boolean(bool(b))
        if c != 0:
            assert type(state.call_info[-1]) is LClosure
            state.call_info[-1].pc += 1

    @staticmethod
    def LOADNIL(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        for i in range(a, b + 1):
            state.stack[i] = Value.nil()

    @staticmethod
    def GETUPVAL(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        closure = state.call_info[-1]
        if b < len(closure.upvalues):
            state.stack[a] = closure.upvalues[b]
        else:
            state.stack[a] = Value.nil()

    @staticmethod
    def GETGLOBAL(inst: Instruction, state: LuaState):
        a, bx = inst.abx()
        name = state.func.consts[bx].value
        assert type(name) is str
        state.stack[a] = state.get_global(name)

    @staticmethod
    def GETTABLE(inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        table_value = state.stack[b]
        key = state.get_rk(c)
        if table_value.is_table():
            result = state.gettable(b, key)
            state.stack[a] = result
        else:
            state.stack[a] = Value.nil()

    @staticmethod
    def SETGLOBAL(inst: Instruction, state: LuaState):
        a, bx = inst.abx()
        name = state.func.consts[bx].value
        assert type(name) is str
        state.set_global(name, state.stack[a])

    @staticmethod
    def SETUPVAL(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        closure = state.call_info[-1]
        if b < len(closure.upvalues):
            closure.upvalues[b] = state.stack[a]
        else:
            raise IndexError(f"upvalue index {b} out of range (max {len(closure.upvalues)})")

    @staticmethod
    def SETTABLE(inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        table_value = state.stack[a]
        key = state.get_rk(b)
        value = state.get_rk(c)
        if table_value.is_table():
            assert isinstance(table_value.value, Table)
            table_value.value.set(key, value)
        else:
            # Try __newindex metamethod
            mt = table_value.get_metatable()
            if mt:
                newindex = mt.get(Value.string("__newindex"))
                if newindex and newindex.is_function():
                    state.lua_call(newindex.value, table_value, key, value)
                    return
            raise TypeError(f"attempt to index a {table_value.type_name()} value")

    @staticmethod
    def NEWTABLE(inst: Instruction, state: LuaState):
        a, _, _ = inst.abc()
        state.stack[a] = Value.table(Table())

    @staticmethod
    def SELF(inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        state.stack[a + 1] = state.stack[b]
        key = state.get_rk(c)
        result = state.gettable(b, key)
        state.stack[a] = result

    @staticmethod
    def _arith_op(name: str, inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        BINARY_ARITH[name].arith(state, a, b, c)

    @staticmethod
    def ADD(inst: Instruction, state: LuaState):
        Operator._arith_op("ADD", inst, state)

    @staticmethod
    def SUB(inst: Instruction, state: LuaState):
        Operator._arith_op("SUB", inst, state)

    @staticmethod
    def MUL(inst: Instruction, state: LuaState):
        Operator._arith_op("MUL", inst, state)

    @staticmethod
    def DIV(inst: Instruction, state: LuaState):
        Operator._arith_op("DIV", inst, state)

    @staticmethod
    def MOD(inst: Instruction, state: LuaState):
        Operator._arith_op("MOD", inst, state)

    @staticmethod
    def POW(inst: Instruction, state: LuaState):
        Operator._arith_op("POW", inst, state)

    @staticmethod
    def UNM(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        UNARY_ARITH["UNM"].arith(state, a, b)

    @staticmethod
    def NOT(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        state.stack[a] = Value.boolean(not state.stack[b].get_boolean())

    @staticmethod
    def LEN(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        state.stack[a] = Value.number(state.len(b))

    @staticmethod
    def CONCAT(inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        parts: list[str] = []
        for i in range(b, c + 1):
            val = state.stack[i]
            s = val.get_string()
            if s is not None:
                parts.append(s)
        state.stack[a] = Value.string(''.join(parts))

    @staticmethod
    def JMP(inst: Instruction, state: LuaState):
        _, sbx = inst.asbx()
        state.jump(sbx)

    @staticmethod
    def _compare_op(name: str, inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        if BINARY_ARITH[name].compare(state, b, c) == (a != 0):
            next_inst = state.fetch()
            assert type(next_inst) is Instruction and next_inst.op_name() == "JMP"
            Operator.JMP(next_inst, state)
        else:
            assert type(state.call_info[-1]) is LClosure
            state.call_info[-1].pc += 1

    @staticmethod
    def EQ(inst: Instruction, state: LuaState):
        Operator._compare_op("EQ", inst, state)

    @staticmethod
    def LT(inst: Instruction, state: LuaState):
        Operator._compare_op("LT", inst, state)

    @staticmethod
    def LE(inst: Instruction, state: LuaState):
        Operator._compare_op("LE", inst, state)

    @staticmethod
    def TEST(inst: Instruction, state: LuaState):
        a, _, c = inst.abc()
        if state.stack[a].get_boolean() == bool(c):
            state.jump(1)

    @staticmethod
    def TESTSET(inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        if state.stack[b].get_boolean() == (c != 0):
            assert type(state.call_info[-1]) is LClosure
            state.call_info[-1].pc += 1
        else:
            state.stack[a] = state.stack[b]
            state.jump(1)

    @staticmethod
    def CALL(inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        nargs = b - 1 if b != 0 else len(state.stack) - a - 1
        num_rets = c - 1
        state.call(a, nargs, num_rets)

    @staticmethod
    def TAILCALL(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        nargs = b - 1 if b != 0 else len(state.stack) - a - 1
        state.call(a, nargs, -1)

    @staticmethod
    def RETURN(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        ret_count = b - 1 if b != 0 else len(state.stack) - a
        state.pos_call(a, ret_count)

    @staticmethod
    def FORLOOP(inst: Instruction, state: LuaState):
        a, sbx = inst.asbx()
        step = state.stack[a + 2]
        idx = state.stack[a]
        assert isinstance(idx.value, (int, float))
        assert isinstance(step.value, (int, float))
        new_idx = Value.number(idx.value + step.value)
        state.stack[a] = new_idx
        limit = state.stack[a + 1]
        assert isinstance(limit.value, (int, float))

        if (step.value > 0 and new_idx.value <= limit.value) or \
           (step.value <= 0 and new_idx.value >= limit.value):
            state.jump(sbx)
            state.stack[a + 3] = new_idx

    @staticmethod
    def FORPREP(inst: Instruction, state: LuaState):
        a, sbx = inst.asbx()
        init = state.stack[a]
        step = state.stack[a + 2]
        assert isinstance(init.value, (int, float))
        assert isinstance(step.value, (int, float))
        state.stack[a] = Value.number(init.value - step.value)
        state.jump(sbx)

    @staticmethod
    def TFORLOOP(inst: Instruction, state: LuaState):
        a, _, c = inst.abc()
        state.stack[a + 3] = state.stack[a]
        state.stack[a + 4] = state.stack[a + 1]
        state.stack[a + 5] = state.stack[a + 2]
        state.call(a + 3, 2, c)
        if not state.stack[a + 3].is_nil():
            state.stack[a + 2] = state.stack[a + 3]
        else:
            state.jump(1)

    @staticmethod
    def SETLIST(inst: Instruction, state: LuaState):
        a, b, c = inst.abc()
        table = state.stack[a]
        if not table.is_table():
            raise TypeError("SETLIST expects a table")
        assert type(table.value) is Table

        n = b if b != 0 else len(state.stack) - a - 1
        base = (c - 1) * 50

        for i in range(1, n + 1):
            table.value.set(base + i, state.stack[a + i])

    @staticmethod
    def CLOSE(inst: Instruction, state: LuaState):
        pass

    @staticmethod
    def CLOSURE(inst: Instruction, state: LuaState):
        a, bx = inst.abx()
        proto = state.func.protos[bx]
        closure = LClosure.from_proto(proto)
        state.stack[a] = Value.closure(closure)

    @staticmethod
    def VARARG(inst: Instruction, state: LuaState):
        a, b, _ = inst.abc()
        closure = state.call_info[-1]
        assert type(closure) is LClosure
        n = b - 1 if b != 0 else len(closure.varargs)
        for i in range(n):
            if i < len(closure.varargs):
                state.stack[a + i] = closure.varargs[i]
            else:
                state.stack[a + i] = Value.nil()


# Pre-built dispatch table for O(1) opcode lookup instead of getattr
DISPATCH_TABLE: dict[str, Callable] = {
    name: getattr(Operator, name)
    for name in dir(Operator)
    if not name.startswith('_') and callable(getattr(Operator, name))
}
