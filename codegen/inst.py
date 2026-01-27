from __future__ import annotations

from .func import Const, FuncInfo


# Instruction argument modes
OpArgN = 0  # argument is not used
OpArgU = 1  # argument is used
OpArgR = 2  # argument is a register or a jump offset
OpArgK = 3  # argument is a constant or register/constant

# Instruction formats: iABC, iABx, iAsBx
iABC, iABx, iAsBx = 0, 1, 2


class OpCode:
    """Lua 5.1 opcode definition with mode information."""
    def __init__(self, name: str, test_flag: int, seta_reg: int, argb: int, argc: int, mode: int):
        self.name = name
        self.test_flag = test_flag  # operator is a test (next instruction must be a jump)
        self.seta_reg = seta_reg    # instruction set register A
        self.argb = argb          # B arg mode
        self.argc = argc          # C arg mode
        self.mode = mode          # op mode (iABC=0, iABx=1, iAsBx=2)

    def __repr__(self):
        return self.name


# Lua 5.1 opcodes with their properties
# OpCode(name, testflag, setareg, argb, argc, mode)
OPCODES = [
    OpCode("MOVE",      0, 1, OpArgR, OpArgN, iABC),
    OpCode("LOADK",     0, 1, OpArgK, OpArgN, iABx),
    OpCode("LOADBOOL",  0, 1, OpArgU, OpArgU, iABC),
    OpCode("LOADNIL",   0, 1, OpArgU, OpArgN, iABC),
    OpCode("GETUPVAL",  0, 1, OpArgU, OpArgN, iABC),
    OpCode("GETGLOBAL", 0, 1, OpArgK, OpArgN, iABx),
    OpCode("GETTABLE",  0, 1, OpArgR, OpArgK, iABC),
    OpCode("SETGLOBAL", 0, 0, OpArgK, OpArgN, iABx),
    OpCode("SETUPVAL",  0, 0, OpArgU, OpArgN, iABC),
    OpCode("SETTABLE",  0, 0, OpArgK, OpArgK, iABC),
    OpCode("NEWTABLE",  0, 1, OpArgU, OpArgU, iABC),
    OpCode("SELF",      0, 1, OpArgR, OpArgK, iABC),
    OpCode("ADD",       0, 1, OpArgK, OpArgK, iABC),
    OpCode("SUB",       0, 1, OpArgK, OpArgK, iABC),
    OpCode("MUL",       0, 1, OpArgK, OpArgK, iABC),
    OpCode("DIV",       0, 1, OpArgK, OpArgK, iABC),
    OpCode("MOD",       0, 1, OpArgK, OpArgK, iABC),
    OpCode("POW",       0, 1, OpArgK, OpArgK, iABC),
    OpCode("UNM",       0, 1, OpArgR, OpArgN, iABC),
    OpCode("NOT",       0, 1, OpArgR, OpArgN, iABC),
    OpCode("LEN",       0, 1, OpArgR, OpArgN, iABC),
    OpCode("CONCAT",    0, 1, OpArgR, OpArgR, iABC),
    OpCode("JMP",       0, 0, OpArgR, OpArgN, iAsBx),
    OpCode("EQ",        1, 0, OpArgK, OpArgK, iABC),
    OpCode("LT",        1, 0, OpArgK, OpArgK, iABC),
    OpCode("LE",        1, 0, OpArgK, OpArgK, iABC),
    OpCode("TEST",      1, 0, OpArgN, OpArgU, iABC),
    OpCode("TESTSET",   1, 1, OpArgR, OpArgU, iABC),
    OpCode("CALL",      0, 1, OpArgU, OpArgU, iABC),
    OpCode("TAILCALL",  0, 1, OpArgU, OpArgU, iABC),
    OpCode("RETURN",    0, 0, OpArgU, OpArgN, iABC),
    OpCode("FORLOOP",   0, 1, OpArgR, OpArgN, iAsBx),
    OpCode("FORPREP",   0, 1, OpArgR, OpArgN, iAsBx),
    OpCode("TFORLOOP",  0, 0, OpArgN, OpArgU, iABC),
    OpCode("SETLIST",   0, 0, OpArgU, OpArgU, iABC),
    OpCode("CLOSE",     0, 0, OpArgN, OpArgN, iABC),
    OpCode("CLOSURE",   0, 1, OpArgU, OpArgN, iABx),
    OpCode("VARARG",    0, 1, OpArgU, OpArgN, iABC),
]


OP = {opcode.name: idx for idx, opcode in enumerate(OPCODES)}


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
