from __future__ import annotations

from typing import Optional
from lua_operator import Operator
from structs.instruction import Instruction
from lua_value import Value
from lua_table import Table
from lua_function import LClosure, PClosure, Proto
from lua_builtins import BUILTIN

LUA_REGISTRY_INDEX = -10000
LUA_GLOBALS_INDEX = -10002


LUA_OK = 0
LUA_YIELD = 1
LUA_ERRRUN = 2
LUA_ERRSYNTAX = 3
LUA_ERRMEM = 4
LUA_ERRERR = 5


class LuaState:
    call_info: list[LClosure | PClosure]
    func: Proto
    stack: list[Value]
    registry: Table
    globals: Table

    # Global
    mt: Table

    def __init__(self, main: Proto):
        self.call_info = [LClosure.from_proto(main)]  # Pass Value as factory
        self.registry = Table()
        key = Value.number(LUA_GLOBALS_INDEX)
        self.registry.set(key, Value.table(Table()))
        self.globals = self.registry.get(key).value
        self.mt = Table()

        self.func = self.call_info[-1].func
        self.stack = self.call_info[-1].stack

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
        self.func = self.call_info[-1].func
        self.stack = self.call_info[-1].stack

    def pop_closure(self) -> LClosure:
        frame = self.call_info.pop()
        if len(self.call_info) > 0:
            self.func = self.call_info[-1].func
            self.stack = self.call_info[-1].stack
        return frame

    def register(self, name: str, func: callable):
        self.globals.set(Value.string(name), Value.closure(PClosure(func)))

    def _getmetatable(self, val: Value) -> Value | None:
        if val.is_table() or val.is_userdata():
            mt = val.get_metatable()
            return Value.table(mt) if mt else None
        else:
            return self.mt.get(Value.string(val.type_name()))

    # external metamethods
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
        assert mt.is_table(), "Metatable must be a table"
        if obj.is_table():
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
        # Delegate to Value's gettable method with callback
        return t.gettable(key, self._luacall)

    def len(self, idx: int) -> int:
        t = self.stack[idx]
        # Delegate to Value's len method with callback
        return t.len(self._luacall)

    def call(self, idx: int, nargs: int, nrets: int):
        func_value = self.stack[idx]
        if func_value.is_function():
            if type(func_value.value) is LClosure:
                self.precall(func_value.value, idx, nargs, nrets)
                while self.excute():
                    pass
            else:
                self.pycall(func_value.value, idx, nargs, nrets)
        elif func_value.is_table():
            mt = func_value.get_metatable()
            func_value = mt.get(Value("__call")) if mt else None
            if func_value and func_value.is_function():
                self.stack[idx] = self._luacall(func_value.value, *self.stack[idx: idx + nargs + 1])
        else:
            raise TypeError("CALL error")

    def pcall(self, idx: int, nargs: int, nrets: int) -> int:
        ci_len = len(self.call_info)
        try:
            self.call(idx, nargs, nrets)
        except Exception as e:
            while len(self.call_info) > ci_len:
                self.pop_closure()
            self.stack.clear()
            self.pushvalue(Value.string(str(e)))
            if e is RuntimeError:
                return LUA_ERRRUN
            elif e is SyntaxError:
                return LUA_ERRSYNTAX
            elif e is MemoryError:
                return LUA_ERRMEM
            else:
                return LUA_ERRERR
        return LUA_OK

    def error(self):
        value = self.stack[-1]
        raise RuntimeError(value.value)

    def excute(self) -> bool:
        inst = self.fetch()
        if inst is None:
            return False
        op_name = inst.op_name()
        method = getattr(Operator, op_name, None)
        if method:
            # print(f"-{len(self.call_info)}- " +  str(inst).ljust(40))
            method(inst, self)
            # print(f"-{len(self.call_info)}- " +  ''.join(f"[{v}]" for v in self.stack))
        if op_name == "RETURN":
            return False
        return True

    def precall(self, closure: LClosure, func_idx: int = 0, nargs: int = 0, nrets: int = 0):
        closure.stack = [Value.nil()] * closure.func.maxstacksize
        closure.pc = 0
        closure.varargs = []
        for i in range(nargs):
            value = self.stack[func_idx + 1 + i]
            if i < closure.func.numparams:
                closure.stack[i] = value
            else:
                closure.varargs.append(value)

        closure.nrets = nrets
        closure.ret_idx = func_idx
        self.push_closure(closure)

    def pycall(self, closure: PClosure, func_idx: int = 0, args_count: int = 0, nrets: int = 0):
        closure.stack = []
        for i in range(args_count):
            value = self.stack[func_idx + 1 + i]
            closure.stack.append(value)

        self.push_closure(closure)
        ret_count = closure.func(self)
        self.pop_closure()

        ret_start = len(closure.stack) - ret_count

        for i in range(nrets):
            ret_value = closure.stack[ret_start + i] if i < ret_count else Value.nil()
            self.stack[func_idx + i] = ret_value

    def poscall(self, ret_start, ret_count: int = 0):
        closure = self.pop_closure()

        # Handle return values
        if ret_count == -1:
            ret_count = len(closure.stack) - ret_start

        if closure.nrets == -1:
            closure.nrets = ret_count

        for i in range(closure.nrets):
            ret_value = closure.stack[ret_start + i] if i < ret_count else Value.nil()
            self.stack[closure.ret_idx + i] = ret_value

    def next(self, idx: int) -> Optional[tuple[Value, Value]]:
        table = self.stack[idx]
        key = self.stack[-1]
        if not table.is_table():
            raise TypeError("next expects a table")
        return table.value.next(key)

    def pushpyfunction(self, func: callable):
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

    def _luacall(self, func, *args) -> Value:
        nargs = len(args)
        func_idx = len(self.stack)
        self.stack.append(Value.closure(func))
        self.stack.extend(args)
        self.call(func_idx, nargs, 1)
        res = self.stack[func_idx]
        while len(self.stack) > func_idx:
            self.stack.pop()
        return res

    def _get_rk(self, rk: int) -> Value:
        """Get RK value: if rk >= 256, it's a constant index; otherwise it's a register"""
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
        self.call_info[-1].pc += offset

    def fetch(self) -> Optional[Instruction]:
        if len(self.call_info) == 0:
            return None
        return self.call_info[-1].fetch()

    # debug
    def print_stack(self):
        pass
        # self.call_info[-1].print_stack()
