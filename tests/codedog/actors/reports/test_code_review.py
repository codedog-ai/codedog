import unittest

from codedog.actors import CodeReviewMarkdownReporter
from codedog.models.change_file import ChangeFile, ChangeStatus
from codedog.models.code_review import CodeReview

mock_items = [("")] * 10


class TestCodeReviewMarkdownReporter(unittest.TestCase):
    def setUp(self):
        self.code_reviews = [
            CodeReview(
                file=ChangeFile(
                    blob_id=i,
                    sha=str(i),
                    full_name=f"test/{i}.py",
                    source_full_name="",
                    status=ChangeStatus.modified,
                    pull_request_id=1,
                    start_commit_id=1,
                    end_commit_id=2,
                    name=f"{i}.py",
                    suffix="py",
                ),
                review=f"Review {i}",
            )
            for i, _ in enumerate(mock_items)
        ]

        # 创建 CodeReviewMarkdownReporter 对象
        self.reporter = CodeReviewMarkdownReporter(code_reviews=self.code_reviews, language="en")

    def test_init(self):
        # 测试 __init__ 方法
        self.assertEqual(self.reporter._code_reviews, self.code_reviews)
        self.assertEqual(self.reporter._markdown, "")

    def test_report(self):
        fake_report = "abc"
        self.reporter._markdown = fake_report
        report = self.reporter.report()
        self.assertIsInstance(report, str)
        self.assertEqual(report, fake_report)

    def test_generate_report(self):
        expected_report = self.reporter.template.REPORT_CODE_REVIEW.format(
            feedback="\n".join(
                [
                    self.reporter.template.REPORT_CODE_REVIEW_SEGMENT.format(
                        full_name=cr.file.full_name, url=cr.file.diff_url, review=cr.review
                    )
                    for cr in self.code_reviews
                ]
            )
        )
        self.assertEqual(self.reporter.report(), expected_report)


if __name__ == "__main__":
    unittest.main()
