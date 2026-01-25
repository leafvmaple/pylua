"""Utility functions for AST serialization.

This module provides helper functions for converting AST nodes to dictionaries
and other common operations.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .lua_exp import Expr
    from .lua_stat import Stat
    from .lua_block import Block


def convert_value(value: Any) -> Any:
    """Recursively convert a value to a JSON-serializable form.
    
    Handles AST nodes, lists, tuples, and primitive values.
    """
    # Import here to avoid circular dependencies
    from .lua_exp import Expr
    from .lua_stat import Stat
    from .lua_block import Block
    
    if isinstance(value, (Expr, Stat, Block)):
        return value.to_dict()
    elif isinstance(value, list):
        return [convert_value(item) for item in value]
    elif isinstance(value, tuple):
        return tuple(convert_value(item) for item in value)
    else:
        return value


def obj_to_dict(obj: Expr | Stat | Block) -> dict[str, Any]:
    """Convert an AST node to a dictionary using reflection.
    
    This creates a dictionary with:
    - 'type': The class name of the node
    - All instance attributes with their converted values
    """
    result: dict[str, Any] = {"type": obj.__class__.__name__}
    
    for key, value in obj.__dict__.items():
        result[key] = convert_value(value)
    
    return result

