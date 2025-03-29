import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_pull_request():
    """Create a mock PullRequest object for testing."""
    mock_pr = MagicMock()
    mock_pr.pull_request_id = 123
    mock_pr.repository_id = 456
    mock_pr.pull_request_number = 42
    mock_pr.title = "Test PR"
    mock_pr.body = "PR description"
    mock_pr.url = "https://github.com/test/repo/pull/42"
    mock_pr.repository_name = "test/repo"
    mock_pr.json.return_value = "{}"
    return mock_pr


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    mock = MagicMock()
    mock.invoke.return_value = {"text": "Test response"}
    return mock
