from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
import os
from github import Github
from gitlab import Gitlab
from urllib.parse import urlparse

@dataclass
class CommitInfo:
    """Store commit information"""
    hash: str
    author: str
    date: datetime
    message: str
    files: List[str]
    diff: str
    added_lines: int = 0
    deleted_lines: int = 0
    effective_lines: int = 0

class RemoteRepositoryAnalyzer:
    """Analyzer for remote Git repositories (GitHub and GitLab)"""
    
    def __init__(self, repo_url: str, access_token: Optional[str] = None):
        """Initialize the analyzer with repository URL and optional access token.
        
        Args:
            repo_url: Full URL to the repository (e.g., https://github.com/owner/repo)
            access_token: GitHub/GitLab access token (can also be set via GITHUB_TOKEN/GITLAB_TOKEN env vars)
        """
        self.repo_url = repo_url
        parsed_url = urlparse(repo_url)
        
        # Extract platform, owner, and repo name from URL
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) < 2:
            raise ValueError(f"Invalid repository URL: {repo_url}")
            
        self.owner = path_parts[0]
        self.repo_name = path_parts[1]
        
        # Determine platform and initialize client
        if 'github.com' in parsed_url.netloc:
            self.platform = 'github'
            token = access_token or os.environ.get('GITHUB_TOKEN')
            if not token:
                raise ValueError("GitHub token required. Set via access_token or GITHUB_TOKEN env var")
            self.client = Github(token)
            self.repo = self.client.get_repo(f"{self.owner}/{self.repo_name}")
            
        elif 'gitlab.com' in parsed_url.netloc:
            self.platform = 'gitlab'
            token = access_token or os.environ.get('GITLAB_TOKEN')
            if not token:
                raise ValueError("GitLab token required. Set via access_token or GITLAB_TOKEN env var")
            self.client = Gitlab('https://gitlab.com', private_token=token)
            self.repo = self.client.projects.get(f"{self.owner}/{self.repo_name}")
        else:
            raise ValueError(f"Unsupported Git platform: {parsed_url.netloc}")

    def get_commits_by_author_and_timeframe(
        self,
        author: str,
        start_date: datetime,
        end_date: datetime,
        include_extensions: Optional[List[str]] = None,
        exclude_extensions: Optional[List[str]] = None
    ) -> List[CommitInfo]:
        """Get commits by author within a specified timeframe.
        
        Args:
            author: Author name or email
            start_date: Start date for commit search
            end_date: End date for commit search
            include_extensions: List of file extensions to include (e.g. ['.py', '.js'])
            exclude_extensions: List of file extensions to exclude (e.g. ['.md', '.txt'])
            
        Returns:
            List of CommitInfo objects containing commit details
        """
        commits = []
        
        if self.platform == 'github':
            # GitHub API query
            gh_commits = self.repo.get_commits(
                author=author,
                since=start_date,
                until=end_date
            )
            
            for commit in gh_commits:
                files = []
                diff = ""
                added_lines = 0
                deleted_lines = 0
                
                # Get detailed commit info including diffs
                detailed_commit = self.repo.get_commit(commit.sha)
                for file in detailed_commit.files:
                    if self._should_include_file(file.filename, include_extensions, exclude_extensions):
                        files.append(file.filename)
                        if file.patch:
                            diff += f"diff --git a/{file.filename} b/{file.filename}\n{file.patch}\n"
                        added_lines += file.additions
                        deleted_lines += file.deletions
                
                if files:  # Only include commits that modified relevant files
                    commits.append(CommitInfo(
                        hash=commit.sha,
                        author=commit.commit.author.name,
                        date=commit.commit.author.date,
                        message=commit.commit.message,
                        files=files,
                        diff=diff,
                        added_lines=added_lines,
                        deleted_lines=deleted_lines,
                        effective_lines=added_lines - deleted_lines
                    ))
                    
        elif self.platform == 'gitlab':
            # GitLab API query
            gl_commits = self.repo.commits.list(
                all=True,
                query_parameters={
                    'author': author,
                    'since': start_date.isoformat(),
                    'until': end_date.isoformat()
                }
            )
            
            for commit in gl_commits:
                # Get detailed commit info including diffs
                detailed_commit = self.repo.commits.get(commit.id)
                diff = detailed_commit.diff()
                
                files = []
                added_lines = 0
                deleted_lines = 0
                
                for change in diff:
                    if self._should_include_file(change['new_path'], include_extensions, exclude_extensions):
                        files.append(change['new_path'])
                        # Parse diff to count lines
                        if change.get('diff'):
                            for line in change['diff'].splitlines():
                                if line.startswith('+') and not line.startswith('+++'):
                                    added_lines += 1
                                elif line.startswith('-') and not line.startswith('---'):
                                    deleted_lines += 1
                
                if files:  # Only include commits that modified relevant files
                    commits.append(CommitInfo(
                        hash=commit.id,
                        author=commit.author_name,
                        date=datetime.fromisoformat(commit.created_at),
                        message=commit.message,
                        files=files,
                        diff='\n'.join(d['diff'] for d in diff if d.get('diff')),
                        added_lines=added_lines,
                        deleted_lines=deleted_lines,
                        effective_lines=added_lines - deleted_lines
                    ))
        
        return commits

    def _should_include_file(
        self,
        filename: str,
        include_extensions: Optional[List[str]] = None,
        exclude_extensions: Optional[List[str]] = None
    ) -> bool:
        """Check if a file should be included based on its extension.
        
        Args:
            filename: Name of the file to check
            include_extensions: List of file extensions to include
            exclude_extensions: List of file extensions to exclude
            
        Returns:
            Boolean indicating whether the file should be included
        """
        if not filename:
            return False
            
        ext = os.path.splitext(filename)[1].lower()
        
        if exclude_extensions and ext in exclude_extensions:
            return False
            
        if include_extensions:
            return ext in include_extensions
            
        return True

    def get_file_diffs_by_timeframe(
        self,
        author: str,
        start_date: datetime,
        end_date: datetime,
        include_extensions: Optional[List[str]] = None,
        exclude_extensions: Optional[List[str]] = None
    ) -> Tuple[List[CommitInfo], Dict[str, str], Dict[str, Dict[str, Any]]]:
        """Get file diffs and statistics for commits within a timeframe.
        
        Args:
            author: Author name or email
            start_date: Start date for commit search
            end_date: End date for commit search
            include_extensions: List of file extensions to include
            exclude_extensions: List of file extensions to exclude
            
        Returns:
            Tuple containing:
            - List of CommitInfo objects
            - Dict mapping filenames to their diffs
            - Dict containing statistics about the changes
        """
        commits = self.get_commits_by_author_and_timeframe(
            author, start_date, end_date,
            include_extensions, exclude_extensions
        )
        
        file_diffs = {}
        stats = {
            'total_commits': len(commits),
            'total_files': 0,
            'total_additions': 0,
            'total_deletions': 0,
            'files_changed': set()
        }
        
        for commit in commits:
            stats['total_files'] += len(commit.files)
            stats['total_additions'] += commit.added_lines
            stats['total_deletions'] += commit.deleted_lines
            stats['files_changed'].update(commit.files)
            
            # Aggregate diffs by file
            for file in commit.files:
                if file not in file_diffs:
                    file_diffs[file] = ""
                file_diffs[file] += f"\n# Commit {commit.hash[:8]} - {commit.message.splitlines()[0]}\n{commit.diff}"
        
        # Convert set to list for JSON serialization
        stats['files_changed'] = list(stats['files_changed'])
        
        return commits, file_diffs, stats 