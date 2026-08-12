import tempfile
import unittest
from pathlib import Path

from tools.differential_test import ExecutionResult, compare_results, load_cases


class TestDifferentialRunner(unittest.TestCase):
    def test_default_corpus_has_unique_cases(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 10)
        self.assertEqual(len({case.name for case in cases}), len(cases))

    def test_successful_results_compare_exact_stdout(self):
        reference = ExecutionResult(0, "one\n", "")
        self.assertIsNone(compare_results(reference, ExecutionResult(0, "one\n", "warning")))
        self.assertIn("stdout differs", compare_results(reference, ExecutionResult(0, "two\n", "")))

    def test_error_text_is_implementation_specific(self):
        reference = ExecutionResult(1, "", "reference error")
        pylua = ExecutionResult(1, "", "different pylua error")
        self.assertIsNone(compare_results(reference, pylua))

    def test_outcome_mismatch_is_reported(self):
        mismatch = compare_results(ExecutionResult(1, "", "error"), ExecutionResult(0, "", ""))
        self.assertIn("outcome differs", mismatch)

    def test_duplicate_case_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_text(
                '[{"name":"same","source":"print(1)"},{"name":"same","source":"print(2)"}]',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_cases(path)


if __name__ == "__main__":
    unittest.main()
