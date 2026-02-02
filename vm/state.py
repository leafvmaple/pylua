from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from vm.operator import Operator
from structs.instruction import Instruction
from structs.value import Value
from structs.table import Table
from structs.function import LClosure, PClosure, Proto
from vm.builtins import BUILTIN

if TYPE_CHECKING:
    from structs.function import PyFunction

LUA_REGISTRY_INDEX = -10000
LUA_GLOBALS_INDEX = -10002


LUA_OK = 0
LUA_YIELD = 1
LUA_ERR_RUN = 2
LUA_ERR_SYNTAX = 3
LUA_ERR_MEM = 4
LUA_ERR_ERR = 5


class LuaState:
    call_info: list[LClosure | PClosure]
    func: Proto
    stack: list[Value]
    registry: Table
    globals: Table

    # Global
    mt: Table

    def __init__(self, main: Proto):
        call_info = LClosure.from_proto(main)
        self.registry = Table()
        key = Value.number(LUA_GLOBALS_INDEX)

        self.globals = Table()
        self.registry.set(key, Value.table(self.globals))
        self.mt = Table()
        self.call_info = [call_info]  # Pass Value as factory
        self.func = call_info.func
        self.stack = call_info.stack

        # Register built-in functions
        self.register("print", BUILTIN.lua_print)
        self.register("getmetatable", BUILTIN.lua_getmetatable)
        self.register("setmetatable", BUILTIN.lua_setmetatable)
        self.register("next", BUILTIN.lua_next)
        self.register("ipairs", BUILTIN.lua_ipairs)
        self.register("pairs", BUILTIN.lua_pairs)
        self.register("error", BUILTIN.lua_error)
        self.register("pcall", BUILTIN.lua_pcall)

    def get_global(self, name: str) -> Value:
        key = Value.string(name)
        value = self.globals.get(key)
        return value if value is not None else Value.nil()

    def set_global(self, name: str, value: Value):
        key = Value.string(name)
        self.globals.set(key, value)

    def push_closure(self, closure: LClosure | PClosure):
        self.call_info.append(closure)
        if type(closure) is LClosure:
            self.func = closure.func
        # Always switch to closure's stack, regardless of type
        self.stack = closure.stack

    def pop_closure(self) -> LClosure | PClosure:
        frame = self.call_info.pop()
        if self.call_info:
            call_info = self.call_info[-1]
            if type(call_info) is LClosure:
                self.func = call_info.func
            # Always restore stack from the current call_info
            self.stack = call_info.stack
        return frame

    def register(self, name: str, func: PyFunction):
        self.globals.set(Value.string(name), Value.closure(PClosure(func)))

    def _getmetatable(self, val: Value) -> Value | None:
        if val.is_table() or val.is_userdata():
            mt = val.get_metatable()
            return Value.table(mt) if mt else None
        else:
            return self.mt.get(Value.string(val.type_name()))

    # external meta methods
    def pop(self, n: int) -> None:
        for _ in range(n):
            self.stack.pop()

    def remove(self, idx: int) -> None:
        assert idx != 0, "Index cannot be zero"
        if idx < 0:
            self.stack.pop(idx)
        elif idx > 0:
            self.stack.pop(idx - 1)

    def gettop(self) -> int:
        return len(self.stack)

    def settop(self, idx: int):
        while len(self.stack) > idx:
            self.stack.pop()
        while len(self.stack) < idx:
            self.stack.append(Value.nil())

    def pushstring(self, s: str):
        self.stack.append(Value.string(s))

    def rawget(self, idx: int) -> None:
        t = self._index2adr(idx)
        if not t.is_table():
            raise TypeError("rawget expects a table")
        assert type(t.value) is Table

        key = self.stack[-1]
        value = t.value.get(key)
        if value is None:
            value = Value.nil()
        self.stack[-1] = value

    def getmetatable(self, idx: int) -> int:
        obj = self._index2adr(idx)
        mt = self._getmetatable(obj)
        if mt is None:
            return 0
        self.stack.append(mt)
        return 1

    def setmetatable(self, idx: int) -> None:
        obj = self._index2adr(idx)
        mt = self.stack[-1]
        if not mt.is_table():
            raise TypeError("setmetatable expects a table as metatable")
        assert type(mt.value) is Table

        if obj.is_table():
            assert type(obj.value) is Table
            obj.value.setmetatable(mt.value)
        else:
            self.mt.set(Value.string(obj.type_name()), mt)

    def getmetafield(self, idx: int, field: str) -> int:
        if self.getmetatable(idx) == 0:
            return 0
        self.pushstring(field)
        self.rawget(-2)
        if self.stack[-1].is_nil():
            self.pop(2)
            return 0
        self.remove(-2)
        return 1

    def gettable(self, idx: int, key: Value) -> Value:
        t = self.stack[idx]
        value = t.gettable(key, self.lua_call)
        return value if value is not None else Value.nil()

    def len(self, idx: int) -> int:
        t = self.stack[idx]
        return t.len(self.lua_call)

    def call(self, idx: int, nargs: int, num_rets: int):
        func_value = self.stack[idx]
        if func_value.is_function():
            if type(func_value.value) is LClosure:
                self.pre_call(func_value.value, idx, nargs, num_rets)
                while self.execute():
                    pass
            elif type(func_value.value) is PClosure:
                self.py_call(func_value.value, idx, nargs, num_rets)
        elif func_value.is_table():
            mt = func_value.get_metatable()
            func_value = mt.get(Value("__call")) if mt else None
            if func_value and func_value.is_function():
                assert type(func_value.value) is LClosure
                self.stack[idx] = self.lua_call(func_value.value, *self.stack[idx: idx + nargs + 1])
        else:
            raise TypeError("CALL error")

    def pcall(self, idx: int, nargs: int, num_rets: int) -> int:
        ci_len = len(self.call_info)
        try:
            self.call(idx, nargs, num_rets)
        except Exception as e:
            while len(self.call_info) > ci_len:
                self.pop_closure()
            self.stack.clear()
            self.pushvalue(Value.string(str(e)))
            if isinstance(e, RuntimeError):
                return LUA_ERR_RUN
            elif isinstance(e, SyntaxError):
                return LUA_ERR_SYNTAX
            elif isinstance(e, MemoryError):
                return LUA_ERR_MEM
            else:
                return LUA_ERR_ERR
        return LUA_OK

    def error(self):
        value = self.stack[-1]
        raise RuntimeError(value.value)

    def execute(self) -> bool:
        inst = self.fetch()
        if inst is None:
            return False
        op_name = inst.op_name()
        method = getattr(Operator, op_name, None)
        if method:
            # print(f"-{len(self.call_info)}- " + str(inst).ljust(40))
            method(inst, self)
            # print(
            #     f"-{len(self.call_info)}- "
            #     + ''.join(f"[{v}]" for v in self.stack)
            # )
        if op_name == "RETURN":
            return False
        return True

    def pre_call(self, closure: LClosure, func_idx: int = 0, nargs: int = 0, num_rets: int = 0):
        closure.stack = [Value.nil()] * closure.func.max_stack_size
        closure.pc = 0
        closure.varargs = []
        for i in range(nargs):
            value = self.stack[func_idx + 1 + i]
            if i < closure.func.num_params:
                closure.stack[i] = value
            else:
                closure.varargs.append(value)

        closure.num_rets = num_rets
        closure.ret_idx = func_idx
        self.push_closure(closure)

    def py_call(self, closure: PClosure, func_idx: int = 0, args_count: int = 0, num_rets: int = 0):
        closure.stack = []
        for i in range(args_count):
            value = self.stack[func_idx + 1 + i]
            closure.stack.append(value)

        self.push_closure(closure)
        ret_count = closure.func(self)
        self.pop_closure()

        ret_start = len(closure.stack) - ret_count

        for i in range(num_rets):
            ret_value = closure.stack[ret_start + i] if i < ret_count else Value.nil()
            self.stack[func_idx + i] = ret_value

    def pos_call(self, ret_start: int, ret_count: int = 0):
        closure = self.pop_closure()

        # Handle return values
        if ret_count == -1:
            ret_count = len(closure.stack) - ret_start

        if closure.num_rets == -1:
            closure.num_rets = ret_count

        for i in range(closure.num_rets):
            ret_value = closure.stack[ret_start + i] if i < ret_count else Value.nil()
            self.stack[closure.ret_idx + i] = ret_value

    def next(self, idx: int) -> Optional[tuple[Value, Value]]:
        table = self.stack[idx]
        key = self.stack[-1]
        if not table.is_table():
            raise TypeError("next expects a table")
        assert type(table.value) is Table
        return table.value.next(key)

    def pushpyfunction(self, func: PyFunction):
        self.stack.append(Value.closure(PClosure(func)))

    def pushvalue(self, val: Value):
        self.stack.append(val)

    def pushboolean(self, b: bool):
        self.stack.append(Value.boolean(b))

    def insert(self, idx: int):
        val = self.stack.pop()
        self.stack.insert(idx - 1, val)

    def pushnil(self):
        self.stack.append(Value.nil())

    def lua_call(self, func: LClosure, *args: Value) -> Value:
        nargs = len(args)
        func_idx = len(self.stack)
        self.stack.append(Value.closure(func))
        self.stack.extend(args)
        self.call(func_idx, nargs, 1)
        res = self.stack[func_idx]
        while len(self.stack) > func_idx:
            self.stack.pop()
        return res

    def get_rk(self, rk: int) -> Value:
        """Get RK value: constant index or register."""
        if rk >= 256:
            # It's a constant (k)
            return self.func.consts[rk - 256]
        else:
            # It's a register (r)
            return self.stack[rk]

    def _index2adr(self, idx: int) -> Value:
        """Convert Lua stack index to Value reference"""
        if idx > 0:
            return self.stack[idx - 1]
        elif idx > LUA_GLOBALS_INDEX:   # idx < 0
            return self.stack[len(self.stack) + idx]
        else:
            if idx == LUA_GLOBALS_INDEX:
                return Value.table(self.globals)
            elif idx == LUA_REGISTRY_INDEX:
                return Value.table(self.registry)
            raise IndexError("Invalid stack index")

    def jump(self, offset: int):
        assert len(self.call_info) > 0 and type(self.call_info[-1]) is LClosure
        self.call_info[-1].pc += offset

    def fetch(self) -> Optional[Instruction]:
        if self.call_info:
            assert type(self.call_info[-1]) is LClosure
            return self.call_info[-1].fetch()
        return None

    # debug
    def print_stack(self):
        pass
        # self.call_info[-1].print_stack()
