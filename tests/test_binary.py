import io
import unittest

from binary.io import Reader, Writer
from binary.reader import read_header


class TestBinaryIO(unittest.TestCase):
    def test_string_roundtrip_for_supported_layouts(self):
        for endianness in (0, 1):
            for size_len in (4, 8):
                with self.subTest(endianness=endianness, size_len=size_len):
                    buffer = io.BytesIO()
                    Writer(buffer, endianness, size_len).write_string("Lua 字节码")
                    buffer.seek(0)
                    reader = Reader(buffer)
                    reader.configure(endianness, size_len)
                    self.assertEqual(reader.read_string(), "Lua 字节码")

    def test_header_configures_reader_layout(self):
        data = b"\x1bLua\x51\x00\x00\x04\x04\x04\x08\x00"
        reader = Reader(io.BytesIO(data))
        header = read_header(reader)
        self.assertEqual(header.size_len, 4)
        self.assertEqual(reader.endian, ">")
        self.assertEqual(reader.size_len, 4)

    def test_header_rejects_unsupported_number_layout(self):
        data = b"\x1bLua\x51\x00\x01\x04\x08\x04\x08\x01"
        with self.assertRaisesRegex(ValueError, "double-precision"):
            read_header(Reader(io.BytesIO(data)))

    def test_string_size_is_bounded(self):
        buffer = io.BytesIO((Reader.MAX_STRING_SIZE + 1).to_bytes(8, "little"))
        with self.assertRaisesRegex(ValueError, "too large"):
            Reader(buffer).read_string()


if __name__ == "__main__":
    unittest.main()
