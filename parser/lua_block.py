from __future__ import annotations

import json

from typing import Any

from .lua_lexer import Lexer
from .lua_expr import Expr
from .lua_stat import Stmt, ReturnStmt
from codegen.func import FuncInfo
from codegen.inst import CodegenInst


class Block:
    last_line: int
    stmts: list[Stmt]
    ret_exprs: list[Expr]

    def __init__(self, last_line: int, stmts: list[Stmt], ret_exps: list[Expr]):
        self.last_line = last_line
        self.stmts = stmts
        self.ret_exprs = ret_exps

    @classmethod
    def parse(cls, lexer: Lexer) -> Block:
        """Parse a block of statements until a block-ending keyword."""
        stmts: list[Stmt] = []

        while (token := lexer.current()) and not token.is_end() and not token.is_return():
            stmts.append(Stmt.parse(lexer))

        token = lexer.current()
        ret_exprs = ReturnStmt.parse_list(lexer) if token.is_return() else []

        return cls(0, stmts, ret_exprs)

    def codegen(self, info: FuncInfo):
        for stmt in self.stmts:
            stmt.codegen(info)

    def to_dict(self) -> dict[str, Any]:
        from .lua_ast_util import obj_to_dict
        return obj_to_dict(self)

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent='  ', ensure_ascii=False)


class Chunk:
    block: Block

    def __init__(self, block: Block):
        self.block = block

    @classmethod
    def parse(cls, lexer: Lexer) -> Chunk:
        block = Block.parse(lexer)

        return cls(block)

    def to_info(self) -> FuncInfo:
        info = FuncInfo()
        self.block.codegen(info)

        if self.block.ret_exprs:
            num_rets = len(self.block.ret_exprs)
            reg = info.alloc_regs(num_rets)
            for i in range(num_rets):
                self.block.ret_exprs[i].codegen(info, reg + i)
            CodegenInst.ret(info, reg, num_rets + 1)
            info.free_regs(num_rets)
        else:
            CodegenInst.ret(info, 0, 1)

        return info
