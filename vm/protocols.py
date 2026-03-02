"""Protocol definitions for breaking circular dependencies.

This module defines protocol interfaces (similar to C++ abstract interfaces)
that allow different modules to depend on interfaces rather than concrete implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from structs.function import LClosure
    from structs.value import Value


class LuaCallable(Protocol):
    def __call__(self, func: LClosure, *args: Value) -> Value: ...


class LuaCheckable(Protocol):
    @staticmethod
    def check(val: Value) -> bool: ...

    @staticmethod
    def checks(va: Value, vb: Value) -> bool: ...
