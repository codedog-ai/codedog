"""
Code analysis module for GitHub and GitLab repositories.
Provides functionality to analyze code changes and generate reports.
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
from utils.remote_repository_analyzer import RemoteRepositoryAnalyzer

def format_commit_for_json(commit):
    """Format commit data for JSON serialization."""
    return {
        'hash': commit.hash,
        'author': commit.author,
        'date': commit.date.isoformat(),
        'message': commit.message,
        'files': commit.files,
        'added_lines': commit.added_lines,
        'deleted_lines': commit.deleted_lines,
        'effective_lines': commit.effective_lines
    }

def save_analysis_results(output_path, commits, file_diffs, stats, show_diffs=False):
    """
    Save analysis results to a JSON file.
    Args:
        output_path: Path where to save the JSON file
        commits: List of commit objects
        file_diffs: Dictionary of file diffs
        stats: Dictionary containing analysis statistics
        show_diffs: Whether to include file diffs in the output
    """
    results = {
        'summary': {
            'total_commits': stats['total_commits'],
            'total_files': len(stats['files_changed']),
            'total_additions': stats['total_additions'],
            'total_deletions': stats['total_deletions'],
            'files_changed': sorted(stats['files_changed'])
        },
        'commits': [format_commit_for_json(commit) for commit in commits]
    }
    
    if show_diffs:
        results['file_diffs'] = file_diffs
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def analyze_repository(repo_url, author, days=7, include=None, exclude=None, token=None):
    """
    Analyze a Git repository and return the analysis results.
    
    Args:
        repo_url: URL of the repository to analyze
        author: Author name or email to filter commits
        days: Number of days to look back (default: 7)
        include: List of file extensions to include
        exclude: List of file extensions to exclude
        token: GitHub/GitLab access token
    
    Returns:
        Tuple of (commits, file_diffs, stats)
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    analyzer = RemoteRepositoryAnalyzer(repo_url, token)
    
    return analyzer.get_file_diffs_by_timeframe(
        author=author,
        start_date=start_date,
        end_date=end_date,
        include_extensions=include,
        exclude_extensions=exclude
    ) 