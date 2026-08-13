from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from structs.value import LuaValue, Value


def _make_value(v: LuaValue) -> Value:
    """Lazy import helper to create Value at runtime."""
    from structs.value import Value

    return Value(v)


def _make_number_value(v: int | float) -> Value:
    """Lazy import helper to create Value.number at runtime."""
    from structs.value import Value

    return Value.number(v)


class Table:
    _metatable: Table | None = None
    _list: list[Value]
    _map: dict[Value | int, Value]

    def __init__(self):
        self._list = []
        self._map = {}

    def get(self, key: int | Value) -> Value | None:
        int_key = key if isinstance(key, int) else key.get_integer()
        if int_key is not None:
            if 1 <= int_key <= len(self._list):
                return self._list[int_key - 1]
            return self._map.get(int_key, None)
        return self._map.get(key, None)

    def set(self, key: int | Value, value: Value):
        if not isinstance(key, int) and key.is_nil():
            raise RuntimeError("table index is nil")
        int_key = key if isinstance(key, int) else key.get_integer()
        if value.is_nil():
            if int_key is not None:
                if 1 <= int_key <= len(self._list):
                    self._shrink_list(int_key)
                elif int_key in self._map:
                    del self._map[int_key]
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
        entries: list[tuple[Value, Value]] = [
            (_make_number_value(index), value) for index, value in enumerate(self._list, 1)
        ]
        entries.extend(
            (_make_number_value(map_key) if isinstance(map_key, int) else map_key, value)
            for map_key, value in self._map.items()
        )
        if key.is_nil():
            return entries[0] if entries else None

        for index, (entry_key, _) in enumerate(entries):
            if entry_key == key:
                return entries[index + 1] if index + 1 < len(entries) else None
        raise RuntimeError("invalid key to 'next'")

    def setmetatable(self, metatable: Table | None):
        self._metatable = metatable

    def getmetatable(self) -> Table | None:
        return self._metatable

    def _shrink_list(self, key: int):
        # Remove any stale hash entry for the removed integer key.
        self._map.pop(key, None)
        for lua_idx in range(key + 1, len(self._list) + 1):
            self._map[lua_idx] = self._list[lua_idx - 1]
        self._list = self._list[: key - 1]

    def _expand_list(self):
        while (len(self._list) + 1) in self._map:
            key = len(self._list) + 1
            self._list.append(self._map[key])
            del self._map[key]

    def gettable(self, key: Value) -> Value | None:
        return self.get(key)
