ARITHS = {
    'ADD': lambda a, b: a + b,
    'SUB': lambda a, b: a - b,
    'MUL': lambda a, b: a * b,
    'DIV': lambda a, b: a / b,
    'MOD': lambda a, b: a % b,
    'POW': lambda a, b: a ** b,

    'UNM': lambda a: -a,
    'BNOT': lambda a: ~a,
}

COMPARE = {
    'EQ': lambda a, b: a == b,
    'LT': lambda a, b: a < b,
    'LE': lambda a, b: a <= b,
}