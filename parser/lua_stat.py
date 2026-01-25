"""Lua statement AST nodes and parser.

This module defines all statement types in Lua and their parsing logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from .lua_lexer import Lexer
from .lua_exp import Expr, NameExp, FuncCallExp, TrueExp, NameExp, FuncDefExp, TableAccessExp

if TYPE_CHECKING:
    from .lua_block import Block

from codegen.func import FuncInfo
from codegen.inst import CodegenInst

class Stat:
    """Base class for all Lua statements."""
    
    @staticmethod
    def parse(lexer: Lexer) -> Stat:
        """Parse a statement based on the current token."""        
        token = lexer.current()
        
        # Empty statement
        if token.type == "SEMICOLON":
            return EmptyStat.parse(lexer)
        
        # Break statement
        elif token.type == "BREAK":
            return BreakStat.parse(lexer)
        
        # Do block
        elif token.type == "DO":
            return DoStat.parse(lexer)
        
        # While loop
        elif token.type == "WHILE":
            return WhileStat.parse(lexer)
        
        # Repeat-until loop
        elif token.type == "REPEAT":
            return RepeatStat.parse(lexer)
        
        # If statement
        elif token.type == "IF":
            return IfStat.parse(lexer)
        
        # For loop (numeric or iterator)
        elif token.type == "FOR":
            return ForStat.parse(lexer)
        
        # Function definition
        elif token.type == "FUNCTION":
            return AssignStat.parse_func(lexer)
        
        # Local declaration
        elif token.type == "LOCAL":
            return LocalStat.parse(lexer)
        
        # Return statement (should not be called directly)
        elif token.type == "RETURN":
            assert False, "Use ReturnStat.parse_list to parse return statements"
        
        # Assignment or function call
        else:
            prefix = Expr.parse_prefix(lexer)
            if type(prefix) is FuncCallExp:
                return prefix
            return AssignStat.parse(lexer, prefix)
        
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

class EmptyStat(Stat):
    @classmethod
    def parse(cls, lexer: Lexer) -> EmptyStat:
        lexer.consume("SEMICOLON")
        return cls()
    
    def codegen(self, info: FuncInfo):
        pass


# TODO
class BreakStat(Stat):
    """Break statement."""
    line: int

    def __init__(self, line: int = 0):
        self.line = line

    @classmethod
    def parse(cls, lexer: Lexer) -> BreakStat:
        token = lexer.consume("BREAK")
        return cls(token.line)
    
    def codegen(self, info: FuncInfo):
        # TODO: Implement break - needs loop context to know where to jump
        # For now, just emit a JMP instruction with placeholder offset
        CodegenInst.jmp(info, 0)


class ReturnStat(Stat):
    @staticmethod
    def parse_list(lexer: Lexer) -> list[Expr]:
        lexer.consume("RETURN")
        if (token := lexer.current()) and token.type != "SEMICOLON" and not token.is_end():
            return Expr.parse_list(lexer)
        return []


# ============================================================================
# Block Statements
# ============================================================================

class DoStat(Stat):
    """Do-end block statement."""
    block: Block

    def __init__(self, block: Block):
        self.block = block

    @classmethod
    def parse(cls, lexer: Lexer) -> DoStat:
        from .lua_block import Block

        lexer.consume("DO")
        block = Block.parse(lexer)
        lexer.consume("END")
        return cls(block)
    
    def codegen(self, info: FuncInfo):
        info.enter_scope()
        self.block.codegen(info)
        info.exit_scope()


class WhileStat(Stat):
    """While loop statement."""
    exp: Expr
    block: Block

    def __init__(self, exp: Expr, block: Block):
        self.exp = exp
        self.block = block

    @classmethod
    def parse(cls, lexer: Lexer) -> WhileStat:
        from .lua_block import Block

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
        
        # Test condition: if true, skip JMP (continue loop); if false, execute JMP (exit loop)
        CodegenInst.test(info, cond_reg, 1)
        pc_jmp = info.current_pc()
        CodegenInst.jmp(info, 0)  # Placeholder - jump to end if condition is false
        info.free_reg()

        # Loop body
        info.enter_scope()
        self.block.codegen(info)
        info.exit_scope()

        CodegenInst.jmp(info, pc_start - info.current_pc() - 1)
        
        # Patch the exit jump
        pc_end = info.current_pc()
        info.insts[pc_jmp].set_sbx(pc_end - pc_jmp - 1)


class RepeatStat(Stat):
    """Repeat-until loop statement."""
    block: Block
    exp: Expr

    def __init__(self, block: Block, exp: Expr):
        self.block = block
        self.exp = exp

    @classmethod
    def parse(cls, lexer: Lexer) -> RepeatStat:
        from .lua_block import Block

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
        
        # Test condition: if true, skip JMP (exit loop); if false, execute JMP (repeat)
        CodegenInst.test(info, cond_reg, 1)
        CodegenInst.jmp(info, start_pc - info.current_pc() - 1)
        
        info.free_reg()


class IfStat(Stat):
    """If-then-elseif-else-end statement."""
    exps: list[Expr]
    blocks: list[Block]

    def __init__(self, exps: list[Expr], blocks: list[Block]):
        self.exps = exps
        self.blocks = blocks
    
    @classmethod
    def parse(cls, lexer: Lexer) -> IfStat:
        """Parse if-then-elseif-else-end statement."""
        from .lua_block import Block

        exps = []
        blocks = []
        
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
            exps.append(TrueExp())  # Use TrueExp as condition for else
            blocks.append(Block.parse(lexer))
        
        lexer.consume("END")
        return cls(exps, blocks)
    
    def codegen(self, info: FuncInfo):
        jmp_to_ends = []
        
        for i in range(len(self.exps)):
            # Evaluate condition (skip for else clause with TrueExp)
            if i < len(self.exps) - 1 or type(self.exps[i]).__name__ != 'TrueExp':
                cond_reg = info.alloc_reg()
                self.exps[i].codegen(info, cond_reg)
                
                # Test condition: if true, skip JMP (execute this block); if false, execute JMP (try next branch)
                CodegenInst.test(info, cond_reg, 1)
                pc_jmp_to_next = info.current_pc()
                CodegenInst.jmp(info, 0)  # Placeholder - jump to next branch if condition is false
                info.free_reg()
            else:
                pc_jmp_to_next = None
            
            # Execute block
            info.enter_scope()
            self.blocks[i].codegen(info)
            info.exit_scope()
            
            # Jump to end after executing block
            if i < len(self.exps) - 1:
                jmp_to_ends.append(info.current_pc())
                CodegenInst.jmp(info, 0)  # Placeholder
            
            # Patch jump to next condition/block
            if pc_jmp_to_next is not None:
                pc_next = info.current_pc()
                info.insts[pc_jmp_to_next] = info.insts[pc_jmp_to_next] | ((pc_next - pc_jmp_to_next - 1) << 14)
        
        # Patch all jumps to end
        pc_end = info.current_pc()
        for jmp_pc in jmp_to_ends:
            info.insts[jmp_pc] = info.insts[jmp_pc] | ((pc_end - jmp_pc - 1) << 14)

# ============================================================================
# Loop Statements
# ============================================================================

class ForStat(Stat):
    @staticmethod
    def parse(lexer: Lexer) -> ForNumStat | ForInStat:
        lexer.consume("FOR")
        varname = NameExp.parse(lexer)
        
        # After parsing first variable, check what follows
        if lexer.current().type == "ASSIGN":
            return ForNumStat.parse(lexer, varname)
        else:  # COMMA or IN
            return ForInStat.parse(lexer, varname)
        
    def codegen(self, info: FuncInfo):
        # This should never be called as parse() returns ForNumStat or ForInStat
        raise RuntimeError("ForStat.codegen should not be called directly")


class ForNumStat(Stat):
    """for var = init, limit [, step] do ... end"""
    varname: NameExp
    initexp: Expr
    limitexp: Expr
    stepexp: Expr | None
    block: Block

    def __init__(self, varname: NameExp, initexp: Expr, limitexp: Expr, stepexp: Expr | None, block: Block):
        self.varname = varname
        self.initexp = initexp
        self.limitexp = limitexp
        self.stepexp = stepexp
        self.block = block

    @classmethod
    def parse(cls, lexer: Lexer, varname: NameExp) -> ForNumStat:
        from .lua_block import Block
        lexer.consume("ASSIGN")
        initexp = Expr.parse(lexer)
        lexer.consume("COMMA")
        limitexp = Expr.parse(lexer)
        
        stepexp = None
        if lexer.current().type == "COMMA":
            lexer.consume()
            stepexp = Expr.parse(lexer)
        
        lexer.consume("DO")
        block = Block.parse(lexer)
        lexer.consume("END")
        return cls(varname, initexp, limitexp, stepexp, block)
    
    def codegen(self, info: FuncInfo):
        info.enter_scope()
        
        # Allocate registers for loop variables: index, limit, step
        idx_reg = info.alloc_reg()
        limit_reg = info.alloc_reg()
        step_reg = info.alloc_reg()
        
        # Initialize loop variables
        self.initexp.codegen(info, idx_reg)
        self.limitexp.codegen(info, limit_reg)
        if self.stepexp:
            self.stepexp.codegen(info, step_reg)
        else:
            # Default step is 1
            CodegenInst.load_k(info, step_reg, 1)
        
        # Add loop variable to scope
        loop_var = info.add_local_var(self.varname.name)
        
        # FORPREP instruction
        pc_forprep = info.current_pc()
        CodegenInst.forprep(info, idx_reg, 0)  # Placeholder jump
        
        # Loop body
        self.block.codegen(info)
        
        # FORLOOP instruction
        pc_forloop = info.current_pc()
        CodegenInst.forloop(info, idx_reg, pc_forprep - pc_forloop - 1)
        
        # Patch FORPREP to jump past FORLOOP
        info.insts[pc_forprep] = (info.insts[pc_forprep] & 0x3FFF) | ((pc_forloop - pc_forprep) << 14)
        
        info.exit_scope()


class ForInStat(Stat):
    """for vars in explist do ... end"""
    varnames: list[NameExp]
    exps: list[Expr]
    block: Block

    def __init__(self, varnames: list[NameExp], exps: list[Expr], block: Block):
        self.varnames = varnames
        self.exps = exps
        self.block = block

    @classmethod
    def parse(cls, lexer: Lexer, first_var: NameExp) -> ForInStat:
        from .lua_block import Block

        varnames = [first_var]
        while lexer.current().type == "COMMA":
            lexer.consume()
            varnames.append(NameExp.parse(lexer))
        
        lexer.consume("IN")
        exps = Expr.parse_list(lexer)
        lexer.consume("DO")

        block = Block.parse(lexer)
        lexer.consume("END")

        return cls(varnames, exps, block)
    
    def codegen(self, info: FuncInfo):
        info.enter_scope()
        
        # Allocate registers for iterator function, state, control variable
        iter_reg = info.alloc_reg()
        state_reg = info.alloc_reg()
        ctrl_reg = info.alloc_reg()
        
        # Evaluate iterator expressions
        for i, exp in enumerate(self.exps[:3]):
            exp.codegen(info, iter_reg + i)
        
        # Add loop variables to scope
        for varname in self.varnames:
            info.add_local_var(varname.name)
        
        # TFORLOOP instruction
        pc_tforloop = info.current_pc()
        CodegenInst.tforloop(info, iter_reg, len(self.varnames))
        
        pc_jmp_to_end = info.current_pc()
        CodegenInst.jmp(info, 0)  # Placeholder
        
        # Loop body
        self.block.codegen(info)
        
        # Jump back to TFORLOOP
        CodegenInst.jmp(info, pc_tforloop - info.current_pc() - 1)
        
        # Patch jump to end
        pc_end = info.current_pc()
        info.insts[pc_jmp_to_end] = info.insts[pc_jmp_to_end] | ((pc_end - pc_jmp_to_end - 1) << 14)
        
        info.exit_scope()


# ============================================================================
# Declaration and Assignment Statements
# ============================================================================

class LocalStat(Stat):
    @staticmethod
    def parse(lexer: Lexer) -> LocalVarDeclStat | LocalFuncDefStat:
        lexer.consume("LOCAL")
        
        if lexer.current().type == "FUNCTION":
            return LocalFuncDefStat.parse(lexer)
        else:
            return LocalVarDeclStat.parse(lexer)


class LocalVarDeclStat(Stat):
    """local vars [= explist]"""
    varnames: list[NameExp]
    exps: list[Expr]

    def __init__(self, varnames: list[NameExp], exps: list[Expr]):
        self.varnames = varnames
        self.exps = exps

    @classmethod
    def parse(cls, lexer: Lexer) -> LocalVarDeclStat:
        varnames = [NameExp.parse(lexer)]
        while lexer.current().type == "COMMA":
            lexer.consume()
            varnames.append(NameExp.parse(lexer))

        exps = []
        if lexer.current().type == "ASSIGN":
            lexer.consume()
            exps = Expr.parse_list(lexer)
        
        return cls(varnames, exps)
    
    def codegen(self, info: FuncInfo):
        for i in range(len(self.varnames)):
            local = info.add_local_var(self.varnames[i].name)
            if i < len(self.exps):
                self.exps[i].codegen(info, local.reg_idx)
            else:
                CodegenInst.load_nil(info, local.reg_idx, 1)


class AssignStat(Stat):
    """varlist = explist"""
    varlist: list[Expr]
    explist: list[Expr]

    def __init__(self, varlist: list[Expr], explist: list[Expr]):
        self.varlist = varlist
        self.explist = explist

    @classmethod
    def parse(cls, lexer: Lexer, first_var: Expr) -> AssignStat:
        varlist = [first_var]
        while lexer.current().type == "COMMA":
            lexer.consume()
            varlist.append(Expr.parse(lexer))
        
        lexer.consume("ASSIGN")
        explist = Expr.parse_list(lexer)
        
        return cls(varlist, explist)
    
    @classmethod
    def parse_func(cls, lexer: Lexer) -> AssignStat:
        """function [obj.]name[:method] body end"""
        lexer.consume("FUNCTION")
        exp = NameExp.parse(lexer)

        while lexer.current().type == "DOT":
            exp = TableAccessExp.parse_dot(lexer, exp)

        # Handle obj:method (inserts 'self' as first parameter)
        colon = False
        if lexer.current().type == "COLON":
            exp = TableAccessExp.parse_colon(lexer, exp)
            colon = True
        
        return cls([exp], [FuncDefExp.parse(lexer, colon=colon)])
    
    def codegen(self, info: FuncInfo):
        # Allocate registers for all RHS expressions
        nexp = len(self.explist)
        nvar = len(self.varlist)
        
        # Generate code for RHS expressions
        exp_regs = []
        for i in range(nexp):
            reg = info.alloc_reg()
            self.explist[i].codegen(info, reg)
            exp_regs.append(reg)
        
        # Assign to LHS variables
        for i in range(nvar):
            var = self.varlist[i]
            if i < nexp:
                val_reg = exp_regs[i]
            else:
                # No value for this variable, assign nil
                val_reg = info.alloc_reg()
                CodegenInst.load_nil(info, val_reg, 1)
                exp_regs.append(val_reg)
            
            if isinstance(var, NameExp):
                local = info.get_local_var(var.name)
                if local:
                    CodegenInst.move(info, local.reg_idx, val_reg)
                else:
                    upval_idx = info.idx_of_upval(var.name)
                    if upval_idx is not None:
                        CodegenInst.set_upvalue(info, val_reg, upval_idx)
                    else:
                        # Global variable
                        idx = info.idx_of_const(var.name)
                        CodegenInst.set_global(info, val_reg, idx)
            elif isinstance(var, TableAccessExp):
                var.codegen_set(info, val_reg)
            else:
                raise NotImplementedError(f"Assignment to {type(var).__name__} not implemented.")
        
        # Free all allocated registers
        for _ in exp_regs:
            info.free_reg()

class LocalFuncDefStat(Stat):
    """local function name funcbody end"""
    name: NameExp
    funcbody: FuncDefExp

    def __init__(self, name: NameExp, funcbody: FuncDefExp):
        self.name = name
        self.funcbody = funcbody

    @classmethod
    def parse(cls, lexer: Lexer) -> LocalFuncDefStat:
        lexer.consume("FUNCTION")
        name = NameExp.parse(lexer)
        funcbody = FuncDefExp.parse(lexer)
        return cls(name, funcbody)
    
    def codegen(self, info: FuncInfo):
        # Add local variable first
        local = info.add_local_var(self.name.name)
        # Generate function closure
        self.funcbody.codegen(info, local.reg_idx)

