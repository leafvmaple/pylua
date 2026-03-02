"""Utility functions for AST serialization.

This module provides helper functions for converting AST nodes to dictionaries
and other common operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .block import Block
    from .expr import Expr
    from .stat import Stmt


def convert_value(value: Any) -> Any:
    """Recursively convert a value to a JSON-serializable form.

    Handles AST nodes, lists, tuples, and primitive values.
    """
    # Import here to avoid circular dependencies
    from .block import Block
    from .expr import Expr
    from .stat import Stmt

    if isinstance(value, (Expr, Stmt, Block)):
        return value.to_dict()
    elif isinstance(value, list):
        return [convert_value(item) for item in value]  # type: ignore[misc]
    elif isinstance(value, tuple):
        return tuple(convert_value(item) for item in value)  # type: ignore[misc]
    else:
        return value


def asdict(obj: Expr | Stmt | Block) -> dict[str, Any]:
    """Convert an AST node to a dictionary using reflection.

    This creates a dictionary with:
    - 'type': The class name of the node
    - Fields from _fields tuple (if defined) or all instance attributes
    """
    result: dict[str, Any] = {"type": obj.__class__.__name__}

    # Use _fields tuple if defined, otherwise fall back to __dict__
    fields = getattr(obj, "_fields", None)

    if fields:
        # Only serialize fields listed in _fields
        for key in fields:
            if hasattr(obj, key):
                result[key] = convert_value(getattr(obj, key))
    else:
        # Fall back to all instance attributes
        for key, value in obj.__dict__.items():
            result[key] = convert_value(value)

    return result
