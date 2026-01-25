from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from lua_value import Value


class Table:
    _metatable: Table | None = None
    _list: list[Value]
    _map: dict[Value | int, Value]

    def __init__(self):
        self._list = []
        self._map = {}

    def get(self, key: int | Value) -> Value | None:
        int_key = key if type(key) is int else key.get_integer()
        if int_key is not None:
            if 1 <= int_key <= len(self._list):
                return self._list[int_key - 1]
            return self._map.get(int_key, None)
        return self._map.get(key, None)

    def set(self, key: int | Value, value: Value):
        int_key = key if type(key) is int else key.get_integer()
        if value.is_nil():
            if int_key is not None:
                if 1 <= int_key <= len(self._list):
                    self._shrink_list(int_key)
            elif key in self._map:
                del self._map[key]
        else:
            if int_key is not None:
                if int_key == len(self._list) + 1:
                    self._list.append(value)
                    self._expand_list()
                elif 1 <= int_key <= len(self._list):
                    self._list[int_key - 1] = value
                else:
                    self._map[int_key] = value
            else:
                self._map[key] = value

    def len(self) -> int:
        return len(self._list)
    
    def next(self, key: Value) -> tuple[Value, Value] | None:
        if key.is_nil():
            if len(self._list) > 0:
                return Value(1), self._list[0]
            for k in self._map:
                return k, self._map[k]
            return None
        
        int_key = key.get_integer()
        if int_key is not None:
            return self._list_next(int_key) or self._map_next(int_key)
        return self._map_next(key)
    
    def _list_next(self, key: int) -> tuple[Value, Value] | None:
        if key < len(self._list):
            return Value(key + 1), self._list[key]
        return None
    
    def _map_next(self, key: Value | int) -> tuple[Value, Value] | None:
        found = False
        for k in self._map:
            if found:
                return k, self._map[k]
            if k == key:
                found = True
        return None
    
    def setmetatable(self, metatable: Table):
        self._metatable = metatable

    def getmetatable(self) -> Table | None:
        return self._metatable

    def _shrink_list(self, key: int):
        for lua_idx in range(key + 1, len(self._list) + 1):
            self._map[lua_idx] = self._list[lua_idx - 1]
        self._list = self._list[:key - 1]

    def _expand_list(self):
        while (len(self._list) + 1) in self._map:
            key = len(self._list) + 1
            self._list.append(self._map[key])
            del self._map[key]

    def gettable(self, key: str) -> Value | None:
        return self.get(Value(key))
