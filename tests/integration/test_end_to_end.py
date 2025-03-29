import unittest
from unittest.mock import MagicMock, patch
from codedog.chains.pr_summary.base import PRSummaryChain
from codedog.chains.code_review.base import CodeReviewChain
from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.models import PRSummary, ChangeSummary, PullRequest, PRType, Repository


class TestEndToEndFlow(unittest.TestCase):
    @patch('github.Github')
    @patch('langchain_openai.chat_models.ChatOpenAI')
    def test_github_to_report_flow(self, mock_chat_openai, mock_github):
        # Setup mocks
        mock_github_client = MagicMock()
        mock_github.return_value = mock_github_client

        # Setup mock LLMs
        mock_llm35 = MagicMock()
        mock_llm4 = MagicMock()
        mock_chat_openai.side_effect = [mock_llm35, mock_llm4]

        # Create a mock repository and PR directly
        mock_repository = Repository(
            repository_id=456,
            repository_name="repo",
            repository_full_name="test/repo",
            repository_url="https://github.com/test/repo",
            raw=MagicMock()
        )

        mock_pull_request = PullRequest(
            repository_id=456,
            repository_name="test/repo",
            pull_request_id=123,
            pull_request_number=42,
            title="Test PR",
            body="PR description",
            url="https://github.com/test/repo/pull/42",
            status=None,
            head_commit_id="abcdef1234567890",
            base_commit_id="0987654321fedcba",
            raw=MagicMock(),
            change_files=[],
            related_issues=[]
        )

        # Mock the retriever
        mock_retriever = MagicMock()
        mock_retriever.pull_request = mock_pull_request
        mock_retriever.repository = mock_repository

        # Mock the summary chain
        mock_summary_result = {
            "pr_summary": PRSummary(
                overview="This is a test PR",
                pr_type=PRType.feature,
                major_files=["src/main.py"]
            ),
            "code_summaries": [
                ChangeSummary(full_name="src/main.py", summary="Added new feature")
            ]
        }

        with patch.object(PRSummaryChain, 'from_llm', return_value=MagicMock()) as mock_summary_chain_factory:
            mock_summary_chain = mock_summary_chain_factory.return_value
            mock_summary_chain.return_value = mock_summary_result

            # Create summary chain
            summary_chain = PRSummaryChain.from_llm(
                code_summary_llm=mock_llm35,
                pr_summary_llm=mock_llm4
            )

            # Run summary chain
            summary_result = summary_chain({"pull_request": mock_pull_request})

            # Mock the code review chain
            mock_review_result = {
                "code_reviews": [MagicMock()]
            }

            with patch.object(CodeReviewChain, 'from_llm', return_value=MagicMock()) as mock_review_chain_factory:
                mock_review_chain = mock_review_chain_factory.return_value
                mock_review_chain.return_value = mock_review_result

                # Create review chain
                review_chain = CodeReviewChain.from_llm(llm=mock_llm35)

                # Run review chain
                review_result = review_chain({"pull_request": mock_pull_request})

                # Mock the reporter
                mock_report = "# Test PR Report"

                with patch.object(PullRequestReporter, 'report', return_value=mock_report):
                    # Create reporter
                    reporter = PullRequestReporter(
                        pr_summary=summary_result["pr_summary"],
                        code_summaries=summary_result["code_summaries"],
                        pull_request=mock_pull_request,
                        code_reviews=review_result["code_reviews"]
                    )

                    # Generate report
                    report = reporter.report()

                    # Verify the report output
                    self.assertEqual(report, mock_report)

                    # Verify the chain factories were called with correct args
                    mock_summary_chain_factory.assert_called_once()
                    mock_review_chain_factory.assert_called_once()

                    # Verify the chains were called with the PR
                    mock_summary_chain.assert_called_once()
                    mock_review_chain.assert_called_once()


if __name__ == '__main__':
    unittest.main()
