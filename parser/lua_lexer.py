from __future__ import annotations

TOKEN_TYPE = {
    '+': "PLUS",
    '-': "MINUS",
    '*': "MULTIPLY",
    '/': "DIVIDE",
    '%': "MOD",
    '^': "POW",
    '#': "LEN",
    '&': "BAND",
    '~': "BXOR",
    '|': "BOR",
    '=': "ASSIGN",
    ';': "SEMICOLON",
    '(': "LPAREN",
    ')': "RPAREN",
    ',': "COMMA",
    '{': "LBRACE",
    '}': "RBRACE",
    '[': "LBRACKET",
    ']': "RBRACKET",
    ':': "COLON",
}

KEYWORDS = {
    'and', 'break', 'do', 'else', 'elseif', 'end',
    'false', 'for', 'function', 'goto', 'if', 'in',
    'local', 'nil', 'not', 'or', 'repeat', 'return',
    'then', 'true', 'until', 'while'
}


class Token:
    type: str
    value: str
    line: int

    def __init__(self, type: str, value: str, line: int):
        self.type = type
        self.value = value
        self.line = line

    def is_end(self) -> bool:
        return self.type in ("EOF", "END", "ELSE", "ELSEIF", "UNTIL")

    def is_return(self) -> bool:
        return self.type == "RETURN"

    def is_eof(self) -> bool:
        return self.type == "EOF"


