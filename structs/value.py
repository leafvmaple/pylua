from __future__ import annotations

from enum import Enum

from typing import TypeAlias
from vm.protocols import LuaCallable
from structs.table import Table
from structs.function import Closure, LClosure, PClosure


LuaValue: TypeAlias = str | float | int | bool | Table | Closure | None


class LUA_TYPE(Enum):
    NIL = 0
    BOOLEAN = 1
    LIGHTUSERDATA = 2
    NUMBER = 3
    STRING = 4
    TABLE = 5
    FUNCTION = 6
    USERDATA = 7
    THREAD = 8


# Sentinel for uninitialized singleton cache
_UNSET = object()


class Value:
    value: LuaValue

    # Singleton caches for frequently created immutable values
    _NIL: Value | None = None
    _TRUE: Value | None = None
    _FALSE: Value | None = None

    def __init__(self, value: LuaValue):
        self.value = value
        self._conv_float_to_int()

    @classmethod
    def nil(cls) -> Value:
        """Create a nil value (cached singleton)"""
        if cls._NIL is None:
            cls._NIL = cls(None)
        return cls._NIL

    @classmethod
    def boolean(cls, val: bool) -> Value:
        """Create a boolean value (cached singletons for True/False)"""
        if val:
            if cls._TRUE is None:
                cls._TRUE = cls(True)
            return cls._TRUE
        else:
            if cls._FALSE is None:
                cls._FALSE = cls(False)
            return cls._FALSE

    @classmethod
    def number(cls, val: int | float) -> Value:
        """Create a number value"""
        return cls(val)

    @classmethod
    def string(cls, val: str) -> Value:
        """Create a string value"""
        return cls(val)

    @classmethod
    def table(cls, val: Table) -> Value:
        """Create a table value"""
        return cls(val)

    @classmethod
    def closure(cls, val: LClosure | PClosure) -> Value:
        """Create a closure value"""
        return cls(val)

    def to_number_str(self) -> Value:
        """Return a new Value with number converted to string."""
        if self.is_number():
            return Value.string(str(self.value))
        return self

    def to_str_number(self) -> Value | None:
        """Return a new Value with string converted to number, or None if not convertible."""
        if self.is_string():
            assert isinstance(self.value, str)
            try:
                num = float(self.value)
                if num.is_integer():
                    return Value.number(int(num))
                return Value.number(num)
            except (ValueError, OverflowError):
                return None
        if self.is_number():
            return self
        return None

    # Keep backward-compatible in-place methods (used by CheckNumber)
    def conv_number_to_str(self):
        if self.is_number():
            self.value = str(self.value)

    def conv_str_to_number(self) -> bool:
        """Try to convert string value to number in-place. Returns True on success."""
        if self.is_number():
            return True
        if self.is_string():
            assert isinstance(self.value, str)
            try:
                self.value = float(self.value)
                self._conv_float_to_int()
                return True
            except (ValueError, OverflowError):
                return False
        return False

    def _conv_float_to_int(self):
        if isinstance(self.value, float) and self.value.is_integer():
            self.value = int(self.value)

    def is_nil(self) -> bool:
        return self.value is None

    def is_boolean(self) -> bool:
        return type(self.value) is bool

    def is_number(self) -> bool:
        return isinstance(self.value, (int, float)) and not isinstance(self.value, bool)

    def is_string(self) -> bool:
        return isinstance(self.value, str)

    def is_table(self) -> bool:
        return isinstance(self.value, Table)

    def is_function(self) -> bool:
        return isinstance(self.value, (LClosure, PClosure))

    def is_userdata(self) -> bool:
        return False  # Placeholder for userdata type

    def type_name(self) -> str:
        if self.is_nil():
            return 'nil'
        elif self.is_boolean():
            return 'boolean'
        elif self.is_number():
            return 'number'
        elif self.is_string():
            return 'string'
        elif self.is_table():
            return 'table'
        elif self.is_function():
            return 'function'
        return 'unknown'

    def get_boolean(self) -> bool:
        if self.is_nil():
            return False
        if self.is_boolean():
            assert type(self.value) is bool
            return self.value
        return True

    def get_integer(self) -> int | None:
        if type(self.value) is int:
            return self.value
        if type(self.value) is float:
            if self.value.is_integer():
                return int(self.value)
        return None

    def get_string(self) -> str | None:
        if self.is_number():
            return str(self.value)
        if self.is_string():
            assert type(self.value) is str
            return self.value
        return None

    def get_metatable(self) -> Table | None:
        if self.is_table():
            assert type(self.value) is Table
            return self.value.getmetatable()
        return None

    def gettable(self, key: Value, caller: LuaCallable | None = None) -> Value | None:
        if self.is_table():
            assert isinstance(self.value, Table)
            return self.value.gettable(key)

        mt = self.get_metatable()
        index = mt.get(Value.string("__index")) if mt else None
        if index:
            if index.is_function():
                if caller is None:
                    raise RuntimeError("__index meta method requires a caller")
                return caller(index.value, self, key)
            if index.is_table():
                return index.gettable(key, caller)
        return None

    def len(self, caller: LuaCallable | None = None) -> int:
        mt = self.get_metatable()
        length = mt.get(Value.string("__len")) if mt else None
        if length and length.is_function():
            if caller is None:
                raise RuntimeError("__len meta method requires a caller")
            result = caller(length.value, self)
            int_result = result.get_integer()
            return int_result if int_result is not None else 0

        if self.is_table():
            assert type(self.value) is Table
            return self.value.len()
        if self.is_string():
            assert type(self.value) is str
            return len(self.value)
        return 0

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Value):
            return False
        return self.value == other.value

    def __repr__(self) -> str:
        if self.is_nil():
            return 'nil'
        elif self.is_boolean():
            return 'true' if self.value else 'false'
        elif self.is_string():
            return f'"{self.value}"'
        elif self.is_table():
            return 'table'
        elif self.is_function():
            return 'function'
        return str(self.value)
    
    def __str__(self) -> str:
        """String representation for print() - no quotes for strings"""
        if self.is_nil():
            return 'nil'
        elif self.is_boolean():
            return 'true' if self.value else 'false'
        elif self.is_string():
            return str(self.value)
        elif self.is_table():
            return 'table: ' + hex(id(self.value))
        elif self.is_function():
            return 'function: ' + hex(id(self.value))
        return str(self.value)
