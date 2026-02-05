import struct
from typing import BinaryIO


class Reader:
    def __init__(self, file: BinaryIO):
        self.file = file

    def read_bytes(self, n: int) -> bytes:
        data = self.file.read(n)
        if len(data) != n:
            raise EOFError("Unexpected end of file")
        return data

    def read_uint8(self) -> int:
        """Read a single unsigned byte."""
        return struct.unpack('B', self.read_bytes(1))[0]

    def read_uint32(self) -> int:
        """Read an unsigned 32-bit integer."""
        return struct.unpack('I', self.read_bytes(4))[0]

    def read_uint64(self) -> int:
        """Read an unsigned 64-bit integer."""
        return struct.unpack('Q', self.read_bytes(8))[0]

    def read_double(self) -> float:
        """Read a double-precision float."""
        return struct.unpack('d', self.read_bytes(8))[0]

    def read_string(self) -> str:
        length = self.read_uint64()
        if length == 0:
            return ""
        string_bytes = self.read_bytes(length - 1)  # Exclude null terminator
        self.read_bytes(1)  # Read and discard null terminator
        return string_bytes.decode('utf-8')


class Writer:
    def __init__(self, file: BinaryIO):
        self.file = file

    def write_bytes(self, data: bytes) -> None:
        """Write bytes to the file."""
        self.file.write(data)

    def write_uint8(self, value: int) -> None:
        """Write a single unsigned byte."""
        self.file.write(struct.pack('B', value))

    def write_uint32(self, value: int) -> None:
        """Write an unsigned 32-bit integer."""
        self.file.write(struct.pack('I', value))

    def write_uint64(self, value: int) -> None:
        """Write an unsigned 64-bit integer."""
        self.file.write(struct.pack('Q', value))

    def write_double(self, value: float) -> None:
        """Write a double-precision float."""
        self.file.write(struct.pack('d', value))

    def write_string(self, value: str) -> None:
        """Write a string to the file."""
        if not value:
            self.write_uint64(0)
            return
        string_bytes = value.encode('utf-8')
        length = len(string_bytes) + 1  # Include null terminator
        self.write_uint64(length)
        self.file.write(string_bytes)
        self.file.write(b'\x00')  # Write null terminator
