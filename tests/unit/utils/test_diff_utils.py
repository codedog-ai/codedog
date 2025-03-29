import unittest
from unittest.mock import patch, MagicMock
from codedog.utils.diff_utils import parse_diff, parse_patch_file


class TestDiffUtils(unittest.TestCase):
    @patch('unidiff.PatchSet')
    @patch('io.StringIO')
    def test_parse_diff(self, mock_stringio, mock_patchset):
        # Create mock objects
        mock_result = MagicMock()
        mock_stringio.return_value = "mock_stringio_result"
        mock_patchset.return_value = [mock_result]

        # Test data
        test_diff = "--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-old\n+new\n"

        # Call the function
        result = parse_diff(test_diff)

        # Check the function called the right methods with the right args
        mock_stringio.assert_called_once_with(test_diff)
        mock_patchset.assert_called_once_with(mock_stringio.return_value)

        # Verify the result is what we expect (the mock)
        self.assertEqual(result, mock_result)

    @patch('unidiff.PatchSet')
    @patch('io.StringIO')
    def test_parse_patch_file(self, mock_stringio, mock_patchset):
        # Create mock objects
        mock_result = MagicMock()
        mock_stringio.return_value = "mock_stringio_result"
        mock_patchset.return_value = [mock_result]

        # Test data
        patch_content = "@@ -1,1 +1,1 @@\n-old\n+new\n"
        prev_name = "old_file.py"
        name = "new_file.py"

        # Call the function
        result = parse_patch_file(patch_content, prev_name, name)

        # Check the expected combined string was passed to StringIO
        expected_content = f"--- a/{prev_name}\n+++ b/{name}\n{patch_content}"
        mock_stringio.assert_called_once_with(expected_content)

        # Check PatchSet was called with the StringIO result
        mock_patchset.assert_called_once_with(mock_stringio.return_value)

        # Verify result
        self.assertEqual(result, mock_result)

    @patch('unidiff.PatchSet')
    def test_error_handling(self, mock_patchset):
        # Setup mock to simulate error cases
        mock_patchset.side_effect = Exception("Test exception")

        # Test parse_diff with an error
        with self.assertRaises(Exception):
            parse_diff("Invalid diff")

        # Reset side effect for next test
        mock_patchset.side_effect = None

        # Setup to return empty list
        mock_patchset.return_value = []

        # Test IndexError when no patches
        with self.assertRaises(IndexError):
            parse_diff("Empty diff")

        # Test parse_patch_file with empty list
        with self.assertRaises(IndexError):
            parse_patch_file("Empty patch", "old.py", "new.py")


if __name__ == '__main__':
    unittest.main()
