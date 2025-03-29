import unittest
from unittest.mock import MagicMock, patch
from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.models import PRSummary, ChangeSummary, PullRequest, CodeReview, PRType


class TestPullRequestReporter(unittest.TestCase):
    def setUp(self):
        # Create mock models
        self.pr_summary = PRSummary(
            overview="This PR adds a new feature",
            pr_type=PRType.feature,
            major_files=["src/main.py"]
        )

        self.code_summaries = [
            ChangeSummary(full_name="src/main.py", summary="Added new function")
        ]

        self.pull_request = MagicMock(spec=PullRequest)
        self.pull_request.repository_name = "test/repo"
        self.pull_request.pull_request_number = 42
        self.pull_request.title = "Add new feature"
        self.pull_request.url = "https://github.com/test/repo/pull/42"

        # Mock code review with a mock file inside
        mock_file = MagicMock()
        mock_file.full_name = "src/main.py"
        mock_file.diff_url = "https://github.com/test/repo/pull/42/files#diff-123"

        self.code_reviews = [
            MagicMock(spec=CodeReview)
        ]
        self.code_reviews[0].file = mock_file
        self.code_reviews[0].review = "Looks good, but consider adding tests"

        # Mock the nested reporters
        patch_summary_reporter = patch('codedog.actors.reporters.pull_request.PRSummaryMarkdownReporter')
        self.mock_summary_reporter = patch_summary_reporter.start()
        self.addCleanup(patch_summary_reporter.stop)

        patch_review_reporter = patch('codedog.actors.reporters.pull_request.CodeReviewMarkdownReporter')
        self.mock_review_reporter = patch_review_reporter.start()
        self.addCleanup(patch_review_reporter.stop)

        # Set up reporter instance returns
        self.mock_summary_reporter.return_value.report.return_value = "PR Summary Report"
        self.mock_review_reporter.return_value.report.return_value = "Code Review Report"

        # Create reporter
        self.reporter = PullRequestReporter(
            pr_summary=self.pr_summary,
            code_summaries=self.code_summaries,
            pull_request=self.pull_request,
            code_reviews=self.code_reviews
        )

    def test_reporter_initialization(self):
        self.assertEqual(self.reporter._pr_summary, self.pr_summary)
        self.assertEqual(self.reporter._code_summaries, self.code_summaries)
        self.assertEqual(self.reporter._pull_request, self.pull_request)
        self.assertEqual(self.reporter._code_reviews, self.code_reviews)

    def test_report_generation(self):
        report = self.reporter.report()

        # Verify the summary reporter was instantiated
        self.mock_summary_reporter.assert_called_once_with(
            pr_summary=self.pr_summary,
            code_summaries=self.code_summaries,
            pull_request=self.pull_request,
            language='en'
        )

        # Verify the review reporter was instantiated
        self.mock_review_reporter.assert_called_once_with(
            self.code_reviews, 'en'
        )

        # Verify report called on both reporters
        self.mock_summary_reporter.return_value.report.assert_called_once()
        self.mock_review_reporter.return_value.report.assert_called_once()

        # Verify report contains expected sections
        self.assertIn("test/repo #42", report)
        self.assertIn("PR Summary Report", report)
        self.assertIn("Code Review Report", report)

    def test_reporter_with_telemetry(self):
        # Test report generation with telemetry data
        telemetry_data = {
            "start_time": 1625097600,  # Example timestamp
            "time_usage": 3.5,
            "cost": 0.05,
            "tokens": 2500
        }

        reporter = PullRequestReporter(
            pr_summary=self.pr_summary,
            code_summaries=self.code_summaries,
            pull_request=self.pull_request,
            code_reviews=self.code_reviews,
            telemetry=telemetry_data
        )

        # Generate and verify report has telemetry info
        generated_report = reporter.report()

        # Verify telemetry section exists - match actual output format
        self.assertIn("Time usage", generated_report)
        self.assertIn("3.50s", generated_report)  # Time usage
        self.assertIn("$0.0500", generated_report)  # Cost

    def test_reporter_chinese_language(self):
        # Test report generation with Chinese language
        reporter = PullRequestReporter(
            pr_summary=self.pr_summary,
            code_summaries=self.code_summaries,
            pull_request=self.pull_request,
            code_reviews=self.code_reviews,
            language="cn"
        )

        # Should instantiate reporters with cn language
        # Generate report (but we don't need to use the result for this test)
        reporter.report()

        # Verify Chinese reporters were instantiated
        self.mock_summary_reporter.assert_called_once_with(
            pr_summary=self.pr_summary,
            code_summaries=self.code_summaries,
            pull_request=self.pull_request,
            language='cn'
        )

        self.mock_review_reporter.assert_called_once_with(
            self.code_reviews, 'cn'
        )


if __name__ == '__main__':
    unittest.main()
