import unittest

from codedog.actors.reporters.pull_request_review import (
    PullRequestReviewMarkdownReporter,
)
from codedog.models import (
    ChangeFile,
    ChangeSummary,
    CodeReview,
    PRSummary,
    PRType,
    PullRequest,
)
from codedog.models.change_file import ChangeStatus

mock_files = [
    ChangeFile(
        blob_id=1,
        sha="",
        full_name="test/a.py",
        source_full_name="",
        status=ChangeStatus.addition,
        pull_request_id=1,
        start_commit_id=1,
        end_commit_id=1,
        name="a.py",
        suffix="py",
    ),
    ChangeFile(
        blob_id=1,
        sha="",
        full_name="test/b.py",
        source_full_name="",
        status=ChangeStatus.addition,
        pull_request_id=1,
        start_commit_id=1,
        end_commit_id=1,
        name="b.py",
        suffix="py",
    ),
    ChangeFile(
        blob_id=1,
        sha="",
        full_name="test/c.txt",
        source_full_name="",
        status=ChangeStatus.addition,
        pull_request_id=1,
        start_commit_id=1,
        end_commit_id=1,
        name="c.txt",
        suffix="txt",
    ),
]


class TestPullRequestReviewMarkdownReporter(unittest.TestCase):
    def setUp(self):
        # 创建mock对象
        self.mock_pr_summary = PRSummary(overview="PR Summary", pr_type=PRType.test, major_files=["test/a.py"])
        self.mock_code_summary = [
            ChangeSummary(full_name="test/a.py", summary="summary a important"),
            ChangeSummary(full_name="test/b.py", summary="summary b"),
        ]
        self.mock_pull_request = PullRequest(
            pull_request_id=1,
            repository_id=2,
            repository_name="test",
            change_files=mock_files,
        )

        self.mock_code_reviews = [
            CodeReview(file=mock_files[0], review="review a important"),
            CodeReview(file=mock_files[1], review="review b"),
        ]
        self.mock_telemetry = {"start_time": 1618417791, "time_usage": 0.232, "cost": 0.1234, "tokens": 123}

        # 创建测试对象
        self.reporter = PullRequestReviewMarkdownReporter(
            pr_summary=self.mock_pr_summary,
            code_summaries=self.mock_code_summary,
            pull_request=self.mock_pull_request,
            code_reviews=self.mock_code_reviews,
            telemetry=self.mock_telemetry,
        )

    def test_report(self):
        # 在这里你可以对report方法的结果进行断言检查
        report_result = self.reporter.report()

        # 这里只是一个例子，你需要根据你的期望来改变这个断言
        self.assertIsInstance(report_result, str)


if __name__ == "__main__":
    unittest.main()
