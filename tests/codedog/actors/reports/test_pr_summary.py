import unittest

from codedog.actors import PRSummaryMarkdownReporter  # 请替换为你的模块
from codedog.actors.reporters.base import Reporter
from codedog.localization import Localization
from codedog.models import ChangeFile, ChangeSummary, PRSummary, PRType, PullRequest
from codedog.models.change_file import ChangeStatus

# full_name, status, summary, is_code, is_major
mock_files = [
    ("a/b.py", ChangeStatus.addition, "Important add b", True, True),
    ("a/c.py", ChangeStatus.modified, "Important update c", True, True),
    ("d/e.py", ChangeStatus.deletion, "Unimportant delete e", True, False),
    ("f", ChangeStatus.modified, None, False, False),
]
# Mock objects
mock_pr_summary = PRSummary(
    overview="mock overview", pr_type=PRType.feature, major_files=[file[0] for file in mock_files if file[4]]
)
mock_code_summaries = [ChangeSummary(full_name=file[0], summary=file[2]) for file in mock_files if file[3]]
mock_pull_request = PullRequest(
    pull_request_id=1,
    repository_id=1,
    change_files=[
        ChangeFile(
            blob_id=1,
            sha="mock_sha",
            full_name=file[0],
            source_full_name=file[0],
            status=file[1],
            pull_request_id=1,
            start_commit_id=1,
            end_commit_id=1,
            name=file[0].split("/")[-1],
            suffix=file[0].split(".")[-1],
        )
        for file in mock_files
    ],
)


class TestPRSummaryMDReporter(unittest.TestCase):
    def setUp(self):
        self.reporter = PRSummaryMarkdownReporter(mock_pr_summary, mock_code_summaries, mock_pull_request)

    def test_init(self):
        self.assertIsInstance(self.reporter, PRSummaryMarkdownReporter)
        self.assertIsInstance(self.reporter, Reporter)
        self.assertIsInstance(self.reporter, Localization)
        self.assertEqual(self.reporter._pr_summary, mock_pr_summary)
        self.assertEqual(len(self.reporter._code_summaries), len(mock_code_summaries))
        self.assertEqual(self.reporter._pull_request, mock_pull_request)

    def test_report(self):
        fake_report = "abc"
        self.reporter._markdown = fake_report
        report = self.reporter.report()
        self.assertIsInstance(report, str)
        self.assertEqual(report, fake_report)

    def test_generate_pr_overview(self):
        pr_overview = self.reporter._generate_pr_overview()
        self.assertIsInstance(pr_overview, str)
        print(pr_overview)

    def test_generate_change_overivew(self):
        change_overview = self.reporter._generate_change_overivew()
        self.assertIsInstance(change_overview, str)

    def test_generate_file_changes(self):
        file_changes = self.reporter._generate_file_changes()
        self.assertIsInstance(file_changes, str)

    def test_generate_markdown(self):
        markdown = self.reporter._generate_markdown()
        self.assertIsInstance(markdown, str)


if __name__ == "__main__":
    unittest.main()
