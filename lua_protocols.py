"""Protocol definitions for breaking circular dependencies.

This module defines protocol interfaces (similar to C++ abstract interfaces)
that allow different modules to depend on interfaces rather than concrete implementations.
"""
from __future__ import annotations

from typing import Protocol, TYPE_CHECKING
if TYPE_CHECKING:
    from lua_value import Value


class LuaCallable(Protocol):
    def __call__(self, func, *args: Value) -> Value:
        ...
