from __future__ import annotations


class Header:
    signature: bytes = b'\x1bLua'
    version: int = 0x51
    format: int = 0
    endianness: int = 1
    int_len: int = 4
    size_len: int = 4
    inst_len: int = 4
    number_len: int = 8
    number_is_int: bool = False

    SUPPORTED_VERSIONS = (0x51,)  # Lua 5.1
