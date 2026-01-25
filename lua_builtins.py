"""Lua built-in functions implementation."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lua_state import LuaState

from lua_value import Value

class BUILTIN:
    @staticmethod
    def lua_print(state: LuaState) -> int:
        n = state.gettop()
        outputs = []
        for i in range(n):
            outputs.append(str(state.stack[i]))
        print(', '.join(outputs))
        return 0
    
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
        table = state.stack[0]
        index = state.stack[1]
        if not table.is_table():
            raise TypeError("ipairsaux expects a table")
        index.conv_str_to_number()
        if not index.is_number():
            raise TypeError("ipairsaux index must be a number")
        next_index = index.value + 1
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