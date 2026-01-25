"""Lua expression AST nodes and parser.

This module defines all expression types in Lua and their parsing logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .lua_lexer import Lexer
    from .lua_stat import Block

from codegen.func import FuncInfo
from codegen.inst import CodegenInst

# Operator precedence table (higher number = higher precedence)
BINARY_PRECEDENCE = {
    "OR": 1,
    "AND": 2,
    "LT": 3, "GT": 3, "LE": 3, "GE": 3, "NE": 3, "EQ": 3,
    "BOR": 4,
    "BXOR": 5,
    "BAND": 6,
    "SHL": 7, "SHR": 7,
    "CONCAT": 8,  # Right associative
    "PLUS": 9, "MINUS": 9, "UNM": 9,
    "MULTIPLY": 10, "DIVIDE": 10, "IDIV": 10, "MOD": 10,
    "POW": 11,  # Right associative
}

UNARY_PRECEDENCE = 12  # Unary operators have higher precedence than all binary


class Expr:
    def to_dict(self) -> dict[str, Any]:
        from .lua_ast_util import obj_to_dict
        return obj_to_dict(self)
    
    @staticmethod
    def parse(lexer: Lexer) -> Expr:
        return Expr.parse_subexp(lexer, 0)

    @staticmethod
    def parse_list(lexer: Lexer) -> list[Expr]:
        exps = [Expr.parse(lexer)]
        while lexer.current().type == "COMMA":
            lexer.consume()
            exps.append(Expr.parse(lexer))
        
        return exps
    
    @staticmethod
    def parse_prefix(lexer: Lexer) -> Expr:
        """Parse a prefix expression (identifier or parenthesized expression)."""
        token = lexer.current()
        if token.type == "IDENTIFIER":
            exp = NameExp.parse(lexer)
        elif token.type == "LPAREN":
            lexer.consume("LPAREN")
            exp = Expr.parse(lexer)
            lexer.consume("RPAREN")
        
        return Expr.parse_postfix(lexer, exp)
        
    @staticmethod
    def parse_postfix(lexer: Lexer, exp: Expr) -> Expr:
        """Parse postfix operators (field access, indexing, function calls)."""
        while token := lexer.current():
            if token.type == "LBRACKET":
                exp = TableAccessExp.parse_bracket(lexer, exp)
            elif token.type == "DOT":
                exp = TableAccessExp.parse_dot(lexer, exp)
            elif token.type in ("COLON", "LPAREN", "LBRACE", "STRING"):
                exp = FuncCallExp.parse(lexer, exp)
            else:
                return exp
            
    @staticmethod
    def parse_subexp(lexer: Lexer, limit: int) -> Expr:
        """Parse sub-expression with operator precedence climbing algorithm."""
        # Parse unary operators or simple expression
        if lexer.current().type in ("NOT", "MINUS", "LEN", "BXOR"):
            exp = UnaryOpExp.parse(lexer)
        else:
            exp = Expr._parse_simple_exp(lexer)

        # Parse binary operators with precedence
        while (op := lexer.current().type) and (lbp := BINARY_PRECEDENCE.get(op, -1)) > limit:
            lexer.consume()  # consume operator
            # Right associative operators (POW, CONCAT) use lbp-1
            rbp = lbp - 1 if op in ("POW", "CONCAT") else lbp
            right = Expr.parse_subexp(lexer, rbp)
            exp = BinaryOpExp(op, exp, right)
        return exp
    
    @staticmethod
    def _parse_simple_exp(lexer: Lexer) -> Expr:
        token = lexer.current()
        
        # Literal tokens
        if token.type == "NIL":
            return NilExp.parse(lexer)
        elif token.type == "TRUE":
            return TrueExp.parse(lexer)
        elif token.type == "FALSE":
            return FalseExp.parse(lexer)
        elif token.type == "VARARG":
            return VarargExp.parse(lexer)
        
        # Numbers
        elif token.type == "NUMBER":
            # TODO: Distinguish integer vs float
            return Expr.parse_number(lexer)
        
        # Strings
        elif token.type == "STRING":
            return StringExp.parse(lexer)
        
        # Table constructor
        elif token.type == "LBRACE":
            return TableConstructorExp.parse(lexer)
        
        # Anonymous Function
        elif token.type == "FUNCTION":
            lexer.consume("FUNCTION")
            return FuncDefExp.parse(lexer)
        
        # Parenthesized expression
        elif token.type == "LPAREN":
            return ParenExp.parse(lexer)
        
        # Identifier (with potential postfix)
        elif token.type == "IDENTIFIER":
            return Expr.parse_postfix(lexer, NameExp.parse(lexer))
        else:
            raise SyntaxError(f"Unexpected token: {token.type}")
        
    @classmethod
    def parse_number(cls, lexer: Lexer) -> Expr:
        """Parse a numeric literal (integer or float, decimal or hex)."""
        token = lexer.current()
        value_str = token.value
        
        # Hexadecimal number
        if value_str.startswith(('0x', '0X')):
            if '.' in value_str or 'p' in value_str or 'P' in value_str:
                return FloatExp.parse_hex(lexer)
            else:
                return IntegerExp.parse_hex(lexer)
        # Decimal number
        else:
            if '.' in value_str or 'e' in value_str or 'E' in value_str:
                return FloatExp.parse(lexer)
            else:
                return IntegerExp.parse(lexer)
            
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        """Generate code for this expression."""
        pass


# ============================================================================
# Literal Expressions
# ============================================================================

class NilExp(Expr):
    @classmethod
    def parse(cls, lexer: Lexer) -> NilExp:
        lexer.consume("NIL")
        return cls()
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_nil(info, reg, cnt if cnt else 1)

class TrueExp(Expr):
    @classmethod
    def parse(cls, lexer: Lexer):
        lexer.consume("TRUE")
        return cls()
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_bool(info, reg, 1, 0)


class FalseExp(Expr):
    @classmethod
    def parse(cls, lexer: Lexer):
        lexer.consume("FALSE")
        return cls()
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_bool(info, reg, 0, 0)


class VarargExp(Expr):
    @classmethod
    def parse(cls, lexer: Lexer):
        lexer.consume("VARARG")
        return cls()
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.vararg(info, reg, cnt)

class IntegerExp(Expr):
    value: int

    def __init__(self, value: int):
        self.value = value

    @classmethod
    def parse(cls, lexer: Lexer) -> IntegerExp:
        token = lexer.consume("NUMBER")
        return cls(int(token.value))
    
    @classmethod
    def parse_hex(cls, lexer: Lexer) -> IntegerExp:
        token = lexer.consume("NUMBER")
        return cls(int(token.value, 16))
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_k(info, reg, self.value)


class FloatExp(Expr):
    """Floating-point literal expression."""
    value: float

    def __init__(self, value: float):
        self.value = value

    @classmethod
    def parse(cls, lexer: Lexer) -> FloatExp:
        token = lexer.consume("NUMBER")
        return cls(float(token.value))
    
    @classmethod
    def parse_hex(cls, lexer: Lexer) -> FloatExp:
        token = lexer.consume("NUMBER")
        return cls(float.fromhex(token.value))
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_k(info, reg, self.value)


class StringExp(Expr):
    """String literal expression."""
    value: str

    def __init__(self, value: str):
        self.value = value
    
    @classmethod
    def parse(cls, lexer: Lexer) -> StringExp:
        token = lexer.consume("STRING")
        return cls(token.value)
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_k(info, reg, self.value)

class NameExp(Expr):
    """Variable name expression (identifier)."""
    name: str

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def parse(cls, lexer: Lexer) -> NameExp:
        token = lexer.consume("IDENTIFIER")
        return cls(token.value)
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        loc_var = info.get_local_var(self.name)
        if loc_var:
            CodegenInst.move(info, reg, loc_var.reg_idx)
            return
        upval_idx = info.idx_of_upval(self.name)
        if upval_idx is not None:
            CodegenInst.get_upval(info, reg, upval_idx)
            return
        idx = info.idx_of_const(self.name)
        CodegenInst.get_global(info, reg, idx)

# ============================================================================
# Operator Expressions
# ============================================================================

class UnaryOpExp(Expr):
    """Unary operator expression (not, -, #, ~)."""
    op: str
    exp: Expr

    def __init__(self, op: str, exp: Expr):
        self.op = op
        if self.op == "MINUS":
            self.op = "UNM"
        self.exp = exp

    @classmethod
    def parse(cls, lexer: Lexer) -> UnaryOpExp:
        token = lexer.consume()
        exp = Expr.parse_subexp(lexer, UNARY_PRECEDENCE)
        return cls(token.type, exp)
    
    def codegen(self, info, reg, cnt = 1):
        operand_reg = info.alloc_reg()
        self.exp.codegen(info, operand_reg)

        op_func = getattr(CodegenInst, self.op)
        if op_func:
            op_func(info, reg, operand_reg)
        else:
            raise NotImplementedError(f"Unary operator {self.op} not implemented.")
        
        info.free_reg()


class BinaryOpExp(Expr):
    """Binary operator expression."""
    op: str
    left: Expr
    right: Expr

    def __init__(self, op: str, left: Expr, right: Expr):
        self.op = op
        self.left = left
        self.right = right

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        if self.op == 'CONCAT':
            exprs: list[Expr] = []
            def collect(e: Expr):
                if type(e) is BinaryOpExp and e.op == 'CONCAT':
                    collect(e.left)
                    collect(e.right)
                else:
                    exprs.append(e)
            collect(self)
            
            start_reg = info.alloc_regs(len(exprs))
            for i, e in enumerate(exprs):
                e.codegen(info, start_reg + i)
            
            CodegenInst.concat(info, reg, start_reg, start_reg + len(exprs) - 1)
            info.free_regs(len(exprs))

        elif self.op in ('AND', 'OR'):
            self.left.codegen(info, reg)
            if self.op == 'AND':
                CodegenInst.test_set(info, reg, reg, 0)  # Jump if false
            else:  # OR
                CodegenInst.test_set(info, reg, reg, 1)  # Jump if true
 
            right_reg = info.alloc_reg()
            self.right.codegen(info, right_reg)
            CodegenInst.move(info, reg, right_reg)
            info.free_reg()

        elif self.op in ('EQ', 'NE', 'LT', 'LE', 'GT', 'GE'):
            # Comparison operators - result in boolean
            self.left.codegen(info, reg)
            right_reg = info.alloc_reg()
            self.right.codegen(info, right_reg)
            
            op_func = getattr(CodegenInst, self.op)
            if op_func:
                op_func(info, 1, reg, right_reg)  # Compare and skip if true
                CodegenInst.jmp(info, 1)  # Skip next instruction
                CodegenInst.load_bool(info, reg, 0, 1)  # Load false and skip
                CodegenInst.load_bool(info, reg, 1, 0)  # Load true
            
            info.free_reg()
        else:
            # Arithmetic operators
            self.left.codegen(info, reg)
            right_reg = info.alloc_reg()
            self.right.codegen(info, right_reg)
            
            op_func = getattr(CodegenInst, self.op)
            if op_func:
                op_func(info, reg, reg, right_reg)
            else:
                raise NotImplementedError(f"Binary operator {self.op} not implemented.")
        
            info.free_reg()


class ConcatExp(Expr):
    """String concatenation expression (deprecated, use BinaryOpExp)."""
    exps: list[Expr]

    def __init__(self, exps: list[Expr]):
        self.exps = exps

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        exp_regs = []
        for exp in self.exps:
            exp_reg = info.alloc_reg()
            exp.codegen(info, exp_reg)
            exp_regs.append(exp_reg)
        
        CodegenInst.concat(info, reg, exp_regs[0], len(exp_regs))
        
        for _ in exp_regs:
            info.free_reg()


# ============================================================================
# Complex Expressions
# ============================================================================

class ParenExp(Expr):
    exp: Expr

    def __init__(self, exp: Expr):
        self.exp = exp

    @classmethod
    def parse(cls, lexer: Lexer) -> ParenExp:
        lexer.consume("LPAREN")
        exp = Expr.parse(lexer)
        lexer.consume("RPAREN")
        return cls(exp)
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        self.exp.codegen(info, reg, cnt)


class TableConstructorExp(Expr):
    """Table constructor expression {...}."""
    key_exps: list[Expr | None]
    val_exps: list[Expr]

    def __init__(self, key_exps: list[Expr | None], val_exps: list[Expr]):
        self.key_exps = key_exps
        self.val_exps = val_exps

    @classmethod
    def parse(cls, lexer: Lexer) -> TableConstructorExp:
        key_exps = []
        val_exps = []
        lexer.consume("LBRACE")
        while lexer.current().type != "RBRACE":
            cls._parse_field(lexer, key_exps, val_exps)
            
            if lexer.current().type in ("COMMA", "SEMICOLON"):
                lexer.consume()
            else:
                break

        lexer.consume("RBRACE")
        return cls(key_exps, val_exps)
    
    @staticmethod
    def _parse_field(lexer: Lexer, key_exps: list[Expr | None], val_exps: list[Expr]) -> None:
        if lexer.current().type == "LBRACKET":
            # [exp] = exp
            lexer.consume("LBRACKET")
            key_exps.append(Expr.parse(lexer))
            lexer.consume("RBRACKET")
            lexer.consume("ASSIGN")
            val_exps.append(Expr.parse(lexer))
        else:
            exp = Expr.parse(lexer)
            if lexer.current().type == "ASSIGN":
                # name = exp
                if type(exp) is NameExp:
                    exp = StringExp(exp.name)
                lexer.consume("ASSIGN")
                key_exps.append(exp)
                val_exps.append(Expr.parse(lexer))
            else:
                # exp (array-style)
                key_exps.append(None)
                val_exps.append(exp)

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.new_table(info, reg, 0, 0)
        
        for key_exp, val_exp in zip(self.key_exps, self.val_exps):
            if key_exp:
                key_reg = info.alloc_reg()
                key_exp.codegen(info, key_reg)
            else:
                key_reg = 0  # Indicate array-style insertion
            
            val_reg = info.alloc_reg()
            val_exp.codegen(info, val_reg)
            
            CodegenInst.set_table(info, reg, key_reg, val_reg)
            
            if key_exp:
                info.free_reg()
            info.free_reg()


class TableAccessExp(Expr):
    prefix_exp: Expr
    key_exp: Expr

    def __init__(self, prefix_exp: Expr, key_exp: Expr):
        self.prefix_exp = prefix_exp
        self.key_exp = key_exp
        
    @classmethod
    def parse_bracket(cls, lexer: Lexer, prefix_exp: Expr) -> TableAccessExp:
        lexer.consume("LBRACKET")
        key_exp = Expr.parse(lexer)
        lexer.consume("RBRACKET")
        return cls(prefix_exp, key_exp)
    
    @classmethod
    def parse_dot(cls, lexer: Lexer, prefix_exp: Expr) -> TableAccessExp:
        lexer.consume("DOT")
        return cls(prefix_exp, NameExp.parse(lexer))
    
    @classmethod
    def parse_colon(cls, lexer: Lexer, prefix_exp: Expr) -> TableAccessExp:
        lexer.consume("COLON")
        return cls(prefix_exp, NameExp.parse(lexer))
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        prefix_reg = info.alloc_reg()
        self.prefix_exp.codegen(info, prefix_reg)
        
        key_reg = info.alloc_reg()
        self.key_exp.codegen(info, key_reg)
        
        CodegenInst.get_table(info, reg, prefix_reg, key_reg)
        
        info.free_reg()
        info.free_reg()
    
    def codegen_set(self, info: FuncInfo, val_reg: int):
        """Generate code for table assignment: table[key] = value"""
        prefix_reg = info.alloc_reg()
        self.prefix_exp.codegen(info, prefix_reg)
        
        key_reg = info.alloc_reg()
        self.key_exp.codegen(info, key_reg)
        
        CodegenInst.set_table(info, prefix_reg, key_reg, val_reg)
        
        info.free_reg()
        info.free_reg()


class FuncCallExp(Expr):
    """Function call expression."""
    prefix_exp: Expr
    name_exp: NameExp | None
    args: list[Expr]

    def __init__(self, prefix_exp: Expr, name_exp: NameExp | None, args: list[Expr]):
        self.prefix_exp = prefix_exp
        self.name_exp = name_exp
        self.args = args

    @classmethod
    def parse(cls, lexer: Lexer, prefix_exp: Expr) -> FuncCallExp:
        """Parse function call: func(args) or obj:method(args)."""
        name_exp = None
        if lexer.current().type == "COLON":
            lexer.consume("COLON")
            name_exp = NameExp.parse(lexer)
        
        args = cls._parse_args(lexer)
        return cls(prefix_exp, name_exp, args)
    
    @staticmethod
    def _parse_args(lexer: Lexer) -> list[Expr]:
        """Parse function arguments."""
        token = lexer.current()
        
        if token.type == "LPAREN":
            lexer.consume("LPAREN")
            args = Expr.parse_list(lexer) if lexer.current().type != "RPAREN" else []
            lexer.consume("RPAREN")
            return args
        elif token.type == "LBRACE":
            return [TableConstructorExp.parse(lexer)]
        elif token.type == "STRING":
            return [StringExp.parse(lexer)]
        else:
            return []
        
    def codegen(self, info: FuncInfo, reg: int = None, cnt: int = 1):
        # If reg is None, we're being called as a statement
        if reg is None:
            reg = info.alloc_reg()
            should_free = True
        else:
            should_free = False
            
        func_reg = info.alloc_reg()
        
        # Handle method calls (obj:method(args))
        if self.name_exp:
            # Use SELF instruction for method calls
            obj_reg = info.alloc_reg()
            self.prefix_exp.codegen(info, obj_reg)
            
            key_reg = info.alloc_reg()
            self.name_exp.codegen(info, key_reg)
            
            CodegenInst.self_(info, func_reg, obj_reg, key_reg)
            info.free_reg()
            info.free_reg()
        else:
            self.prefix_exp.codegen(info, func_reg)
        
        # Generate code for arguments
        arg_start = info.alloc_regs(len(self.args))
        for i, arg in enumerate(self.args):
            arg.codegen(info, arg_start + i)
        
        # Call instruction: CALL func_reg, nargs+1, nresults+1
        nargs = len(self.args) + (1 if self.name_exp else 0)  # +1 for self
        CodegenInst.call(info, func_reg, nargs + 1, cnt + 1)
        
        # Move result to target register
        if func_reg != reg:
            CodegenInst.move(info, reg, func_reg)
        
        # Free registers
        if len(self.args) > 0:
            info.free_regs(len(self.args))
        info.free_reg()
        
        if should_free:
            info.free_reg()


class FuncDefExp(Expr):
    """Function definition expression."""
    param_names: list[NameExp]
    is_vararg: bool
    body: Block
    ret_exps: list[Expr]

    def __init__(self, param_names: list[NameExp], ret_exps: list[Expr], is_vararg: bool, body: Block):
        self.param_names = param_names
        self.ret_exps = ret_exps
        self.is_vararg = is_vararg
        self.body = body
    
    @classmethod
    def parse(cls, lexer: Lexer, colon: bool = False) -> FuncDefExp:
        from .lua_block import Block
        from .lua_stat import ReturnStat

        lexer.consume("LPAREN")
        
        param_names = [NameExp("self")] if colon else []
        
        # Parse parameters
        while lexer.current().type == "IDENTIFIER":
            param_names.append(NameExp.parse(lexer))
            if lexer.current().type == "COMMA":
                lexer.consume("COMMA")

        is_vararg = False
        if lexer.current().type == "VARARG":
            VarargExp.parse(lexer)
            is_vararg = True

        lexer.consume("RPAREN")

        body = Block.parse(lexer)
        if lexer.current().is_return():
            ret_exps = ReturnStat.parse_list(lexer)
        else:
            ret_exps = []
        lexer.consume("END")
        
        return cls(param_names, ret_exps, is_vararg, body)
    
    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        func_info = FuncInfo(parent=info)
        func_info.nparams = len(self.param_names)
        func_info.is_vararg = self.is_vararg

        func_info.enter_scope()
        for param in self.param_names:
            func_info.add_local_var(param.name)

        self.body.codegen(func_info)
        func_info.exit_scope()
        
        idx = len(info.sub_funcs)
        info.sub_funcs.append(func_info)

        CodegenInst.closure(info, reg, idx)
