"""Lua built-in functions implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vm.state import LuaState

from structs.value import Value


class BUILTIN:
    @staticmethod
    def lua_print(state: LuaState) -> int:
        n = state.gettop()
        outputs: list[str] = []
        for i in range(n):
            outputs.append(str(state.stack[i]))
        print('\t'.join(outputs))
        return 0

    @staticmethod
    def lua_type(state: LuaState) -> int:
        """type(v) -> string"""
        if state.gettop() < 1:
            raise RuntimeError("bad argument #1 to 'type' (value expected)")
        val = state.stack[0]
        state.pushvalue(Value.string(val.type_name()))
        return 1

    @staticmethod
    def lua_tostring(state: LuaState) -> int:
        """tostring(v) -> string"""
        if state.gettop() < 1:
            raise RuntimeError("bad argument #1 to 'tostring' (value expected)")
        val = state.stack[0]
        state.pushvalue(Value.string(str(val)))
        return 1

    @staticmethod
    def lua_tonumber(state: LuaState) -> int:
        """tonumber(e [, base]) -> number or nil"""
        if state.gettop() < 1:
            raise RuntimeError("bad argument #1 to 'tonumber' (value expected)")
        val = state.stack[0]
        if val.is_number():
            state.pushvalue(val)
            return 1
        result = val.to_str_number()
        if result is not None:
            state.pushvalue(result)
        else:
            state.pushnil()
        return 1

    @staticmethod
    def lua_assert(state: LuaState) -> int:
        """assert(v [, message]) -> v or error"""
        n = state.gettop()
        if n < 1:
            raise RuntimeError("bad argument #1 to 'assert' (value expected)")
        val = state.stack[0]
        if not val.get_boolean():
            if n >= 2:
                msg = state.stack[1]
                raise RuntimeError(str(msg))
            else:
                raise RuntimeError("assertion failed!")
        # Return all arguments
        return n

    @staticmethod
    def lua_rawequal(state: LuaState) -> int:
        """rawequal(v1, v2) -> boolean"""
        if state.gettop() < 2:
            raise RuntimeError("bad argument to 'rawequal'")
        v1 = state.stack[0]
        v2 = state.stack[1]
        state.pushboolean(v1 == v2)
        return 1

    @staticmethod
    def lua_rawlen(state: LuaState) -> int:
        """rawlen(v) -> number"""
        from structs.table import Table
        if state.gettop() < 1:
            raise RuntimeError("bad argument #1 to 'rawlen'")
        val = state.stack[0]
        if val.is_table():
            assert isinstance(val.value, Table)
            state.pushvalue(Value.number(val.value.len()))
        elif val.is_string():
            assert isinstance(val.value, str)
            state.pushvalue(Value.number(len(val.value)))
        else:
            raise RuntimeError(f"table or string expected, got {val.type_name()}")
        return 1

    @staticmethod
    def lua_rawset(state: LuaState) -> int:
        """rawset(table, index, value) -> table"""
        from structs.table import Table
        if state.gettop() < 3:
            raise RuntimeError("bad argument to 'rawset'")
        t = state.stack[0]
        if not t.is_table():
            raise RuntimeError(f"bad argument #1 to 'rawset' (table expected, got {t.type_name()})")
        assert isinstance(t.value, Table)
        key = state.stack[1]
        value = state.stack[2]
        if key.is_nil():
            raise RuntimeError("table index is nil")
        t.value.set(key, value)
        state.pushvalue(t)
        return 1

    @staticmethod
    def lua_rawget(state: LuaState) -> int:
        """rawget(table, index) -> value"""
        from structs.table import Table
        if state.gettop() < 2:
            raise RuntimeError("bad argument to 'rawget'")
        t = state.stack[0]
        if not t.is_table():
            raise RuntimeError(f"bad argument #1 to 'rawget' (table expected, got {t.type_name()})")
        assert isinstance(t.value, Table)
        key = state.stack[1]
        value = t.value.get(key)
        state.pushvalue(value if value is not None else Value.nil())
        return 1

    @staticmethod
    def lua_select(state: LuaState) -> int:
        """select(index, ...) -> values after index, or count if index='#'"""
        if state.gettop() < 1:
            raise RuntimeError("bad argument #1 to 'select'")
        idx = state.stack[0]
        n = state.gettop() - 1  # number of varargs
        if idx.is_string() and idx.value == '#':
            state.pushvalue(Value.number(n))
            return 1
        if not idx.is_number():
            raise RuntimeError("bad argument #1 to 'select' (number or string expected)")
        assert isinstance(idx.value, (int, float))
        i = int(idx.value)
        if i < 0:
            i = n + i + 1
        if i < 1 or i > n:
            raise RuntimeError(f"bad argument #1 to 'select' (index out of range)")
        # Return elements from index i onwards
        count = 0
        for j in range(i, n + 1):
            state.pushvalue(state.stack[j])
            count += 1
        return count

    @staticmethod
    def lua_unpack(state: LuaState) -> int:
        """unpack(list [, i [, j]]) -> elements"""
        from structs.table import Table
        if state.gettop() < 1:
            raise RuntimeError("bad argument #1 to 'unpack' (table expected)")
        t = state.stack[0]
        if not t.is_table():
            raise RuntimeError(f"bad argument #1 to 'unpack' (table expected, got {t.type_name()})")
        assert isinstance(t.value, Table)
        
        i = 1
        j = t.value.len()
        if state.gettop() >= 2:
            iv = state.stack[1]
            if iv.is_number():
                assert isinstance(iv.value, (int, float))
                i = int(iv.value)
        if state.gettop() >= 3:
            jv = state.stack[2]
            if jv.is_number():
                assert isinstance(jv.value, (int, float))
                j = int(jv.value)
        
        count = 0
        for idx in range(i, j + 1):
            val = t.value.get(idx)
            state.pushvalue(val if val is not None else Value.nil())
            count += 1
        return count

    @staticmethod
    def lua_getmetatable(state: LuaState) -> int:
        if state.getmetatable(1) != 1:
            state.pushnil()
        return 1

    @staticmethod
    def lua_setmetatable(state: LuaState) -> int:
        if (state.getmetafield(1, "__metatable") != 0):
            raise RuntimeError("cannot change a protected metatable")
        state.settop(2)
        state.setmetatable(1)
        return 0

    @staticmethod
    def lua_ipairsaux(state: LuaState) -> int:
        from structs.table import Table
        table = state.stack[0]
        index = state.stack[1]
        if not table.is_table():
            raise TypeError("ipairsaux expects a table")
        index.conv_str_to_number()
        if not index.is_number():
            raise TypeError("ipairsaux index must be a number")

        assert type(index.value) is int
        next_index = index.value + 1

        assert type(table.value) is Table
        value = table.value.get(next_index)
        if value is not None:
            state.pushvalue(Value.number(next_index))
            state.pushvalue(value)
            return 2
        else:
            return 0

    @staticmethod
    def lua_next(state: LuaState) -> int:
        result = state.next(0)
        if result is not None:
            state.pushvalue(result[0])
            state.pushvalue(result[1])
            return 2
        else:
            return 0

    @staticmethod
    def lua_ipairs(state: LuaState) -> int:
        table = state.stack[0]
        if not table.is_table():
            raise TypeError("ipairs expects a table")
        state.pushpyfunction(BUILTIN.lua_ipairsaux)
        state.pushvalue(table)
        state.pushvalue(Value.number(0))
        return 3

    @staticmethod
    def lua_pairs(state: LuaState) -> int:
        table = state.stack[0]
        if not table.is_table():
            raise TypeError("pairs expects a table")
        state.pushpyfunction(BUILTIN.lua_next)
        state.pushvalue(table)
        state.pushnil()
        return 3

    @staticmethod
    def lua_error(state: LuaState) -> int:
        state.error()
        return 0

    @staticmethod
    def lua_pcall(state: LuaState) -> int:
        nargs = state.gettop() - 1
        status = state.pcall(0, nargs, -1)
        state.pushboolean(status == 0)
        state.insert(1)
        return state.gettop()
