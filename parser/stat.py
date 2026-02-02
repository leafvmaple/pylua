"""Lua statement AST nodes and parser.

This module defines all statement types in Lua and their parsing
logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from .lexer import Lexer
from .expr import Expr, NameExpr, FuncCallExpr, TrueExpr, FuncDefExpr, TableAccessExpr

if TYPE_CHECKING:
    from .block import Block

from codegen.func import FuncInfo
from codegen.inst import CodegenInst


class Stmt:
    """Base class for all Lua statements."""

    @classmethod
    def parse(cls, lexer: Lexer) -> Stmt:
        """Parse a statement based on the current token."""
        token = lexer.current()

        # Empty statement
        if token.type == "SEMICOLON":
            return EmptyStmt.parse(lexer)

        # Break statement
        elif token.type == "BREAK":
            return BreakStmt.parse(lexer)

        # Do block
        elif token.type == "DO":
            return DoStmt.parse(lexer)

        # While loop
        elif token.type == "WHILE":
            return WhileStmt.parse(lexer)

        # Repeat-until loop
        elif token.type == "REPEAT":
            return RepeatStmt.parse(lexer)

        # If statement
        elif token.type == "IF":
            return IfStmt.parse(lexer)

        # For loop (numeric or iterator)
        elif token.type == "FOR":
            return ForStmt.parse(lexer)

        # Function definition
        elif token.type == "FUNCTION":
            return AssignStmt.parse_func(lexer)

        # Local declaration
        elif token.type == "LOCAL":
            return LocalStmt.parse(lexer)

        # Return statement (should not be called directly)
        elif token.type == "RETURN":
            assert False, "Use ReturnStat.parse_list to parse return statements"

        # Assignment or function call
        else:
            prefix = Expr.parse_prefix(lexer)
            if type(prefix) is FuncCallExpr:
                return FuncCallStmt(prefix)
            return AssignStmt.parse_with_first(lexer, prefix)

    def codegen(self, info: FuncInfo):
        """Generate code for the statement."""
        pass

    def to_dict(self) -> dict[str, Any]:
        """Convert statement to dictionary using reflection."""
        from .lua_ast_util import obj_to_dict
        return obj_to_dict(self)


# ============================================================================
# Simple Statements
# ============================================================================

class EmptyStmt(Stmt):
    @classmethod
    def parse(cls, lexer: Lexer) -> EmptyStmt:
        lexer.consume("SEMICOLON")
        return cls()

    def codegen(self, info: FuncInfo):
        pass


# TODO
class BreakStmt(Stmt):
    """Break statement."""
    line: int

    def __init__(self, line: int = 0):
        self.line = line

    @classmethod
    def parse(cls, lexer: Lexer) -> BreakStmt:
        token = lexer.consume("BREAK")
        return cls(token.line)

    def codegen(self, info: FuncInfo):
        # TODO: Implement break - needs loop context to know where to jump
        # For now, just emit a JMP instruction with placeholder offset
        CodegenInst.jmp(info, 0)


class ReturnStmt(Stmt):
    @staticmethod
    def parse_list(lexer: Lexer) -> list[Expr]:
        lexer.consume("RETURN")
        if (token := lexer.current()) and token.type != "SEMICOLON" and not token.is_end():
            return Expr.parse_list(lexer)
        return []


class FuncCallStmt(Stmt):
    func_call: FuncCallExpr

    def __init__(self, func_call: FuncCallExpr):
        self.func_call = func_call

    def codegen(self, info: FuncInfo):
        # FuncCallExpr.codegen already handles register allocation/deallocation
        # when reg == -1 (default), so we don't need to free_reg here
        self.func_call.codegen(info)


# ============================================================================
# Block Statements
# ============================================================================

class DoStmt(Stmt):
    """Do-end block statement."""
    block: Block

    def __init__(self, block: Block):
        self.block = block

    @classmethod
    def parse(cls, lexer: Lexer) -> DoStmt:
        from .block import Block

        lexer.consume("DO")
        block = Block.parse(lexer)
        lexer.consume("END")
        return cls(block)

    def codegen(self, info: FuncInfo):
        info.enter_scope()
        self.block.codegen(info)
        info.exit_scope()


class WhileStmt(Stmt):
    """While loop statement."""
    exp: Expr
    block: Block

    def __init__(self, exp: Expr, block: Block):
        self.exp = exp
        self.block = block

    @classmethod
    def parse(cls, lexer: Lexer) -> WhileStmt:
        from .block import Block

        lexer.consume("WHILE")
        exp = Expr.parse(lexer)
        lexer.consume("DO")
        block = Block.parse(lexer)
        lexer.consume("END")
        return cls(exp, block)

    def codegen(self, info: FuncInfo):
        pc_start = info.current_pc()

        # Evaluate condition
        cond_reg = info.alloc_reg()
        self.exp.codegen(info, cond_reg)

        # Test condition: if true, skip JMP (continue loop); if false,
        # execute JMP (exit loop)
        CodegenInst.test(info, cond_reg, 1)
        pc_jmp = info.current_pc()
        # Placeholder jump to end if condition is false
        CodegenInst.jmp(info, 0)
        info.free_reg()

        # Loop body
        info.enter_scope()
        self.block.codegen(info)
        info.exit_scope()

        CodegenInst.jmp(info, pc_start - info.current_pc() - 1)

        # Patch the exit jump
        pc_end = info.current_pc()
        info.insts[pc_jmp].set_sbx(pc_end - pc_jmp - 1)


class RepeatStmt(Stmt):
    """Repeat-until loop statement."""
    block: Block
    exp: Expr

    def __init__(self, block: Block, exp: Expr):
        self.block = block
        self.exp = exp

    @classmethod
    def parse(cls, lexer: Lexer) -> RepeatStmt:
        from .block import Block

        lexer.consume("REPEAT")
        block = Block.parse(lexer)
        lexer.consume("UNTIL")
        exp = Expr.parse(lexer)
        return cls(block, exp)

    def codegen(self, info: FuncInfo):
        start_pc = info.current_pc()

        # Loop body
        info.enter_scope()
        self.block.codegen(info)

        # Evaluate condition
        cond_reg = info.alloc_reg()
        self.exp.codegen(info, cond_reg)
        info.exit_scope()

        # Test condition: if true, skip JMP (exit loop); if false,
        # execute JMP (repeat)
        CodegenInst.test(info, cond_reg, 1)
        CodegenInst.jmp(info, start_pc - info.current_pc() - 1)

        info.free_reg()


class IfStmt(Stmt):
    """If-then-elseif-else-end statement."""
    exps: list[Expr]
    blocks: list[Block]

    def __init__(self, exps: list[Expr], blocks: list[Block]):
        self.exps = exps
        self.blocks = blocks

    @classmethod
    def parse(cls, lexer: Lexer) -> IfStmt:
        """Parse if-then-elseif-else-end statement."""
        from .block import Block

        exps: list[Expr] = []
        blocks: list[Block] = []

        lexer.consume("IF")
        exps.append(Expr.parse(lexer))
        lexer.consume("THEN")
        blocks.append(Block.parse(lexer))

        # Handle elseif clauses
        while lexer.current().type == "ELSEIF":
            lexer.consume("ELSEIF")
            exps.append(Expr.parse(lexer))
            lexer.consume("THEN")
            blocks.append(Block.parse(lexer))

        # Handle else clause
        if lexer.current().type == "ELSE":
            lexer.consume("ELSE")
            exps.append(TrueExpr())  # Use TrueExp as condition for else
            blocks.append(Block.parse(lexer))

        lexer.consume("END")
        return cls(exps, blocks)

    def codegen(self, info: FuncInfo):
        jmp_to_ends: list[int] = []

        for i in range(len(self.exps)):
            # Evaluate condition (skip for else clause with TrueExp)
            if i < len(self.exps) - 1 or type(self.exps[i]).__name__ != 'TrueExp':
                cond_reg = info.alloc_reg()
                self.exps[i].codegen(info, cond_reg)

                # Test condition: if true, skip JMP (execute this block);
                # if false, execute JMP (try next branch)
                CodegenInst.test(info, cond_reg, 1)
                pc_jmp_to_next = info.current_pc()
                CodegenInst.jmp(info, 0)  # Placeholder jump to next branch
                info.free_reg()
            else:
                pc_jmp_to_next = None

            # Execute block
            info.enter_scope()
            self.blocks[i].codegen(info)
            info.exit_scope()

            if i < len(self.exps) - 1:
                jmp_to_ends.append(info.current_pc())
                CodegenInst.jmp(info, 0)  # Placeholder

            if pc_jmp_to_next is not None:
                pc_next = info.current_pc()
                info.insts[pc_jmp_to_next].set_sbx(pc_next - pc_jmp_to_next - 1)

        # Patch all jumps to end
        pc_end = info.current_pc()
        for jmp_pc in jmp_to_ends:
            info.insts[jmp_pc].set_sbx(pc_end - jmp_pc - 1)

# ============================================================================
# Loop Statements
# ============================================================================


class ForStmt(Stmt):
    @classmethod
    def parse(cls, lexer: Lexer) -> ForNumStat | ForInStat:
        lexer.consume("FOR")
        varname = NameExpr.parse(lexer)

        # After parsing first variable, check what follows
        if lexer.current().type == "ASSIGN":
            return ForNumStat.parse_with_name(lexer, varname)
        else:  # COMMA or IN
            return ForInStat.parse_with_name(lexer, varname)

    def codegen(self, info: FuncInfo):
        # This should never be called as parse() returns ForNumStat
        # or ForInStat
        raise RuntimeError("ForStat.codegen should not be called directly")


class ForNumStat(Stmt):
    """for var = init, limit [, step] do ... end"""
    varname: NameExpr
    init_expr: Expr
    limit_expr: Expr
    step_expr: Expr | None
    block: Block

    def __init__(self, varname: NameExpr, init_expr: Expr, limit_expr: Expr, step_expr: Expr | None, block: Block):
        self.varname = varname
        self.init_expr = init_expr
        self.limit_expr = limit_expr
        self.step_expr = step_expr
        self.block = block

    @classmethod
    def parse_with_name(cls, lexer: Lexer, varname: NameExpr) -> ForNumStat:
        from .block import Block
        lexer.consume("ASSIGN")
        init_expr = Expr.parse(lexer)
        lexer.consume("COMMA")
        limit_expr = Expr.parse(lexer)

        step_expr = None
        if lexer.current().type == "COMMA":
            lexer.consume("COMMA")
            step_expr = Expr.parse(lexer)

        lexer.consume("DO")
        block = Block.parse(lexer)
        lexer.consume("END")
        return cls(varname, init_expr, limit_expr, step_expr, block)

    def codegen(self, info: FuncInfo):
        info.enter_scope()

        # Allocate registers for loop variables: index, limit, step
        idx_reg = info.alloc_reg()
        limit_reg = info.alloc_reg()
        step_reg = info.alloc_reg()

        # Initialize loop variables
        self.init_expr.codegen(info, idx_reg)
        self.limit_expr.codegen(info, limit_reg)
        if self.step_expr:
            self.step_expr.codegen(info, step_reg)
        else:
            # Default step is 1
            CodegenInst.load_k(info, step_reg, 1)

        # Add loop variable to scope
        info.add_local_var(self.varname.name)

        # FORPREP instruction
        pc_forprep = info.current_pc()
        CodegenInst.forprep(info, idx_reg, 0)  # Placeholder jump

        # Loop body
        self.block.codegen(info)

        # FORLOOP instruction
        pc_forloop = info.current_pc()
        offset = pc_forloop - pc_forprep

        CodegenInst.forloop(info, idx_reg, -offset)
        info.insts[pc_forprep].set_sbx(offset - 1)

        info.exit_scope()


class ForInStat(Stmt):
    """for vars in expr list do ... end"""
    var_names: list[NameExpr]
    exprs: list[Expr]
    block: Block

    def __init__(self, var_names: list[NameExpr], exps: list[Expr], block: Block):
        self.var_names = var_names
        self.exprs = exps
        self.block = block

    @classmethod
    def parse_with_name(cls, lexer: Lexer, first_var: NameExpr) -> ForInStat:
        from .block import Block

        var_names = [first_var]
        while lexer.current().type == "COMMA":
            lexer.consume()
            var_names.append(NameExpr.parse(lexer))

        lexer.consume("IN")
        exprs = Expr.parse_list(lexer)
        lexer.consume("DO")

        block = Block.parse(lexer)
        lexer.consume("END")

        return cls(var_names, exprs, block)

    def codegen(self, info: FuncInfo):
        info.enter_scope()

        reg = info.used_regs

        iter_decl = LocalVarDeclStat([NameExpr("(for generator)"), NameExpr("(for state)"), NameExpr("(for control)")], self.exprs)
        iter_decl.codegen(info)

        # Add loop variables to scope
        for varname in self.var_names:
            info.add_local_var(varname.name)

        # info.alloc_reg() # func

        pc_jump = info.current_pc()
        CodegenInst.jmp(info, 0)  # Placeholder

        # Loop body
        self.block.codegen(info)

        # TFORLOOP instruction
        pc_tforloop = info.current_pc()
        CodegenInst.tforloop(info, reg, len(self.var_names))

        CodegenInst.jmp(info, pc_jump - pc_tforloop - 1)

        # Patch jump to end
        info.insts[pc_jump].set_sbx(pc_tforloop - pc_jump - 1)

        # info.free_reg()

        info.exit_scope()


# ============================================================================
# Declaration and Assignment Statements
# ============================================================================

class LocalStmt(Stmt):
    @classmethod
    def parse(cls, lexer: Lexer) -> LocalVarDeclStat | LocalFuncDefStat:
        lexer.consume("LOCAL")

        if lexer.current().type == "FUNCTION":
            return LocalFuncDefStat.parse(lexer)
        else:
            return LocalVarDeclStat.parse(lexer)


class LocalVarDeclStat(Stmt):
    """local vars [= exp list]"""
    var_names: list[NameExpr]
    exprs: list[Expr]

    def __init__(self, var_names: list[NameExpr], exps: list[Expr]):
        self.var_names = var_names
        self.exprs = exps

    @classmethod
    def parse(cls, lexer: Lexer) -> LocalVarDeclStat:
        var_names = [NameExpr.parse(lexer)]
        while lexer.current().type == "COMMA":
            lexer.consume()
            var_names.append(NameExpr.parse(lexer))

        exps = []
        if lexer.current().type == "ASSIGN":
            lexer.consume()
            exps = Expr.parse_list(lexer)

        return cls(var_names, exps)

    def codegen(self, info: FuncInfo):
         for i in range(len(self.var_names)):
            var = info.add_local_var(self.var_names[i].name)
            if i == len(self.exprs) - 1 and type(self.exprs[i]) is FuncCallExpr:
                for j in range(i + 1, len(self.var_names)):
                    info.add_local_var(self.var_names[j].name)
                self.exprs[i].codegen(info, var.reg_idx, len(self.var_names) - i)
                break
            if i < len(self.exprs):
                self.exprs[i].codegen(info, var.reg_idx)
            else:
                CodegenInst.load_nil(info, var.reg_idx, 1)


class AssignStmt(Stmt):
    """varlist = expr list"""
    var_list: list[Expr]
    expr_list: list[Expr]

    def __init__(self, varlist: list[Expr], expr_list: list[Expr]):
        self.var_list = varlist
        self.expr_list = expr_list

    @classmethod
    def parse_with_first(cls, lexer: Lexer, first_var: Expr) -> AssignStmt:
        varlist = [first_var]
        while lexer.current().type == "COMMA":
            lexer.consume()
            varlist.append(Expr.parse(lexer))

        lexer.consume("ASSIGN")
        expr_list = Expr.parse_list(lexer)

        return cls(varlist, expr_list)

    @classmethod
    def parse_func(cls, lexer: Lexer) -> AssignStmt:
        """function [obj.]name[:method] body end"""
        lexer.consume("FUNCTION")
        exp = NameExpr.parse(lexer)

        while lexer.current().type == "DOT":
            exp = TableAccessExpr.parse_dot(lexer, exp)

        # Handle obj:method (inserts 'self' as first parameter)
        colon = False
        if lexer.current().type == "COLON":
            exp = TableAccessExpr.parse_colon(lexer, exp)
            colon = True

        return cls([exp], [FuncDefExpr.parse(lexer, colon=colon)])

    def codegen(self, info: FuncInfo):
        num_exprs = len(self.expr_list)
        num_vars = len(self.var_list)

        exp_regs: list[int] = []
        for i in range(num_exprs):
            reg = info.alloc_reg()
            self.expr_list[i].codegen(info, reg)
            exp_regs.append(reg)

        for i in range(num_vars):
            var = self.var_list[i]
            if i < num_exprs:
                val_reg = exp_regs[i]
            else:
                val_reg = info.alloc_reg()
                CodegenInst.load_nil(info, val_reg, 1)
                exp_regs.append(val_reg)

            if isinstance(var, NameExpr):
                local = info.get_local_var(var.name)
                if local:
                    CodegenInst.move(info, local.reg_idx, val_reg)
                else:
                    upval_idx = info.idx_of_upval(var.name)
                    if upval_idx is not None:
                        CodegenInst.set_upval(info, val_reg, upval_idx)
                    else:
                        idx = info.idx_of_const(var.name)
                        CodegenInst.set_global(info, val_reg, idx)
            elif isinstance(var, TableAccessExpr):
                var.codegen_set(info, val_reg)
            else:
                raise NotImplementedError(f"Assignment to {type(var).__name__} not implemented.")

        for _ in exp_regs:
            info.free_reg()


class LocalFuncDefStat(Stmt):
    """local function name func body end"""
    name: NameExpr
    body: FuncDefExpr

    def __init__(self, name: NameExpr, body: FuncDefExpr):
        self.name = name
        self.body = body

    @classmethod
    def parse(cls, lexer: Lexer) -> LocalFuncDefStat:
        lexer.consume("FUNCTION")
        name = NameExpr.parse(lexer)
        body = FuncDefExpr.parse(lexer)
        return cls(name, body)

    def codegen(self, info: FuncInfo):
        local = info.add_local_var(self.name.name)
        self.body.codegen(info, local.reg_idx)
