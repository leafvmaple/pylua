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