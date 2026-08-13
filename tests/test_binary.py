import io
import unittest

from binary.io import Reader, Writer
from binary.reader import read_header, validate_proto
from codegen.inst import OP
from structs.function import Proto
from structs.instruction import Instruction
from structs.value import Value


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

    def test_empty_string_is_distinct_from_null_string(self):
        buffer = io.BytesIO()
        writer = Writer(buffer)
        writer.write_nullable_string(None)
        writer.write_string("")
        buffer.seek(0)
        reader = Reader(buffer)
        self.assertIsNone(reader.read_nullable_string())
        self.assertEqual(reader.read_string(), "")

    def test_string_requires_null_terminator(self):
        buffer = io.BytesIO((2).to_bytes(8, "little") + b"ab")
        with self.assertRaisesRegex(ValueError, "null terminator"):
            Reader(buffer).read_string()

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

    def test_invalid_opcode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "opcode"):
            Instruction(63)

    def test_invalid_constant_index_is_rejected(self):
        proto = Proto()
        proto.max_stack_size = 1
        proto.consts = [Value.number(1)]
        proto.codes = [Instruction.from_abx(OP["LOADK"], 0, 1)]
        with self.assertRaisesRegex(ValueError, "constant index"):
            validate_proto(proto)

    def test_invalid_jump_target_is_rejected(self):
        proto = Proto()
        proto.max_stack_size = 1
        proto.codes = [Instruction.from_asbx(OP["JMP"], 0, 10)]
        with self.assertRaisesRegex(ValueError, "jump target"):
            validate_proto(proto)

    def test_non_writing_instruction_still_validates_base_register(self):
        proto = Proto()
        proto.max_stack_size = 1
        proto.codes = [Instruction.from_abc(OP["SETTABLE"], 2, 0, 0)]
        with self.assertRaisesRegex(ValueError, "register"):
            validate_proto(proto)


if __name__ == "__main__":
    unittest.main()
