import unittest
from unittest.mock import MagicMock
from codedog.processors.pull_request_processor import PullRequestProcessor
from codedog.models import ChangeFile, ChangeSummary, PullRequest, ChangeStatus


class TestPullRequestProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = PullRequestProcessor()

        # Create mock change files
        self.python_file = ChangeFile(
            blob_id=123,
            sha="abc123",
            full_name="src/main.py",
            source_full_name="src/main.py",
            status=ChangeStatus.modified,
            pull_request_id=42,
            start_commit_id=111,
            end_commit_id=222,
            name="main.py",
            suffix="py"
        )

        self.text_file = ChangeFile(
            blob_id=456,
            sha="def456",
            full_name="README.md",
            source_full_name="README.md",
            status=ChangeStatus.modified,
            pull_request_id=42,
            start_commit_id=111,
            end_commit_id=222,
            name="README.md",
            suffix="md"
        )

        self.deleted_file = ChangeFile(
            blob_id=789,
            sha="ghi789",
            full_name="src/old.py",
            source_full_name="src/old.py",
            status=ChangeStatus.deletion,
            pull_request_id=42,
            start_commit_id=111,
            end_commit_id=222,
            name="old.py",
            suffix="py"
        )

        # Create mock PR
        self.pr = MagicMock(spec=PullRequest)
        self.pr.change_files = [self.python_file, self.text_file, self.deleted_file]
        self.pr.title = "Test PR"
        self.pr.body = "PR description"
        self.pr.related_issues = []

    def test_is_code_file(self):
        self.assertTrue(self.processor.is_code_file(self.python_file))
        self.assertFalse(self.processor.is_code_file(self.text_file))

    def test_get_diff_code_files(self):
        files = self.processor.get_diff_code_files(self.pr)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].full_name, "src/main.py")

    def test_build_change_summaries(self):
        inputs = [
            {"name": "src/main.py", "language": "python", "content": "diff content"}
        ]
        outputs = [
            {"text": "Added new feature"}
        ]

        summaries = self.processor.build_change_summaries(inputs, outputs)
        self.assertEqual(len(summaries), 1)
        self.assertIsInstance(summaries[0], ChangeSummary)
        self.assertEqual(summaries[0].full_name, "src/main.py")
        self.assertEqual(summaries[0].summary, "Added new feature")

    def test_material_generation_with_empty_lists(self):
        # Test generating material with empty lists
        empty_pr = MagicMock(spec=PullRequest)
        empty_pr.change_files = []

        # Should handle empty file list gracefully
        result = self.processor.gen_material_change_files([])
        self.assertEqual(result, "")

        # Should handle empty code summaries
        result = self.processor.gen_material_code_summaries([])
        self.assertEqual(result, "\n")

    def test_different_file_statuses(self):
        # Test handling different file statuses
        renamed_file = ChangeFile(
            blob_id=111,
            sha="abc111",
            full_name="src/new_name.py",
            source_full_name="src/old_name.py",
            status=ChangeStatus.renaming,
            pull_request_id=42,
            start_commit_id=111,
            end_commit_id=222,
            name="new_name.py",
            suffix="py"
        )

        copied_file = ChangeFile(
            blob_id=222,
            sha="abc222",
            full_name="src/copy.py",
            source_full_name="src/original.py",
            status=ChangeStatus.copy,
            pull_request_id=42,
            start_commit_id=111,
            end_commit_id=222,
            name="copy.py",
            suffix="py"
        )

        # Test renamed file template
        result = self.processor._build_status_template_rename(renamed_file)
        self.assertIn("renamed from", result)
        self.assertIn("src/old_name.py", result)

        # Test copied file template
        result = self.processor._build_status_template_copy(copied_file)
        self.assertIn("copied from", result)
        self.assertIn("src/original.py", result)


if __name__ == '__main__':
    unittest.main()
