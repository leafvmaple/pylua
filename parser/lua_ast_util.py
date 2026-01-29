"""Utility functions for AST serialization.

This module provides helper functions for converting AST nodes to dictionaries
and other common operations.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .expr import Expr
    from .stat import Stmt
    from .block import Block


def convert_value(value: Any) -> Any:
    """Recursively convert a value to a JSON-serializable form.

    Handles AST nodes, lists, tuples, and primitive values.
    """
    # Import here to avoid circular dependencies
    from .expr import Expr
    from .stat import Stmt
    from .block import Block

    if isinstance(value, (Expr, Stmt, Block)):
        return value.to_dict()
    elif isinstance(value, list):
        return [convert_value(item) for item in value]  # type: ignore[misc]
    elif isinstance(value, tuple):
        return tuple(convert_value(item) for item in value)  # type: ignore[misc]
    else:
        return value


def obj_to_dict(obj: Expr | Stmt | Block) -> dict[str, Any]:
    """Convert an AST node to a dictionary using reflection.

    This creates a dictionary with:
    - 'type': The class name of the node
    - All instance attributes with their converted values
    """
    result: dict[str, Any] = {"type": obj.__class__.__name__}

    for key, value in obj.__dict__.items():
        result[key] = convert_value(value)

    return result
