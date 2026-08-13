import struct
from typing import BinaryIO


class Reader:
    MAX_STRING_SIZE = 16 * 1024 * 1024

    def __init__(self, file: BinaryIO):
        self.file = file
        self.endian = "<"
        self.size_len = 8

    def configure(self, endianness: int, size_len: int) -> None:
        self.endian = "<" if endianness == 1 else ">"
        self.size_len = size_len

    def read_bytes(self, n: int) -> bytes:
        data = self.file.read(n)
        if len(data) != n:
            raise EOFError("Unexpected end of file")
        return data

    def read_uint8(self) -> int:
        """Read a single unsigned byte."""
        return struct.unpack("B", self.read_bytes(1))[0]

    def read_uint32(self) -> int:
        """Read an unsigned 32-bit integer."""
        return struct.unpack(f"{self.endian}I", self.read_bytes(4))[0]

    def read_uint64(self) -> int:
        """Read an unsigned 64-bit integer."""
        return struct.unpack(f"{self.endian}Q", self.read_bytes(8))[0]

    def read_double(self) -> float:
        """Read a double-precision float."""
        return struct.unpack(f"{self.endian}d", self.read_bytes(8))[0]

    def read_size_t(self) -> int:
        if self.size_len == 4:
            return self.read_uint32()
        if self.size_len == 8:
            return self.read_uint64()
        raise ValueError(f"Unsupported size_t width: {self.size_len}")

    def read_nullable_string(self) -> str | None:
        length = self.read_size_t()
        if length == 0:
            return None
        if length > self.MAX_STRING_SIZE:
            raise ValueError(f"Bytecode string is too large: {length} bytes")
        string_bytes = self.read_bytes(length - 1)  # Exclude null terminator
        if self.read_bytes(1) != b"\x00":
            raise ValueError("Bytecode string is missing its null terminator")
        return string_bytes.decode("utf-8")

    def read_string(self) -> str:
        value = self.read_nullable_string()
        if value is None:
            raise ValueError("Unexpected null bytecode string")
        return value


class Writer:
    def __init__(self, file: BinaryIO, endianness: int = 1, size_len: int = 8):
        self.file = file
        self.endian = "<" if endianness == 1 else ">"
        self.size_len = size_len

    def write_bytes(self, data: bytes) -> None:
        """Write bytes to the file."""
        self.file.write(data)

    def write_uint8(self, value: int) -> None:
        """Write a single unsigned byte."""
        self.file.write(struct.pack("B", value))

    def write_uint32(self, value: int) -> None:
        """Write an unsigned 32-bit integer."""
        self.file.write(struct.pack(f"{self.endian}I", value))

    def write_uint64(self, value: int) -> None:
        """Write an unsigned 64-bit integer."""
        self.file.write(struct.pack(f"{self.endian}Q", value))

    def write_double(self, value: float) -> None:
        """Write a double-precision float."""
        self.file.write(struct.pack(f"{self.endian}d", value))

    def write_size_t(self, value: int) -> None:
        if self.size_len == 4:
            self.write_uint32(value)
        elif self.size_len == 8:
            self.write_uint64(value)
        else:
            raise ValueError(f"Unsupported size_t width: {self.size_len}")

    def write_nullable_string(self, value: str | None) -> None:
        """Write a string to the file."""
        if value is None:
            self.write_size_t(0)
            return
        string_bytes = value.encode("utf-8")
        length = len(string_bytes) + 1  # Include null terminator
        self.write_size_t(length)
        self.file.write(string_bytes)
        self.file.write(b"\x00")  # Write null terminator

    def write_string(self, value: str) -> None:
        self.write_nullable_string(value)
