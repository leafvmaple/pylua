"""Lua expression AST nodes and parser.

This module defines all expression types in Lua and their parsing logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .lexer import Lexer
    from .stat import Block

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

    @classmethod
    def parse(cls, lexer: Lexer) -> Expr:
        return Expr.parse_sub_expr(lexer, 0)

    @staticmethod
    def parse_list(lexer: Lexer) -> list[Expr]:
        exps = [Expr.parse(lexer)]
        while lexer.current().type == "COMMA":
            lexer.consume()
            exps.append(Expr.parse(lexer))

        return exps

    @staticmethod
    def parse_prefix(lexer: Lexer) -> Expr:
        """Parse a prefix expression (identifier or parenthesized)."""
        token = lexer.current()
        if token.type == "IDENTIFIER":
            exp = NameExpr.parse(lexer)
        elif token.type == "LPAREN":
            lexer.consume("LPAREN")
            exp = Expr.parse(lexer)
            lexer.consume("RPAREN")
        else:
            raise SyntaxError(f"Unexpected token in prefix expression: {token.type}")

        return Expr.parse_postfix(lexer, exp)

    @staticmethod
    def parse_postfix(lexer: Lexer, expr: Expr) -> Expr:
        """Parse postfix operators (field access, indexing, function calls)."""
        while token := lexer.current():
            if token.type == "LBRACKET":
                expr = TableAccessExpr.parse_bracket(lexer, expr)
            elif token.type == "DOT":
                expr = TableAccessExpr.parse_dot(lexer, expr)
            elif token.type in ("COLON", "LPAREN", "LBRACE", "STRING"):
                expr = FuncCallExpr.parse_func(lexer, expr)
            else:
                return expr

        assert False, "Unreachable code in parse_postfix"

    @staticmethod
    def parse_sub_expr(lexer: Lexer, limit: int) -> Expr:
        """Parse sub-expression with operator precedence climbing algorithm."""
        # Parse unary operators or simple expression
        if lexer.current().type in ("NOT", "MINUS", "LEN", "BXOR"):
            exp = UnaryOpExpr.parse(lexer)
        else:
            exp = Expr._parse_simple_exp(lexer)

        # Parse binary operators with precedence
        while (op := lexer.current().type) and (lbp := BINARY_PRECEDENCE.get(op, -1)) > limit:
            lexer.consume()  # consume operator
            # Right associative operators (POW, CONCAT) use lbp-1
            rbp = lbp - 1 if op in ("POW", "CONCAT") else lbp
            right = Expr.parse_sub_expr(lexer, rbp)
            exp = BinaryOpExpr(op, exp, right)
        return exp

    @staticmethod
    def _parse_simple_exp(lexer: Lexer) -> Expr:
        token = lexer.current()

        # Literal tokens
        if token.type == "NIL":
            return NilExpr.parse(lexer)
        elif token.type == "TRUE":
            return TrueExpr.parse(lexer)
        elif token.type == "FALSE":
            return FalseExpr.parse(lexer)
        elif token.type == "VARARG":
            return VarargExpr.parse(lexer)

        # Numbers
        elif token.type == "NUMBER":
            # TODO: Distinguish integer vs float
            return Expr.parse_number(lexer)

        # Strings
        elif token.type == "STRING":
            return StringExpr.parse(lexer)

        # Table constructor
        elif token.type == "LBRACE":
            return TableConstructorExpr.parse(lexer)

        # Anonymous Function
        elif token.type == "FUNCTION":
            lexer.consume("FUNCTION")
            return FuncDefExpr.parse(lexer)

        # Parenthesized expression
        elif token.type == "LPAREN":
            return ParenExpr.parse(lexer)

        # Identifier (with potential postfix)
        elif token.type == "IDENTIFIER":
            return Expr.parse_postfix(lexer, NameExpr.parse(lexer))
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
                return FloatExpr.parse_hex(lexer)
            else:
                return IntegerExpr.parse_hex(lexer)
        # Decimal number
        else:
            if '.' in value_str or 'e' in value_str or 'E' in value_str:
                return FloatExpr.parse(lexer)
            else:
                return IntegerExpr.parse(lexer)

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        """Generate code for this expression."""
        pass


# ============================================================================
# Literal Expressions
# ============================================================================

class NilExpr(Expr):
    @classmethod
    def parse(cls, lexer: Lexer) -> NilExpr:
        lexer.consume("NIL")
        return cls()

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_nil(info, reg, cnt if cnt else 1)


class TrueExpr(Expr):
    @classmethod
    def parse(cls, lexer: Lexer):
        lexer.consume("TRUE")
        return cls()

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_bool(info, reg, 1, 0)


class FalseExpr(Expr):
    @classmethod
    def parse(cls, lexer: Lexer):
        lexer.consume("FALSE")
        return cls()

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_bool(info, reg, 0, 0)


class VarargExpr(Expr):
    @classmethod
    def parse(cls, lexer: Lexer):
        lexer.consume("VARARG")
        return cls()

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.vararg(info, reg, cnt)


class IntegerExpr(Expr):
    value: int

    def __init__(self, value: int):
        self.value = value

    @classmethod
    def parse(cls, lexer: Lexer) -> IntegerExpr:
        token = lexer.consume("NUMBER")
        return cls(int(token.value))

    @classmethod
    def parse_hex(cls, lexer: Lexer) -> IntegerExpr:
        token = lexer.consume("NUMBER")
        return cls(int(token.value, 16))

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_k(info, reg, self.value)


class FloatExpr(Expr):
    value: float

    def __init__(self, value: float):
        self.value = value

    @classmethod
    def parse(cls, lexer: Lexer) -> FloatExpr:
        token = lexer.consume("NUMBER")
        return cls(float(token.value))

    @classmethod
    def parse_hex(cls, lexer: Lexer) -> FloatExpr:
        token = lexer.consume("NUMBER")
        return cls(float.fromhex(token.value))

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_k(info, reg, self.value)


class StringExpr(Expr):
    value: str

    def __init__(self, value: str):
        self.value = value

    @classmethod
    def parse(cls, lexer: Lexer) -> StringExpr:
        token = lexer.consume("STRING")
        return cls(token.value)

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        CodegenInst.load_k(info, reg, self.value)


class NameExpr(Expr):
    name: str

    def __init__(self, name: str):
        self.name = name

    @classmethod
    def parse(cls, lexer: Lexer) -> NameExpr:
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


class UnaryOpExpr(Expr):
    """Unary operator expression (not, -, #, ~)."""
    op: str
    expr: Expr

    def __init__(self, op: str, expr: Expr):
        self.op = op
        if self.op == "MINUS":
            self.op = "UNM"
        self.expr = expr

    @classmethod
    def parse(cls, lexer: Lexer) -> UnaryOpExpr:
        token = lexer.consume()
        exp = Expr.parse_sub_expr(lexer, UNARY_PRECEDENCE)
        return cls(token.type, exp)

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        operand_reg = info.alloc_reg()
        self.expr.codegen(info, operand_reg)

        op_func = getattr(CodegenInst, self.op)
        if op_func:
            op_func(info, reg, operand_reg)
        else:
            raise NotImplementedError(f"Unary operator {self.op} not implemented.")

        info.free_reg()


class BinaryOpExpr(Expr):
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
                if type(e) is BinaryOpExpr and e.op == 'CONCAT':
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
                CodegenInst.testset(info, reg, reg, 0)  # Jump if false
            else:  # OR
                CodegenInst.testset(info, reg, reg, 1)  # Jump if true

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


# ============================================================================
# Complex Expressions
# ============================================================================


class ParenExpr(Expr):
    exp: Expr

    def __init__(self, exp: Expr):
        self.exp = exp

    @classmethod
    def parse(cls, lexer: Lexer) -> ParenExpr:
        lexer.consume("LPAREN")
        exp = Expr.parse(lexer)
        lexer.consume("RPAREN")
        return cls(exp)

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        self.exp.codegen(info, reg, cnt)


class TableConstructorExpr(Expr):
    """Table constructor expression {...}."""
    key_exps: list[Expr | None]
    val_exps: list[Expr]

    def __init__(self, key_exps: list[Expr | None], val_exps: list[Expr]):
        self.key_exps = key_exps
        self.val_exps = val_exps

    @classmethod
    def parse(cls, lexer: Lexer) -> TableConstructorExpr:
        key_exps: list[Expr | None] = []
        val_exps: list[Expr] = []
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
                if type(exp) is NameExpr:
                    exp = StringExpr(exp.name)
                lexer.consume("ASSIGN")
                key_exps.append(exp)
                val_exps.append(Expr.parse(lexer))
            else:
                # exp (array-style)
                key_exps.append(None)
                val_exps.append(exp)

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        # Separate array-style (key is None) and hash-style entries
        array_vals: list[Expr] = []
        hash_keys: list[Expr] = []
        hash_vals: list[Expr] = []
        for key, val in zip(self.key_exps, self.val_exps):
            if key is None:
                array_vals.append(val)
            else:
                hash_keys.append(key)
                hash_vals.append(val)

        CodegenInst.new_table(info, reg, len(array_vals), len(hash_keys))

        # Emit hash-style entries with SETTABLE
        for key, val in zip(hash_keys, hash_vals):
            key_reg = info.alloc_reg()
            key.codegen(info, key_reg)
            val_reg = info.alloc_reg()
            val.codegen(info, val_reg)
            CodegenInst.set_table(info, reg, key_reg, val_reg)
            info.free_regs(2)

        # Emit array-style entries with SETLIST (batches of 50)
        LFIELDS_PER_FLUSH = 50
        for batch_start in range(0, len(array_vals), LFIELDS_PER_FLUSH):
            batch = array_vals[batch_start:batch_start + LFIELDS_PER_FLUSH]
            # SETLIST expects values in reg+1..reg+n, so force allocation there
            saved_used = info.used_regs
            info.used_regs = reg + 1
            batch_regs = info.alloc_regs(len(batch))
            for i, val in enumerate(batch):
                val.codegen(info, batch_regs + i)
            block = batch_start // LFIELDS_PER_FLUSH + 1  # 1-based block number
            CodegenInst.set_list(info, reg, len(batch), block)
            info.used_regs = saved_used


class TableAccessExpr(Expr):
    prefix_expr: Expr
    key_expr: Expr

    def __init__(self, prefix_expr: Expr, key_expr: Expr):
        self.prefix_expr = prefix_expr
        self.key_expr = key_expr

    @classmethod
    def parse_bracket(cls, lexer: Lexer, prefix_expr: Expr) -> TableAccessExpr:
        lexer.consume("LBRACKET")
        key_exp = Expr.parse(lexer)
        lexer.consume("RBRACKET")
        return cls(prefix_expr, key_exp)

    @classmethod
    def parse_dot(cls, lexer: Lexer, prefix_expr: Expr) -> TableAccessExpr:
        lexer.consume("DOT")
        name = NameExpr.parse(lexer)
        return cls(prefix_expr, StringExpr(name.name))

    @classmethod
    def parse_colon(cls, lexer: Lexer, prefix_expr: Expr) -> TableAccessExpr:
        lexer.consume("COLON")
        name = NameExpr.parse(lexer)
        return cls(prefix_expr, StringExpr(name.name))

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        prefix_reg = info.alloc_reg()
        self.prefix_expr.codegen(info, prefix_reg)

        key_reg = info.alloc_reg()
        self.key_expr.codegen(info, key_reg)

        CodegenInst.get_table(info, reg, prefix_reg, key_reg)

        info.free_reg()
        info.free_reg()

    def codegen_set(self, info: FuncInfo, val_reg: int):
        """Generate code for table assignment: table[key] = value"""
        prefix_reg = info.alloc_reg()
        self.prefix_expr.codegen(info, prefix_reg)

        key_reg = info.alloc_reg()
        self.key_expr.codegen(info, key_reg)

        CodegenInst.set_table(info, prefix_reg, key_reg, val_reg)

        info.free_reg()
        info.free_reg()


class FuncCallExpr(Expr):
    """Function call expression."""
    prefix_expr: Expr
    name_expr: NameExpr | None
    args: list[Expr]

    def __init__(self, prefix_exp: Expr, name_exp: NameExpr | None, args: list[Expr]):
        self.prefix_expr = prefix_exp
        self.name_expr = name_exp
        self.args = args

    @classmethod
    def parse_func(cls, lexer: Lexer, prefix_expr: Expr) -> FuncCallExpr:
        """Parse function call: func(args) or obj:method(args)."""
        name_expr = None
        if lexer.current().type == "COLON":
            lexer.consume("COLON")
            name_expr = NameExpr.parse(lexer)

        args = cls._parse_args(lexer)
        return cls(prefix_expr, name_expr, args)

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
            return [TableConstructorExpr.parse(lexer)]
        elif token.type == "STRING":
            return [StringExpr.parse(lexer)]
        else:
            return []
   
    # cnt: return count
    def codegen(self, info: FuncInfo, reg: int = -1, cnt: int = 0):
        regs_cnt = max(len(self.args) + 1, cnt)
        func_reg = info.alloc_reg() if reg == -1 else reg
        needed_regs = func_reg + regs_cnt
        alloc_regs = needed_regs - info.used_regs
        if alloc_regs > 0:
            info.alloc_regs(alloc_regs)

        # Handle method calls (obj:method(args))
        if self.name_expr:
            # Use SELF instruction for method calls
            obj_reg = info.alloc_reg()
            self.prefix_expr.codegen(info, obj_reg)

            key_reg = info.alloc_reg()
            self.name_expr.codegen(info, key_reg)

            CodegenInst.self_(info, func_reg, obj_reg, key_reg)
            info.free_reg()
            info.free_reg()
        else:
            self.prefix_expr.codegen(info, func_reg)

        # Generate code for arguments
        # When an argument is a function call, it should expect 1 return value
        for i, arg in enumerate(self.args):
            if isinstance(arg, FuncCallExpr):
                arg.codegen(info, func_reg + 1 + i, cnt=1)
            else:
                arg.codegen(info, func_reg + 1 + i)

        nargs = len(self.args) + (1 if self.name_expr else 0)  # +1 for self
        CodegenInst.call(info, func_reg, nargs, cnt)

        if alloc_regs > 0:
            info.free_regs(alloc_regs)

        # Free registers
        if func_reg != reg:
            info.free_reg()


class FuncDefExpr(Expr):
    """Function definition expression."""
    param_names: list[NameExpr]
    is_vararg: bool
    body: Block

    def __init__(self, param_names: list[NameExpr], is_vararg: bool, body: Block):
        self.param_names = param_names
        self.is_vararg = is_vararg
        self.body = body

    @classmethod
    def parse(cls, lexer: Lexer, colon: bool = False) -> FuncDefExpr:
        from .block import Block

        lexer.consume("LPAREN")

        param_names = [NameExpr("self")] if colon else []

        # Parse parameters
        while lexer.current().type == "IDENTIFIER":
            param_names.append(NameExpr.parse(lexer))
            if lexer.current().type == "COMMA":
                lexer.consume("COMMA")

        is_vararg = False
        if lexer.current().type == "VARARG":
            VarargExpr.parse(lexer)
            is_vararg = True

        lexer.consume("RPAREN")

        body = Block.parse(lexer)
        lexer.consume("END")

        return cls(param_names, is_vararg, body)

    def codegen(self, info: FuncInfo, reg: int, cnt: int = 1):
        func_info = FuncInfo(parent=info)
        func_info.num_params = len(self.param_names)
        func_info.is_vararg = self.is_vararg

        func_info.enter_scope()
        for param in self.param_names:
            func_info.add_local_var(param.name)

        self.body.codegen(func_info)
        
        # Generate return instruction
        if self.body.ret_exprs:
            num_rets = len(self.body.ret_exprs)
            ret_reg = func_info.alloc_regs(num_rets)
            for i in range(num_rets):
                self.body.ret_exprs[i].codegen(func_info, ret_reg + i)
            CodegenInst.ret(func_info, ret_reg, num_rets + 1)
            func_info.free_regs(num_rets)
        else:
            CodegenInst.ret(func_info, 0, 1)
        
        func_info.exit_scope()

        idx = len(info.sub_funcs)
        info.sub_funcs.append(func_info)

        CodegenInst.closure(info, reg, idx)