class Lexer:
    chunk: str
    chunk_name: str
    pos: int
    tokens: list[Token]

    def __init__(self, chunk: str, chunk_name: str = ""):
        self.chunk = chunk
        self.chunk_name = chunk_name
        self.pos = 0
        self.tokenize()

    @classmethod
    def from_file(cls, filepath: str):
        with open(filepath, 'r') as f:
            chunk = f.read()
        return cls(chunk, filepath)

    def tokenize(self) -> None:
        self.tokens = []
        self._line = 1
        self._chunk_pos = 0
        while not self.is_eof():
            token = self._next_token()
            self.tokens.append(token)

    def _scan_token(self) -> Token:
        """Scan and return the next token from the input stream.

        This is the main lexical analysis function that implements a finite automaton
        to recognize Lua tokens. It uses a dispatch pattern for efficiency.
        """
        self.skip_whitespace()
        if self.is_eof():
            return Token("EOF", '', self._line)

        char = self.peek_char()

        # Dispatch based on first character
        if char.isalpha() or char == '_':
            return self.read_identifier()

        if char.isdigit():
            return self.read_number()

        if char in ('"', "'"):
            return self.read_string()

        # Operators that may form multi-character tokens
        if char == '-':
            return self._scan_minus()

        if char == '=':
            return self._scan_equal()

        if char == '~':
            return self._scan_tilde()

        if char == '<':
            return self._scan_less()

        if char == '>':
            return self._scan_greater()

        if char == '.':
            return self._scan_dot()

        if char == '/':
            return self._scan_slash()

        if char == ':':
            return self._scan_colon()

        # Single-character operators
        if char in TOKEN_TYPE:
            token_type = TOKEN_TYPE[char]
            self.advance_char()
            return Token(token_type, char, self._line)

        # Unrecognized character
        self.advance_char()
        return Token("UNKNOWN", char, self._line)

    def _scan_minus(self) -> Token:
        """Scan '-' or '--' (comment)."""
        self.advance_char()
        if self._match('-'):
            return self.read_comment()
        return Token("MINUS", '-', self._line)

    def _scan_equal(self) -> Token:
        """Scan '=' or '=='."""
        self.advance_char()
        if self._match('='):
            return Token("EQ", '==', self._line)
        return Token("ASSIGN", '=', self._line)

    def _scan_tilde(self) -> Token:
        """Scan '~' or '~='."""
        self.advance_char()
        if self._match('='):
            return Token("NE", '~=', self._line)
        return Token("BXOR", '~', self._line)

    def _scan_less(self) -> Token:
        """Scan '<', '<=', or '<<'."""
        self.advance_char()
        if self._match('='):
            return Token("LE", '<=', self._line)
        if self._match('<'):
            return Token("SHL", '<<', self._line)
        return Token("LT", '<', self._line)

    def _scan_greater(self) -> Token:
        """Scan '>', '>=', or '>>'."""
        self.advance_char()
        if self._match('='):
            return Token("GE", '>=', self._line)
        if self._match('>'):
            return Token("SHR", '>>', self._line)
        return Token("GT", '>', self._line)

    def _scan_dot(self) -> Token:
        """Scan '.', '..', '...', or numbers starting with '.'."""
        self.advance_char()

        if self._match('.'):
            if self._match('.'):
                return Token("VARARG", '...', self._line)
            return Token("CONCAT", '..', self._line)

        # Check for number starting with decimal point (e.g., .5)
        if not self.is_eof() and self.peek_char().isdigit():
            start_pos = self._chunk_pos - 1
            while not self.is_eof() and self.peek_char().isdigit():
                self.advance_char()
            value = self.chunk[start_pos:self._chunk_pos]
            return Token("NUMBER", value, self._line)

        return Token("DOT", '.', self._line)

    def _scan_slash(self) -> Token:
        """Scan '/' or '//'."""
        self.advance_char()
        if self._match('/'):
            return Token("IDIV", '//', self._line)
        return Token("DIVIDE", '/', self._line)

    def _scan_colon(self) -> Token:
        """Scan ':' or '::'."""
        self.advance_char()
        if self._match(':'):
            return Token("LABEL", '::', self._line)
        return Token("COLON", ':', self._line)

    def _match(self, expected: str) -> bool:
        if self.is_eof() or self.peek_char() != expected:
            return False
        self.advance_char()
        return True

    def _next_token(self) -> Token:
        """Get the next non-comment token.

        Wraps _scan_token() to filter out comment tokens during tokenization.
        This is the interface used by the tokenize() method.
        """
        while (token := self._scan_token()).type == "COMMENT":
            pass
        return token

    def current(self) -> Token:
        if self.pos >= len(self.tokens):
            return Token("EOF", '', self._line)
        return self.tokens[self.pos]

    def lookahead(self) -> Token:
        assert self.pos + 1 < len(self.tokens), "No more tokens to lookahead"
        return self.tokens[self.pos + 1]

    def consume(self, expect: str | None = None) -> Token:
        token = self.current()
        if expect and token.type != expect:
            raise SyntaxError(f"Expected {expect} but got {token.type} at line {self._line}")
        self.pos += 1
        return token

    def read_identifier(self) -> Token:
        start_pos = self._chunk_pos
        while not self.is_eof() and ((char := self.peek_char()) and (char.isalnum() or char == '_')):
            self.advance_char()
        value = self.chunk[start_pos: self._chunk_pos]
        # Check if it's a keyword
        if value in KEYWORDS:
            return Token(value.upper(), value, self._line)
        return Token("IDENTIFIER", value, self._line)

    def read_number(self) -> Token:
        start_pos = self._chunk_pos

        # Check for hexadecimal prefix
        if self._peek_ahead('0', ('x', 'X')):
            self._scan_hex_number()
        else:
            self._scan_decimal_number()

        value = self.chunk[start_pos:self._chunk_pos]
        return Token("NUMBER", value, self._line)

    def _peek_ahead(self, first: str, second: tuple[str, ...]) -> bool:
        """Check if next two characters match the pattern."""
        return (
            self.peek_char() == first
            and self._chunk_pos + 1 < len(self.chunk)
            and self.chunk[self._chunk_pos + 1] in second
        )

    def _scan_hex_number(self) -> None:
        self.advance_char()  # skip '0'
        self.advance_char()  # skip 'x' or 'X'

        # Integer part
        self._scan_hex_digits()

        # Fractional part
        if not self.is_eof() and self.peek_char() == '.':
            self.advance_char()
            self._scan_hex_digits()

        # Exponent part (binary exponent with base 2)
        if not self.is_eof() and self.peek_char() in ('p', 'P'):
            self.advance_char()
            if not self.is_eof() and self.peek_char() in ('+', '-'):
                self.advance_char()
            self._scan_decimal_digits()

    def _scan_decimal_number(self) -> None:
        # Integer part
        self._scan_decimal_digits()

        # Fractional part
        if (
            not self.is_eof()
            and self.peek_char() == '.'
            and self._chunk_pos + 1 < len(self.chunk)
            and self.chunk[self._chunk_pos + 1].isdigit()
        ):
            self.advance_char()  # skip '.'
            self._scan_decimal_digits()

        # Exponent part
        if not self.is_eof() and self.peek_char() in ('e', 'E'):
            self.advance_char()
            if not self.is_eof() and self.peek_char() in ('+', '-'):
                self.advance_char()
            self._scan_decimal_digits()

    def _scan_hex_digits(self) -> None:
        while not self.is_eof() and self.peek_char() in '0123456789abcdefABCDEF':
            self.advance_char()

    def _scan_decimal_digits(self) -> None:
        while not self.is_eof() and self.peek_char().isdigit():
            self.advance_char()

    def read_string(self) -> Token:
        quote = self.peek_char()
        self.advance_char()  # skip opening quote

        start_pos = self._chunk_pos

        # Scan until closing quote or EOF
        while not self.is_eof() and self.peek_char() != quote:
            if self.peek_char() == '\\':
                self.advance_char()  # skip backslash
                if not self.is_eof():
                    self.advance_char()  # skip escaped character
            else:
                self.advance_char()

        value = self.chunk[start_pos:self._chunk_pos]

        if not self.is_eof():
            self.advance_char()  # skip closing quote

        return Token("STRING", value, self._line)

    def read_comment(self) -> Token:
        start_pos = self._chunk_pos

        # Consume all characters until newline
        while not self.is_eof() and self.peek_char() != '\n':
            self.advance_char()

        value = self.chunk[start_pos:self._chunk_pos]
        return Token("COMMENT", value, self._line)

    def skip_whitespace(self) -> None:
        while not self.is_eof():
            char = self.peek_char()
            if not char.isspace():
                break
            if char == '\n':
                self._line += 1
            self.advance_char()

    def is_eof(self) -> bool:
        return self._chunk_pos >= len(self.chunk)

    def peek_char(self) -> str:
        if self.is_eof():
            return ''
        return self.chunk[self._chunk_pos]

    def advance_char(self) -> None:
        self._chunk_pos += 1
