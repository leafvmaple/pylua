"""Lua AST module (compatibility wrapper).

This module provides backward compatibility by re-exporting all AST classes
from the new modular structure:
- lua_exp: Expression nodes
- lua_stat: Statement nodes and Block
- lua_ast_util: Utility functions

New code should import from the specific modules directly.
"""
from __future__ import annotations

import json

from typing import Any

from .lua_lexer import Lexer
from .lua_exp import Expr
from .lua_stat import Stat, ReturnStat
from codegen.func import FuncInfo
from codegen.inst import CodegenInst


class Block:
    last_line: int
    stats: list[Stat]

    def __init__(self, last_line: int, stats: list[Stat]):
        self.last_line = last_line
        self.stats = stats

    @classmethod
    def parse(cls, lexer: Lexer) -> Block:
        """Parse a block of statements until a block-ending keyword."""
        stats = []

        while (token := lexer.current()) and not token.is_end() and not token.is_return():
            stats.append(Stat.parse(lexer))

        last_line = lexer._line if hasattr(lexer, '_line') else 0
        return cls(last_line, stats)

    def codegen(self, info: FuncInfo):
        for stmt in self.stats:
            stmt.codegen(info)

    def to_dict(self) -> dict[str, Any]:
        from .lua_ast_util import obj_to_dict
        return obj_to_dict(self)

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent='  ', ensure_ascii=False)


class Chunk:
    block: Block
    ret_exps: list[Expr]

    def __init__(self, block: Block, ret_exps: list[Expr]):
        self.block = block
        self.ret_exps = ret_exps

    @classmethod
    def parse(cls, lexer: Lexer) -> Chunk:
        block = Block.parse(lexer)

        token = lexer.current()
        if token.is_return():
            ret_exps = ReturnStat.parse_list(lexer)
        else:
            ret_exps = []

        return cls(block, ret_exps)

    def to_info(self) -> FuncInfo:
        info = FuncInfo()
        self.block.codegen(info)

        if self.ret_exps:
            nret = len(self.ret_exps)
            reg = info.alloc_regs(nret)
            for i in range(nret):
                self.ret_exps[i].codegen(info, reg + i)
            CodegenInst.ret(info, reg, nret + 1)
            info.free_regs(nret)
        else:
            CodegenInst.ret(info, 0, 1)

        return info
