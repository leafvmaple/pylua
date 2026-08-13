from __future__ import annotations

from typing import TYPE_CHECKING

from structs.function import LClosure, PClosure, Proto
from structs.instruction import Instruction
from structs.table import Table
from structs.value import Value
from vm.builtins import BUILTIN
from vm.operator import DISPATCH_TABLE

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
    registry: Table
    globals: Table

    # Global
    mt: Table

    def __init__(self, main: Proto, globals_table: Table | None = None):
        call_info = LClosure.from_proto(main)
        self.registry = Table()
        key = Value.number(LUA_GLOBALS_INDEX)

        self.globals = globals_table if globals_table is not None else Table()
        self.registry.set(key, Value.table(self.globals))
        self.mt = Table()
        self.call_info = [call_info]

        # Register built-in functions
        self.register("print", BUILTIN.lua_print)
        self.register("type", BUILTIN.lua_type)
        self.register("tostring", BUILTIN.lua_tostring)
        self.register("tonumber", BUILTIN.lua_tonumber)
        self.register("assert", BUILTIN.lua_assert)
        self.register("getmetatable", BUILTIN.lua_getmetatable)
        self.register("setmetatable", BUILTIN.lua_setmetatable)
        self.register("rawequal", BUILTIN.lua_rawequal)
        self.register("rawget", BUILTIN.lua_rawget)
        self.register("rawset", BUILTIN.lua_rawset)
        self.register("rawlen", BUILTIN.lua_rawlen)
        self.register("next", BUILTIN.lua_next)
        self.register("ipairs", BUILTIN.lua_ipairs)
        self.register("pairs", BUILTIN.lua_pairs)
        self.register("select", BUILTIN.lua_select)
        self.register("unpack", BUILTIN.lua_unpack)
        self.register("error", BUILTIN.lua_error)
        self.register("pcall", BUILTIN.lua_pcall)

    @property
    def stack(self) -> list[Value]:
        """Registers of the currently executing frame."""
        return self.call_info[-1].stack

    @property
    def func(self) -> Proto:
        """Prototype of the currently executing Lua frame."""
        frame = self.call_info[-1]
        assert type(frame) is LClosure
        return frame.func

    def get_global(self, name: str) -> Value:
        key = Value.string(name)
        value = self.globals.get(key)
        return value if value is not None else Value.nil()

    def set_global(self, name: str, value: Value):
        key = Value.string(name)
        self.globals.set(key, value)

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
        """Call the value at `idx` and run it to completion synchronously.

        Used by callers that need results immediately (metamethods via
        lua_call, the generic-for iterator, pcall). Pure Lua-to-Lua calls go
        through the CALL opcode and `precall`, which keep the dispatch loop flat
        instead of recursing in Python.
        """
        base = len(self.call_info)
        self.precall(idx, nargs, num_rets)
        if len(self.call_info) > base:
            self._dispatch_until(base)

    def precall(self, idx: int, nargs: int, num_rets: int):
        """Begin a call. Lua closures push a fresh frame and return so the
        active dispatch loop continues into it (no Python recursion). Python
        closures run inline."""
        func_value = self.stack[idx]
        if func_value.is_function():
            if type(func_value.value) is LClosure:
                self._precall_lua(func_value.value, idx, nargs, num_rets)
            elif type(func_value.value) is PClosure:
                self._precall_py(func_value.value, idx, nargs, num_rets)
        elif func_value.is_table():
            mt = func_value.get_metatable()
            callable_value = mt.get(Value("__call")) if mt else None
            if callable_value and callable_value.is_function():
                # __call receives the table itself as its first argument.
                args = self.stack[idx : idx + nargs + 1]
                self._ensure_stack(self.stack, idx + nargs + 2)
                self.stack[idx] = callable_value
                self.stack[idx + 1 : idx + nargs + 2] = args
                self.precall(idx, nargs + 1, num_rets)
            else:
                raise TypeError("attempt to call a table value")
        else:
            raise TypeError(f"attempt to call a {func_value.type_name()} value")

    def _precall_lua(self, closure: LClosure, func_idx: int, nargs: int, num_rets: int):
        proto = closure.func
        # A fresh activation record so recursive calls don't share registers.
        # Captured upvalues are shared with the prototype closure.
        frame = LClosure(proto)
        frame.upvalues = closure.upvalues
        frame.num_rets = num_rets
        frame.ret_idx = func_idx

        caller_stack = self.stack
        for i in range(nargs):
            value = caller_stack[func_idx + 1 + i]
            if i < proto.num_params:
                frame.stack[i] = value
            else:
                frame.varargs.append(value)

        frame.top = proto.num_params

        self.call_info.append(frame)

    def _precall_py(self, closure: PClosure, func_idx: int, nargs: int, num_rets: int):
        caller_stack = self.stack
        frame = PClosure(closure.func)
        frame.stack = [caller_stack[func_idx + 1 + i] for i in range(nargs)]

        self.call_info.append(frame)
        ret_count = closure.func(self)
        self.call_info.pop()

        ret_start = len(frame.stack) - ret_count
        wanted = ret_count if num_rets == -1 else num_rets
        self._ensure_stack(caller_stack, func_idx + wanted)
        for i in range(wanted):
            ret_value = frame.stack[ret_start + i] if i < ret_count else Value.nil()
            caller_stack[func_idx + i] = ret_value
        caller = self.call_info[-1]
        if type(caller) is LClosure:
            caller.top = func_idx + wanted

    def postcall(self, ret_start: int, ret_count: int):
        """Pop the current Lua frame and copy its results into the caller."""
        frame = self.call_info.pop()
        assert type(frame) is LClosure
        frame.close_upvalues(0)

        if ret_count == -1:
            ret_count = len(frame.stack) - ret_start
        num_rets = ret_count if frame.num_rets == -1 else frame.num_rets

        if not self.call_info:
            return  # main chunk returned; no caller to receive results

        caller_stack = self.stack
        self._ensure_stack(caller_stack, frame.ret_idx + num_rets)
        for i in range(num_rets):
            ret_value = frame.stack[ret_start + i] if i < ret_count else Value.nil()
            caller_stack[frame.ret_idx + i] = ret_value
        caller = self.call_info[-1]
        if type(caller) is LClosure:
            caller.top = frame.ret_idx + num_rets

    @staticmethod
    def _ensure_stack(stack: list[Value], size: int) -> None:
        if len(stack) < size:
            stack.extend(Value.nil() for _ in range(size - len(stack)))

    def pcall(self, idx: int, nargs: int, num_rets: int) -> int:
        base = len(self.call_info)
        try:
            self.call(idx, nargs, num_rets)
        except Exception as e:
            while len(self.call_info) > base:
                self.call_info.pop()
            # Keep current frame's stack object; replace contents with error only.
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

    def run(self):
        """Top-level execution loop: run the main chunk to completion."""
        self._dispatch_until(0)

    def _dispatch_until(self, base: int):
        """Drive the dispatch loop until `call_info` shrinks back to `base`.

        A single loop services arbitrarily deep Lua call chains because CALL
        pushes frames and RETURN pops them — recursion depth is bounded by
        memory, not by the Python call stack.
        """
        while len(self.call_info) > base:
            frame = self.call_info[-1]
            if type(frame) is not LClosure:
                break  # defensive: Python frames run inline and never linger here
            inst = frame.fetch()
            if inst is None:
                self.postcall(0, 0)  # ran off the end without RETURN
                continue
            method = DISPATCH_TABLE.get(inst.op_name())
            if method is None:
                raise RuntimeError(f"unknown opcode: {inst.op_name()}")
            method(inst, self)

    def next(self, idx: int) -> tuple[Value, Value] | None:
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
        elif idx > LUA_GLOBALS_INDEX:  # idx < 0
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

    def fetch(self) -> Instruction | None:
        if self.call_info:
            assert type(self.call_info[-1]) is LClosure
            return self.call_info[-1].fetch()
        return None

    # debug
    def print_stack(self):
        pass
        # self.call_info[-1].print_stack()
