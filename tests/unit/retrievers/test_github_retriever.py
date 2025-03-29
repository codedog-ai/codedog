import unittest
from unittest.mock import MagicMock, patch
from github import Github
from github.PullRequest import PullRequest as GHPullRequest
from github.Repository import Repository as GHRepo
from codedog.retrievers.github_retriever import GithubRetriever
from codedog.models import PullRequest, Repository, ChangeFile, ChangeStatus

class TestGithubRetriever(unittest.TestCase):
    def setUp(self):
        # Mock Github client and related objects
        self.mock_github = MagicMock(spec=Github)
        self.mock_repo = MagicMock(spec=GHRepo)
        self.mock_pr = MagicMock(spec=GHPullRequest)
        
        # Setup repo and PR response structure
        self.mock_github.get_repo.return_value = self.mock_repo
        self.mock_repo.get_pull.return_value = self.mock_pr
        
        # Setup basic PR attributes
        self.mock_pr.id = 123
        self.mock_pr.number = 42
        self.mock_pr.title = "Test PR"
        self.mock_pr.body = "PR description with #1 issue reference"
        self.mock_pr.html_url = "https://github.com/test/repo/pull/42"
        
        # Setup head and base for PR
        self.mock_pr.head = MagicMock()
        self.mock_pr.head.repo = MagicMock()
        self.mock_pr.head.repo.id = 456
        self.mock_pr.head.repo.full_name = "test/repo"
        self.mock_pr.head.sha = "abcdef1234567890"
        
        self.mock_pr.base = MagicMock()
        self.mock_pr.base.repo = MagicMock()
        self.mock_pr.base.repo.id = 456
        self.mock_pr.base.sha = "0987654321fedcba"
        
        # Setup mock files
        mock_file = MagicMock()
        mock_file.filename = "src/test.py"
        mock_file.status = "modified"
        mock_file.sha = "abcdef"
        mock_file.patch = "@@ -1,5 +1,7 @@\n def test():\n-    return 1\n+    # Added comment\n+    return 2"
        mock_file.blob_url = "https://github.com/test/repo/blob/abc/src/test.py"
        mock_file.previous_filename = None
        
        self.mock_pr.get_files.return_value = [mock_file]
        
        # Setup mock issue
        mock_issue = MagicMock()
        mock_issue.number = 1
        mock_issue.title = "Test Issue"
        mock_issue.body = "Issue description"
        mock_issue.html_url = "https://github.com/test/repo/issues/1"
        
        self.mock_repo.get_issue.return_value = mock_issue
        
        # Important: Add string attributes to mock_repo for Repository validation
        self.mock_repo.id = 456
        self.mock_repo.name = "repo"
        self.mock_repo.full_name = "test/repo"
        self.mock_repo.html_url = "https://github.com/test/repo"
        
        # Create retriever instance with mocks
        with patch('codedog.retrievers.github_retriever.GithubRetriever._build_diff_content') as mock_build_diff:
            mock_build_diff.return_value = MagicMock()
            self.retriever = GithubRetriever(self.mock_github, "test/repo", 42)

    def test_retriever_type(self):
        self.assertEqual(self.retriever.retriever_type, "Github Retriever")
        
    def test_pull_request_initialization(self):
        pr = self.retriever.pull_request
        self.assertIsInstance(pr, PullRequest)
        self.assertEqual(pr.pull_request_id, 123)
        self.assertEqual(pr.pull_request_number, 42)
        self.assertEqual(pr.title, "Test PR")
        
    def test_changed_files(self):
        # Patch the internal method that causes issues in tests
        with patch('codedog.retrievers.github_retriever.GithubRetriever._build_diff_content') as mock_build_diff:
            mock_build_diff.return_value = MagicMock()
            
            # Force regeneration of changed_files property
            self.retriever._changed_files = None
            
            files = self.retriever.changed_files
            self.assertIsInstance(files, list)
            self.assertGreater(len(files), 0)
            self.assertIsInstance(files[0], ChangeFile)
            self.assertEqual(files[0].full_name, "src/test.py")
        
    def test_parse_issue_numbers(self):
        # Test the private method directly
        issues = self.retriever._parse_issue_numbers(
            "PR with #1 and #2", 
            "Description with #3"
        )
        self.assertEqual(set(issues), {1, 2, 3})
        
    def test_error_handling(self):
        # Test when API calls fail
        mock_github = MagicMock(spec=Github)
        mock_github.get_repo.side_effect = Exception("API Error")
        
        with self.assertRaises(Exception):
            retriever = GithubRetriever(mock_github, "test/repo", 42)

    def test_empty_pr(self):
        # Test PR with no files
        self.mock_pr.get_files.return_value = []
        
        # We need to recreate the retriever to pick up the changes
        with patch('codedog.retrievers.github_retriever.GithubRetriever._build_diff_content') as mock_build_diff:
            mock_build_diff.return_value = MagicMock()
            
            # Force reset of the changed_files property
            self.retriever._changed_files = None
            
            # Verify files list is empty
            self.assertEqual(len(self.retriever.changed_files), 0)

    def test_pr_with_no_issues(self):
        # Test PR with no linked issues
        self.mock_pr.title = "PR without issue"
        self.mock_pr.body = "No issue references"
        
        # Need to recreate the retriever with these changes
        with patch('codedog.retrievers.github_retriever.GithubRetriever._build_diff_content') as mock_build_diff:
            mock_build_diff.return_value = MagicMock()
            
            # Force recreation of the pull_request property
            self.retriever._pull_request = None
            
            # Force the retriever to reload PR data
            pr = self.retriever.pull_request
            
            # The PR should have no related issues
            self.assertEqual(len(pr.related_issues), 0)

if __name__ == '__main__':
    unittest.main() 