from __future__ import annotations

from .func import Const, FuncInfo

OP= {
    'MOVE': 0,
    'LOADK': 1,
    'LOADBOOL': 2,
    'LOADNIL': 3,
    'GETUPVAL': 4,
    'GETGLOBAL': 5,
    'GETTABLE': 6,
    'SETGLOBAL': 7,
    'SETUPVAL': 8,
    'SETTABLE': 9,
    'NEWTABLE': 10,
    'SELF': 11,
    'ADD': 12,
    'SUB': 13,
    'MUL': 14,
    'DIV': 15,
    'MOD': 16,
    'POW': 17,
    'UNM': 18,
    'NOT': 19,
    'LEN': 20,
    'CONCAT': 21,
    'JMP': 22,
    'EQ': 23,
    'LT': 24,
    'LE': 25,
    'TEST': 26,
    'TESTSET': 27,
    'CALL': 28,
    'TAILCALL': 29,
    'RETURN': 30,
    'FORLOOP': 31,
    'FORPREP': 32,
    'TFORLOOP': 34,
    'SETLIST': 35,
    'CLOSE': 36,
    'CLOSURE': 37,
    'VARARG': 38,
}

class CodegenInst:
    @staticmethod
    def move(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['MOVE'], a, b, 0)

    @staticmethod
    def load_k(info: FuncInfo, reg: int, const: Const):
        idx = info.idx_of_const(const)
        if idx < (1 << 18):
            info.emit_abx(OP['LOADK'], reg, idx)
        else:
            raise ValueError("Constant index out of range for LOADK instruction")

    @staticmethod
    def load_bool(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['LOADBOOL'], a, b, c)

    @staticmethod
    def load_nil(info: FuncInfo, a: int, n: int):
        info.emit_abc(OP['LOADNIL'], a, n - 1, 0)

    @staticmethod
    def get_global(info: FuncInfo, a: int, bx: int):
        info.emit_abx(OP['GETGLOBAL'], a, bx)
    
    @staticmethod
    def set_global(info: FuncInfo, a: int, bx: int):
        info.emit_abx(OP['SETGLOBAL'], a, bx)

    @staticmethod
    def get_table(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['GETTABLE'], a, b, c)

    @staticmethod
    def set_table(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['SETTABLE'], a, b, c)

    @staticmethod
    def new_table(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['NEWTABLE'], a, b, c)

    @staticmethod
    def set_list(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['SETLIST'], a, b, c)

    @staticmethod
    def jmp(info: FuncInfo, sbx: int):
        info.emit_asbx(OP['JMP'], 0, sbx)

    @staticmethod
    def ret(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['RETURN'], a, b, 0)

    @staticmethod
    def closure(info: FuncInfo, a: int, bx: int):
        info.emit_abx(OP['CLOSURE'], a, bx)

    @staticmethod
    # num_args: number of arguments
    # num_rets: number of expected return values, -1 for variable
    def call(info: FuncInfo, a: int, num_args: int, num_rets: int):
        info.emit_abc(OP['CALL'], a, num_args + 1, num_rets + 1)

    @staticmethod
    def get_upval(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['GETUPVAL'], a, b, 0)

    @staticmethod
    def set_upval(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['SETUPVAL'], a, b, 0)

    @staticmethod
    def vararg(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['VARARG'], a, b, 0)

    @staticmethod
    def self_(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['SELF'], a, b, c)

    @staticmethod
    def concat(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['CONCAT'], a, b, c)

    @staticmethod
    def test(info: FuncInfo, a: int, c: int):
        info.emit_abc(OP['TEST'], a, 0, c)

    @staticmethod
    def testset(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['TESTSET'], a, b, c)
    
    @staticmethod
    def test_set(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['TESTSET'], a, b, c)

    @staticmethod
    def forprep(info: FuncInfo, a: int, sbx: int):
        info.emit_asbx(OP['FORPREP'], a, sbx)

    @staticmethod
    def forloop(info: FuncInfo, a: int, sbx: int):
        info.emit_asbx(OP['FORLOOP'], a, sbx)

    @staticmethod
    def tforloop(info: FuncInfo, a: int, c: int):
        info.emit_abc(OP['TFORLOOP'], a, 0, c)

    @staticmethod
    def PLUS(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['ADD'], a, b, c)

    @staticmethod
    def MINUS(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['SUB'], a, b, c)

    @staticmethod
    def MULTIPLY(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['MUL'], a, b, c)

    @staticmethod
    def DIVIDE(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['DIV'], a, b, c)

    @staticmethod
    def MOD(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['MOD'], a, b, c)

    @staticmethod
    def POW(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['POW'], a, b, c)

    @staticmethod
    def UNM(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['UNM'], a, b, 0)

    @staticmethod
    def NOT(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['NOT'], a, b, 0)

    @staticmethod
    def LEN(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['LEN'], a, b, 0)

    # Comparison operators
    @staticmethod
    def EQ(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['EQ'], a, b, c)

    @staticmethod
    def LT(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['LT'], a, b, c)

    @staticmethod
    def LE(info: FuncInfo, a: int, b: int, c: int):
        info.emit_abc(OP['LE'], a, b, c)
    
    @staticmethod
    def GT(info: FuncInfo, a: int, b: int, c: int):
        # GT is implemented as NOT (LE)
        info.emit_abc(OP['LE'], 0, c, b)
    
    @staticmethod
    def GE(info: FuncInfo, a: int, b: int, c: int):
        # GE is implemented as NOT (LT)
        info.emit_abc(OP['LT'], 0, c, b)
    
    @staticmethod
    def NE(info: FuncInfo, a: int, b: int, c: int):
        # NE is implemented as NOT (EQ)
        info.emit_abc(OP['EQ'], 0, b, c)

    @staticmethod
    def close(info: FuncInfo, a: int):
        info.emit_abc(OP['CLOSE'], a, 0, 0)

    @staticmethod
    def tailcall(info: FuncInfo, a: int, b: int):
        info.emit_abc(OP['TAILCALL'], a, b, 0)