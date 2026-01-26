from __future__ import annotations

import json

from typing import Any

from .lua_lexer import Lexer
from .lua_exp import Expr
from .lua_stat import Stmt, ReturnStmt
from codegen.func import FuncInfo
from codegen.inst import CodegenInst


class Block:
    last_line: int
    stmts: list[Stmt]

    def __init__(self, last_line: int, stmts: list[Stmt]):
        self.last_line = last_line
        self.stmts = stmts

    @classmethod
    def parse(cls, lexer: Lexer) -> Block:
        """Parse a block of statements until a block-ending keyword."""
        stmts: list[Stmt] = []

        while (token := lexer.current()) and not token.is_end() and not token.is_return():
            stmts.append(Stmt.parse(lexer))

        return cls(0, stmts)

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
    ret_exps: list[Expr]

    def __init__(self, block: Block, ret_exps: list[Expr]):
        self.block = block
        self.ret_exps = ret_exps

    @classmethod
    def parse(cls, lexer: Lexer) -> Chunk:
        block = Block.parse(lexer)

        token = lexer.current()
        if token.is_return():
            ret_exprs = ReturnStmt.parse_list(lexer)
        else:
            ret_exprs = []

        return cls(block, ret_exprs)

    def to_info(self) -> FuncInfo:
        info = FuncInfo()
        self.block.codegen(info)

        if self.ret_exps:
            num_rets = len(self.ret_exps)
            reg = info.alloc_regs(num_rets)
            for i in range(num_rets):
                self.ret_exps[i].codegen(info, reg + i)
            CodegenInst.ret(info, reg, num_rets + 1)
            info.free_regs(num_rets)
        else:
            CodegenInst.ret(info, 0, 1)

        return info

