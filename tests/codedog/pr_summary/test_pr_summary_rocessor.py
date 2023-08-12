import unittest
from unittest.mock import MagicMock

from codedog.models import ChangeFile, ChangeStatus, ChangeSummary, PullRequest
from codedog.processors.pull_request_processor import (
    SUPPORT_CODE_FILE_SUFFIX,
    PullRequestProcessor,
)


class TestPRSummaryProcessor(unittest.TestCase):
    def setUp(self):
        self.pr_processor = PullRequestProcessor()

    def test_is_code_file(self):
        code_file = ChangeFile(
            blob_id=1,
            sha="",
            full_name="path/test.py",
            name="test.py",
            suffix="py",
            source_full_name="",
            status=ChangeStatus.addition,
            pull_request_id=0,
            start_commit_id=0,
            end_commit_id=0,
        )
        non_code_file = ChangeFile(
            blob_id=1,
            sha="",
            full_name="path/test.txt",
            name="test.txt",
            suffix="txt",
            source_full_name="",
            status=ChangeStatus.addition,
            pull_request_id=0,
            start_commit_id=0,
            end_commit_id=0,
        )
        self.assertTrue(self.pr_processor.is_code_file(code_file))
        self.assertFalse(self.pr_processor.is_code_file(non_code_file))

    def test_get_diff_code_files(self):
        change_files = [
            ChangeFile(
                blob_id=1,
                sha="",
                full_name=f"path/file{i}.{ext}",
                name=f"file{i}.{ext}",
                suffix=ext,
                source_full_name="",
                status=ChangeStatus.addition,
                pull_request_id=0,
                start_commit_id=0,
                end_commit_id=0,
            )
            for i, ext in enumerate(SUPPORT_CODE_FILE_SUFFIX)
        ]
        pr = MagicMock(change_files=change_files)

        self.assertEqual(self.pr_processor.get_diff_code_files(pr), change_files)

    def test_gen_material_change_files(self):
        change_files = [
            ChangeFile(
                blob_id=1,
                sha="",
                full_name="path/test.py",
                name="test.py",
                suffix="py",
                source_full_name="",
                status=status,
                pull_request_id=0,
                start_commit_id=0,
                end_commit_id=0,
            )
            for status in ChangeStatus
        ]
        material = self.pr_processor.gen_material_change_files(change_files)
        self.assertIn("Added files:", material)
        self.assertIn("Copied files:", material)
        self.assertIn("- path/test.py", material)

    def test_gen_material_code_summaries(self):
        code_summaries = [ChangeSummary(full_name="file.py", summary="summary")]
        material = self.pr_processor.gen_material_code_summaries(code_summaries)
        self.assertIn("summary", material)

    def test_gen_material_pr_metadata(self):
        pr = PullRequest(pull_request_id=1, repository_id=1, title="PR title", body="PR body")
        material = self.pr_processor.gen_material_pr_metadata(pr)
        self.assertIn("PR title", material)
        self.assertIn("PR body", material)

    def test_build_change_summaries(self):
        input_summaries = [{"name": "file1.py", "content": "x"}, {"name": "file2.py", "content": "y"}]
        output_summaries = [{"text": "summary1"}, {"text": "summary2"}]
        result = self.pr_processor.build_change_summaries(input_summaries, output_summaries)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].full_name, "file1.py")
        self.assertEqual(result[0].summary, "summary1")
        self.assertEqual(result[1].full_name, "file2.py")
        self.assertEqual(result[1].summary, "summary2")

    def test_build_status_template_default(self):
        change_file = ChangeFile(
            blob_id=1,
            sha="",
            full_name="path/test.py",
            name="test.py",
            suffix="py",
            source_full_name="source_path/source_test.py",
            status=ChangeStatus.addition,
            pull_request_id=0,
            start_commit_id=0,
            end_commit_id=0,
        )
        template_default = self.pr_processor._build_status_template_default(change_file)
        template_copy = self.pr_processor._build_status_template_copy(change_file)
        template_rename = self.pr_processor._build_status_template_rename(change_file)
        self.assertEqual(template_default, "- path/test.py")
        self.assertEqual(template_copy, "- path/test.py (copied from source_path/source_test.py)")
        self.assertEqual(template_rename, "- path/test.py (renamed from source_path/source_test.py)")


if __name__ == "__main__":
    unittest.main()
