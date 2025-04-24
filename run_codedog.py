import argparse
import asyncio
import time
import traceback
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional, Tuple
import os
import re
import sys
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

from github import Github
from gitlab import Gitlab
from langchain_community.callbacks.manager import get_openai_callback

from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.chains import CodeReviewChain, PRSummaryChain
from codedog.retrievers import GithubRetriever, GitlabRetriever
from codedog.utils.langchain_utils import load_model_by_name
from codedog.utils.email_utils import send_report_email
from codedog.utils.git_hooks import install_git_hooks
from codedog.utils.git_log_analyzer import get_file_diffs_by_timeframe, get_commit_diff, CommitInfo
from codedog.utils.code_evaluator import DiffEvaluator, generate_evaluation_markdown


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="CodeDog - AI-powered code review tool")

    # Main operation subparsers
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # PR review command
    pr_parser = subparsers.add_parser("pr", help="Review a GitHub or GitLab pull request")
    pr_parser.add_argument("repository", help="Repository path (e.g. owner/repo)")
    pr_parser.add_argument("pr_number", type=int, help="Pull request number to review")
    pr_parser.add_argument("--platform", choices=["github", "gitlab"], default="github",
                         help="Platform to use (github or gitlab, defaults to github)")
    pr_parser.add_argument("--gitlab-url", help="GitLab URL (defaults to https://gitlab.com or GITLAB_URL env var)")
    pr_parser.add_argument("--email", help="Email addresses to send the report to (comma-separated)")

    # Setup git hooks command
    hook_parser = subparsers.add_parser("setup-hooks", help="Set up git hooks for commit-triggered reviews")
    hook_parser.add_argument("--repo", help="Path to git repository (defaults to current directory)")

    # Developer code evaluation command
    eval_parser = subparsers.add_parser("eval", help="Evaluate code commits of a developer in a time period")
    eval_parser.add_argument("author", help="Developer name or email (partial match)")
    eval_parser.add_argument("--start-date", help="Start date (YYYY-MM-DD), defaults to 7 days ago")
    eval_parser.add_argument("--end-date", help="End date (YYYY-MM-DD), defaults to today")
    eval_parser.add_argument("--repo", help="Git repository path or name (e.g. owner/repo for remote repositories)")
    eval_parser.add_argument("--include", help="Included file extensions, comma separated, e.g. .py,.js")
    eval_parser.add_argument("--exclude", help="Excluded file extensions, comma separated, e.g. .md,.txt")
    eval_parser.add_argument("--model", help="Evaluation model, defaults to CODE_REVIEW_MODEL env var or gpt-3.5")
    eval_parser.add_argument("--email", help="Email addresses to send the report to (comma-separated)")
    eval_parser.add_argument("--output", help="Report output path, defaults to codedog_eval_<author>_<date>.md")
    eval_parser.add_argument("--platform", choices=["github", "gitlab", "local"], default="local",
                         help="Platform to use (github, gitlab, or local, defaults to local)")
    eval_parser.add_argument("--gitlab-url", help="GitLab URL (defaults to https://gitlab.com or GITLAB_URL env var)")

    # Commit review command
    commit_parser = subparsers.add_parser("commit", help="Review a specific commit")
    commit_parser.add_argument("commit_hash", help="Commit hash to review")
    commit_parser.add_argument("--repo", help="Git repository path or name (e.g. owner/repo for remote repositories)")
    commit_parser.add_argument("--include", help="Included file extensions, comma separated, e.g. .py,.js")
    commit_parser.add_argument("--exclude", help="Excluded file extensions, comma separated, e.g. .md,.txt")
    commit_parser.add_argument("--model", help="Review model, defaults to CODE_REVIEW_MODEL env var or gpt-3.5")
    commit_parser.add_argument("--email", help="Email addresses to send the report to (comma-separated)")
    commit_parser.add_argument("--output", help="Report output path, defaults to codedog_commit_<hash>_<date>.md")
    commit_parser.add_argument("--platform", choices=["github", "gitlab", "local"], default="local",
                         help="Platform to use (github, gitlab, or local, defaults to local)")
    commit_parser.add_argument("--gitlab-url", help="GitLab URL (defaults to https://gitlab.com or GITLAB_URL env var)")

    return parser.parse_args()


def parse_emails(emails_str: Optional[str]) -> List[str]:
    """Parse comma-separated email addresses."""
    if not emails_str:
        return []

    return [email.strip() for email in emails_str.split(",") if email.strip()]


def parse_extensions(extensions_str: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated file extensions."""
    if not extensions_str:
        return None

    return [ext.strip() for ext in extensions_str.split(",") if ext.strip()]


async def pr_summary(retriever, summary_chain):
    """Generate PR summary asynchronously."""
    result = await summary_chain.ainvoke(
        {"pull_request": retriever.pull_request}, include_run_info=True
    )
    return result


async def code_review(retriever, review_chain):
    """Generate code review asynchronously."""
    result = await review_chain.ainvoke(
        {"pull_request": retriever.pull_request}, include_run_info=True
    )
    return result


def get_remote_commit_diff(
    platform: str,
    repository_name: str,
    commit_hash: str,
    include_extensions: Optional[List[str]] = None,
    exclude_extensions: Optional[List[str]] = None,
    gitlab_url: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Get commit diff from remote repositories (GitHub or GitLab).

    Args:
        platform (str): Platform to use (github or gitlab)
        repository_name (str): Repository name (e.g. owner/repo)
        commit_hash (str): Commit hash to review
        include_extensions (Optional[List[str]], optional): File extensions to include. Defaults to None.
        exclude_extensions (Optional[List[str]], optional): File extensions to exclude. Defaults to None.
        gitlab_url (Optional[str], optional): GitLab URL. Defaults to None.

    Returns:
        Dict[str, Dict[str, Any]]: Dictionary mapping file paths to their diffs and statistics
    """
    if platform.lower() == "github":
        # Initialize GitHub client
        github_client = Github()  # Will automatically load GITHUB_TOKEN from environment
        print(f"Analyzing GitHub repository {repository_name} for commit {commit_hash}")

        try:
            # Get repository
            repo = github_client.get_repo(repository_name)

            # Get commit
            commit = repo.get_commit(commit_hash)

            # Extract file diffs
            file_diffs = {}
            for file in commit.files:
                # Filter by file extensions
                _, ext = os.path.splitext(file.filename)
                if include_extensions and ext not in include_extensions:
                    continue
                if exclude_extensions and ext in exclude_extensions:
                    continue

                if file.patch:
                    file_diffs[file.filename] = {
                        "diff": f"diff --git a/{file.filename} b/{file.filename}\n{file.patch}",
                        "status": file.status,
                        "additions": file.additions,
                        "deletions": file.deletions,
                    }

            return file_diffs

        except Exception as e:
            error_msg = f"Failed to retrieve GitHub commit: {str(e)}"
            print(error_msg)
            return {}

    elif platform.lower() == "gitlab":
        # Initialize GitLab client
        gitlab_token = os.environ.get("GITLAB_TOKEN", "")
        if not gitlab_token:
            error_msg = "GITLAB_TOKEN environment variable is not set"
            print(error_msg)
            return {}

        # Use provided GitLab URL or fall back to environment variable or default
        gitlab_url = gitlab_url or os.environ.get("GITLAB_URL", "https://gitlab.com")

        gitlab_client = Gitlab(url=gitlab_url, private_token=gitlab_token)
        print(f"Analyzing GitLab repository {repository_name} for commit {commit_hash}")

        try:
            # Get repository
            project = gitlab_client.projects.get(repository_name)

            # Get commit
            commit = project.commits.get(commit_hash)

            # Get commit diff
            diff = commit.diff()

            # Extract file diffs
            file_diffs = {}
            for file_diff in diff:
                file_path = file_diff.get('new_path', '')
                old_path = file_diff.get('old_path', '')
                diff_content = file_diff.get('diff', '')

                # Skip if no diff content
                if not diff_content:
                    continue

                # Filter by file extensions
                _, ext = os.path.splitext(file_path)
                if include_extensions and ext not in include_extensions:
                    continue
                if exclude_extensions and ext in exclude_extensions:
                    continue

                # Determine file status
                if file_diff.get('new_file', False):
                    status = 'A'  # Added
                elif file_diff.get('deleted_file', False):
                    status = 'D'  # Deleted
                else:
                    status = 'M'  # Modified

                # Format diff content
                formatted_diff = f"diff --git a/{old_path} b/{file_path}\n{diff_content}"

                # Count additions and deletions
                additions = diff_content.count('\n+')
                deletions = diff_content.count('\n-')

                file_diffs[file_path] = {
                    "diff": formatted_diff,
                    "status": status,
                    "additions": additions,
                    "deletions": deletions,
                }

            return file_diffs

        except Exception as e:
            error_msg = f"Failed to retrieve GitLab commit: {str(e)}"
            print(error_msg)
            return {}

    else:
        error_msg = f"Unsupported platform: {platform}. Use 'github' or 'gitlab'."
        print(error_msg)
        return {}


def get_remote_commits(
    platform: str,
    repository_name: str,
    author: str,
    start_date: str,
    end_date: str,
    include_extensions: Optional[List[str]] = None,
    exclude_extensions: Optional[List[str]] = None,
    gitlab_url: Optional[str] = None,
) -> Tuple[List[Any], Dict[str, Dict[str, str]], Dict[str, int]]:
    """
    Get commits from remote repositories (GitHub or GitLab).

    Args:
        platform (str): Platform to use (github or gitlab)
        repository_name (str): Repository name (e.g. owner/repo)
        author (str): Author name or email
        start_date (str): Start date (YYYY-MM-DD)
        end_date (str): End date (YYYY-MM-DD)
        include_extensions (Optional[List[str]], optional): File extensions to include. Defaults to None.
        exclude_extensions (Optional[List[str]], optional): File extensions to exclude. Defaults to None.
        gitlab_url (Optional[str], optional): GitLab URL. Defaults to None.

    Returns:
        Tuple[List[Any], Dict[str, Dict[str, str]], Dict[str, int]]: Commits, file diffs, and code stats
    """
    if platform.lower() == "github":
        # Initialize GitHub client
        github_client = Github()  # Will automatically load GITHUB_TOKEN from environment
        print(f"Analyzing GitHub repository {repository_name} for commits by {author}")

        try:
            # Get repository
            repo = github_client.get_repo(repository_name)

            # Convert dates to datetime objects
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # Include the end date

            # Get commits
            commits = []
            commit_file_diffs = {}

            # Get all commits in the repository within the date range
            all_commits = repo.get_commits(since=start_datetime, until=end_datetime)

            # Filter by author
            for commit in all_commits:
                if author.lower() in commit.commit.author.name.lower() or (
                    commit.commit.author.email and author.lower() in commit.commit.author.email.lower()
                ):
                    # Create CommitInfo object
                    commit_info = CommitInfo(
                        hash=commit.sha,
                        author=commit.commit.author.name,
                        date=commit.commit.author.date,
                        message=commit.commit.message,
                        files=[file.filename for file in commit.files],
                        diff="\n".join([f"diff --git a/{file.filename} b/{file.filename}\n{file.patch}" for file in commit.files if file.patch]),
                        added_lines=sum(file.additions for file in commit.files),
                        deleted_lines=sum(file.deletions for file in commit.files),
                        effective_lines=sum(file.additions - file.deletions for file in commit.files)
                    )
                    commits.append(commit_info)

                    # Extract file diffs
                    file_diffs = {}
                    for file in commit.files:
                        if file.patch:
                            # Filter by file extensions
                            _, ext = os.path.splitext(file.filename)
                            if include_extensions and ext not in include_extensions:
                                continue
                            if exclude_extensions and ext in exclude_extensions:
                                continue

                            file_diffs[file.filename] = file.patch

                    commit_file_diffs[commit.sha] = file_diffs

            # Calculate code stats
            code_stats = {
                "total_added_lines": sum(commit.added_lines for commit in commits),
                "total_deleted_lines": sum(commit.deleted_lines for commit in commits),
                "total_effective_lines": sum(commit.effective_lines for commit in commits),
                "total_files": len(set(file for commit in commits for file in commit.files))
            }

            return commits, commit_file_diffs, code_stats

        except Exception as e:
            error_msg = f"Failed to retrieve GitHub commits: {str(e)}"
            print(error_msg)
            return [], {}, {}

    elif platform.lower() == "gitlab":
        # Initialize GitLab client
        gitlab_token = os.environ.get("GITLAB_TOKEN", "")
        if not gitlab_token:
            error_msg = "GITLAB_TOKEN environment variable is not set"
            print(error_msg)
            return [], {}, {}

        # Use provided GitLab URL or fall back to environment variable or default
        gitlab_url = gitlab_url or os.environ.get("GITLAB_URL", "https://gitlab.com")

        gitlab_client = Gitlab(url=gitlab_url, private_token=gitlab_token)
        print(f"Analyzing GitLab repository {repository_name} for commits by {author}")

        try:
            # Get repository
            project = gitlab_client.projects.get(repository_name)

            # Get commits
            commits = []
            commit_file_diffs = {}

            # Convert dates to ISO format
            start_iso = f"{start_date}T00:00:00Z"
            end_iso = f"{end_date}T23:59:59Z"

            # Get all commits in the repository within the date range
            all_commits = project.commits.list(all=True, since=start_iso, until=end_iso)

            # Filter by author
            for commit in all_commits:
                if author.lower() in commit.author_name.lower() or (
                    commit.author_email and author.lower() in commit.author_email.lower()
                ):
                    # Get commit details
                    commit_detail = project.commits.get(commit.id)

                    # Get commit diff
                    diff = commit_detail.diff()

                    # Filter files by extension
                    filtered_diff = []
                    for file_diff in diff:
                        file_path = file_diff.get('new_path', '')
                        _, ext = os.path.splitext(file_path)

                        if include_extensions and ext not in include_extensions:
                            continue
                        if exclude_extensions and ext in exclude_extensions:
                            continue

                        filtered_diff.append(file_diff)

                    # Skip if no files match the filter
                    if not filtered_diff:
                        continue

                    # Get file content for each modified file
                    file_diffs = {}
                    for file_diff in filtered_diff:
                        file_path = file_diff.get('new_path', '')
                        old_path = file_diff.get('old_path', '')
                        diff_content = file_diff.get('diff', '')

                        # Skip if no diff content
                        if not diff_content:
                            continue

                        # Try to get the file content
                        try:
                            # For new files, get the content from the current commit
                            if file_diff.get('new_file', False):
                                try:
                                    # Get the file content and handle both string and bytes
                                    file_obj = project.files.get(file_path=file_path, ref=commit.id)
                                    if hasattr(file_obj, 'content'):
                                        # Raw content from API
                                        file_content = file_obj.content
                                    elif hasattr(file_obj, 'decode'):
                                        # Decode if it's bytes
                                        try:
                                            file_content = file_obj.decode()
                                        except TypeError:
                                            # If decode fails, try to get content directly
                                            file_content = file_obj.content if hasattr(file_obj, 'content') else str(file_obj)
                                    else:
                                        # Fallback to string representation
                                        file_content = str(file_obj)

                                    # Format as a proper diff with the entire file as added
                                    formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- /dev/null\n+++ b/{file_path}\n"
                                    formatted_diff += "\n".join([f"+{line}" for line in file_content.split('\n')])
                                    file_diffs[file_path] = formatted_diff
                                except Exception as e:
                                    print(f"Warning: Could not get content for new file {file_path}: {str(e)}")
                                    # Try to get the raw file content directly from the API
                                    try:
                                        import base64
                                        raw_file = project.repository_files.get(file_path=file_path, ref=commit.id)
                                        if raw_file and hasattr(raw_file, 'content'):
                                            # Decode base64 content if available
                                            try:
                                                decoded_content = base64.b64decode(raw_file.content).decode('utf-8', errors='replace')
                                                formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- /dev/null\n+++ b/{file_path}\n"
                                                formatted_diff += "\n".join([f"+{line}" for line in decoded_content.split('\n')])
                                                file_diffs[file_path] = formatted_diff
                                                continue
                                            except Exception as decode_err:
                                                print(f"Warning: Could not decode content for {file_path}: {str(decode_err)}")
                                    except Exception as api_err:
                                        print(f"Warning: Could not get raw file content for {file_path}: {str(api_err)}")

                                    # Use diff content as fallback
                                    file_diffs[file_path] = diff_content
                            # For deleted files, get the content from the parent commit
                            elif file_diff.get('deleted_file', False):
                                try:
                                    # Get parent commit
                                    parent_commits = project.commits.get(commit.id).parent_ids
                                    if parent_commits:
                                        # Get the file content and handle both string and bytes
                                        try:
                                            file_obj = project.files.get(file_path=old_path, ref=parent_commits[0])
                                            if hasattr(file_obj, 'content'):
                                                # Raw content from API
                                                file_content = file_obj.content
                                            elif hasattr(file_obj, 'decode'):
                                                # Decode if it's bytes
                                                try:
                                                    file_content = file_obj.decode()
                                                except TypeError:
                                                    # If decode fails, try to get content directly
                                                    file_content = file_obj.content if hasattr(file_obj, 'content') else str(file_obj)
                                            else:
                                                # Fallback to string representation
                                                file_content = str(file_obj)

                                            # Format as a proper diff with the entire file as deleted
                                            formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- a/{old_path}\n+++ /dev/null\n"
                                            formatted_diff += "\n".join([f"-{line}" for line in file_content.split('\n')])
                                            file_diffs[file_path] = formatted_diff
                                        except Exception as file_err:
                                            # Try to get the raw file content directly from the API
                                            try:
                                                import base64
                                                raw_file = project.repository_files.get(file_path=old_path, ref=parent_commits[0])
                                                if raw_file and hasattr(raw_file, 'content'):
                                                    # Decode base64 content if available
                                                    try:
                                                        decoded_content = base64.b64decode(raw_file.content).decode('utf-8', errors='replace')
                                                        formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- a/{old_path}\n+++ /dev/null\n"
                                                        formatted_diff += "\n".join([f"-{line}" for line in decoded_content.split('\n')])
                                                        file_diffs[file_path] = formatted_diff
                                                    except Exception as decode_err:
                                                        print(f"Warning: Could not decode content for deleted file {old_path}: {str(decode_err)}")
                                                        file_diffs[file_path] = diff_content
                                                else:
                                                    file_diffs[file_path] = diff_content
                                            except Exception as api_err:
                                                print(f"Warning: Could not get raw file content for deleted file {old_path}: {str(api_err)}")
                                                file_diffs[file_path] = diff_content
                                    else:
                                        file_diffs[file_path] = diff_content
                                except Exception as e:
                                    print(f"Warning: Could not get content for deleted file {old_path}: {str(e)}")
                                    file_diffs[file_path] = diff_content
                            # For modified files, use the diff content
                            else:
                                # Check if diff_content is empty or minimal
                                if not diff_content or len(diff_content.strip()) < 10:
                                    # Try to get the full file content for better context
                                    try:
                                        # Get the file content and handle both string and bytes
                                        file_obj = project.files.get(file_path=file_path, ref=commit.id)
                                        if hasattr(file_obj, 'content'):
                                            # Raw content from API
                                            file_content = file_obj.content
                                        elif hasattr(file_obj, 'decode'):
                                            # Decode if it's bytes
                                            try:
                                                file_content = file_obj.decode()
                                            except TypeError:
                                                # If decode fails, try to get content directly
                                                file_content = file_obj.content if hasattr(file_obj, 'content') else str(file_obj)
                                        else:
                                            # Fallback to string representation
                                            file_content = str(file_obj)

                                        # Format as a proper diff with the entire file
                                        formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- a/{old_path}\n+++ b/{file_path}\n"
                                        formatted_diff += "\n".join([f"+{line}" for line in file_content.split('\n')])
                                        file_diffs[file_path] = formatted_diff
                                    except Exception as e:
                                        print(f"Warning: Could not get content for modified file {file_path}: {str(e)}")
                                        # Try to get the raw file content directly from the API
                                        try:
                                            import base64
                                            raw_file = project.repository_files.get(file_path=file_path, ref=commit.id)
                                            if raw_file and hasattr(raw_file, 'content'):
                                                # Decode base64 content if available
                                                try:
                                                    decoded_content = base64.b64decode(raw_file.content).decode('utf-8', errors='replace')
                                                    formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- a/{old_path}\n+++ b/{file_path}\n"
                                                    formatted_diff += "\n".join([f"+{line}" for line in decoded_content.split('\n')])
                                                    file_diffs[file_path] = formatted_diff
                                                except Exception as decode_err:
                                                    print(f"Warning: Could not decode content for {file_path}: {str(decode_err)}")
                                                    # Enhance the diff format with what we have
                                                    formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- a/{old_path}\n+++ b/{file_path}\n{diff_content}"
                                                    file_diffs[file_path] = formatted_diff
                                            else:
                                                # Enhance the diff format with what we have
                                                formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- a/{old_path}\n+++ b/{file_path}\n{diff_content}"
                                                file_diffs[file_path] = formatted_diff
                                        except Exception as api_err:
                                            print(f"Warning: Could not get raw file content for {file_path}: {str(api_err)}")
                                            # Enhance the diff format with what we have
                                            formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- a/{old_path}\n+++ b/{file_path}\n{diff_content}"
                                            file_diffs[file_path] = formatted_diff
                                else:
                                    # Enhance the diff format
                                    formatted_diff = f"diff --git a/{old_path} b/{file_path}\n--- a/{old_path}\n+++ b/{file_path}\n{diff_content}"
                                    file_diffs[file_path] = formatted_diff
                        except Exception as e:
                            print(f"Warning: Error processing diff for {file_path}: {str(e)}")
                            file_diffs[file_path] = diff_content

                    # Skip if no valid diffs
                    if not file_diffs:
                        continue

                    # Create CommitInfo object with enhanced diff content
                    commit_info = CommitInfo(
                        hash=commit.id,
                        author=commit.author_name,
                        date=datetime.strptime(commit.created_at, "%Y-%m-%dT%H:%M:%S.%f%z"),
                        message=commit.message,
                        files=list(file_diffs.keys()),
                        diff="\n\n".join(file_diffs.values()),
                        added_lines=sum(diff.count('\n+') for diff in file_diffs.values()),
                        deleted_lines=sum(diff.count('\n-') for diff in file_diffs.values()),
                        effective_lines=sum(diff.count('\n+') - diff.count('\n-') for diff in file_diffs.values())
                    )
                    commits.append(commit_info)

                    # Store file diffs for this commit
                    commit_file_diffs[commit.id] = file_diffs

            # Calculate code stats
            code_stats = {
                "total_added_lines": sum(commit.added_lines for commit in commits),
                "total_deleted_lines": sum(commit.deleted_lines for commit in commits),
                "total_effective_lines": sum(commit.effective_lines for commit in commits),
                "total_files": len(set(file for commit in commits for file in commit.files))
            }

            return commits, commit_file_diffs, code_stats

        except Exception as e:
            error_msg = f"Failed to retrieve GitLab commits: {str(e)}"
            print(error_msg)
            return [], {}, {}

    else:
        error_msg = f"Unsupported platform: {platform}. Use 'github' or 'gitlab'."
        print(error_msg)
        return [], {}, {}


async def evaluate_developer_code(
    author: str,
    start_date: str,
    end_date: str,
    repo_path: Optional[str] = None,
    include_extensions: Optional[List[str]] = None,
    exclude_extensions: Optional[List[str]] = None,
    model_name: str = "gpt-3.5",
    output_file: Optional[str] = None,
    email_addresses: Optional[List[str]] = None,
    platform: str = "local",
    gitlab_url: Optional[str] = None,
):
    """Evaluate a developer's code commits in a time period."""
    # Generate default output file name if not provided
    if not output_file:
        author_slug = author.replace("@", "_at_").replace(" ", "_").replace("/", "_")
        date_slug = datetime.now().strftime("%Y%m%d")
        output_file = f"codedog_eval_{author_slug}_{date_slug}.md"

    # Get model
    model = load_model_by_name(model_name)

    print(f"Evaluating {author}'s code commits from {start_date} to {end_date}...")

    # Get commits and diffs based on platform
    if platform.lower() == "local":
        # Use local git repository
        commits, commit_file_diffs, code_stats = get_file_diffs_by_timeframe(
            author,
            start_date,
            end_date,
            repo_path,
            include_extensions,
            exclude_extensions
        )
    else:
        # Use remote repository (GitHub or GitLab)
        if not repo_path:
            print("Repository path/name is required for remote platforms")
            return

        commits, commit_file_diffs, code_stats = get_remote_commits(
            platform,
            repo_path,
            author,
            start_date,
            end_date,
            include_extensions,
            exclude_extensions,
            gitlab_url
        )

    if not commits:
        print(f"No commits found for {author} in the specified time period")
        return

    print(f"Found {len(commits)} commits with {sum(len(diffs) for diffs in commit_file_diffs.values())} modified files")

    # Initialize evaluator
    evaluator = DiffEvaluator(model)

    # Timing and statistics
    start_time = time.time()

    with get_openai_callback() as cb:
        # Perform evaluation
        print("Evaluating code commits...")
        evaluation_results = await evaluator.evaluate_commits(commits, commit_file_diffs)

        # Generate Markdown report
        report = generate_evaluation_markdown(evaluation_results)

        # Calculate cost and tokens
        total_cost = cb.total_cost
        total_tokens = cb.total_tokens

    # Add evaluation statistics
    elapsed_time = time.time() - start_time
    telemetry_info = (
        f"\n## Evaluation Statistics\n\n"
        f"- **Evaluation Model**: {model_name}\n"
        f"- **Evaluation Time**: {elapsed_time:.2f} seconds\n"
        f"- **Tokens Used**: {total_tokens}\n"
        f"- **Cost**: ${total_cost:.4f}\n"
        f"\n## Code Statistics\n\n"
        f"- **Total Files Modified**: {code_stats.get('total_files', 0)}\n"
        f"- **Lines Added**: {code_stats.get('total_added_lines', 0)}\n"
        f"- **Lines Deleted**: {code_stats.get('total_deleted_lines', 0)}\n"
        f"- **Effective Lines**: {code_stats.get('total_effective_lines', 0)}\n"
    )

    report += telemetry_info

    # Save report
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {output_file}")

    # Send email report if addresses provided
    if email_addresses:
        subject = f"[CodeDog] Code Evaluation Report for {author} ({start_date} to {end_date})"

        sent = send_report_email(
            to_emails=email_addresses,
            subject=subject,
            markdown_content=report,
        )

        if sent:
            print(f"Report sent to {', '.join(email_addresses)}")
        else:
            print("Failed to send email notification")

    return report


def generate_full_report(repository_name, pull_request_number, email_addresses=None, platform="github", gitlab_url=None):
    """Generate a full report including PR summary and code review.

    Args:
        repository_name (str): Repository path (e.g. owner/repo)
        pull_request_number (int): Pull request number to review
        email_addresses (list, optional): List of email addresses to send the report to
        platform (str, optional): Platform to use (github or gitlab). Defaults to "github".
        gitlab_url (str, optional): GitLab URL. Defaults to https://gitlab.com or GITLAB_URL env var.
    """
    start_time = time.time()

    # Initialize client and retriever based on platform
    if platform.lower() == "github":
        # Initialize GitHub client and retriever
        github_client = Github()  # Will automatically load GITHUB_TOKEN from environment
        print(f"Analyzing GitHub repository {repository_name} PR #{pull_request_number}")

        try:
            retriever = GithubRetriever(github_client, repository_name, pull_request_number)
            print(f"Successfully retrieved PR: {retriever.pull_request.title}")
        except Exception as e:
            error_msg = f"Failed to retrieve GitHub PR: {str(e)}"
            print(error_msg)
            return error_msg

    elif platform.lower() == "gitlab":
        # Initialize GitLab client and retriever
        gitlab_token = os.environ.get("GITLAB_TOKEN", "")
        if not gitlab_token:
            error_msg = "GITLAB_TOKEN environment variable is not set"
            print(error_msg)
            return error_msg

        # Use provided GitLab URL or fall back to environment variable or default
        gitlab_url = gitlab_url or os.environ.get("GITLAB_URL", "https://gitlab.com")

        gitlab_client = Gitlab(url=gitlab_url, private_token=gitlab_token)
        print(f"Analyzing GitLab repository {repository_name} MR #{pull_request_number}")

        try:
            retriever = GitlabRetriever(gitlab_client, repository_name, pull_request_number)
            print(f"Successfully retrieved MR: {retriever.pull_request.title}")
        except Exception as e:
            error_msg = f"Failed to retrieve GitLab MR: {str(e)}"
            print(error_msg)
            return error_msg

    else:
        error_msg = f"Unsupported platform: {platform}. Use 'github' or 'gitlab'."
        print(error_msg)
        return error_msg

    # Load models based on environment variables
    code_summary_model = os.environ.get("CODE_SUMMARY_MODEL", "gpt-3.5")
    pr_summary_model = os.environ.get("PR_SUMMARY_MODEL", "gpt-4")
    code_review_model = os.environ.get("CODE_REVIEW_MODEL", "gpt-3.5")

    # Initialize chains with specified models
    summary_chain = PRSummaryChain.from_llm(
        code_summary_llm=load_model_by_name(code_summary_model),
        pr_summary_llm=load_model_by_name(pr_summary_model),
        verbose=True
    )

    review_chain = CodeReviewChain.from_llm(
        llm=load_model_by_name(code_review_model),
        verbose=True
    )

    with get_openai_callback() as cb:
        # Get PR summary
        print(f"Generating PR summary using {pr_summary_model}...")
        pr_summary_result = asyncio.run(pr_summary(retriever, summary_chain))
        pr_summary_cost = cb.total_cost
        print(f"PR summary complete, cost: ${pr_summary_cost:.4f}")

        # Get code review
        print(f"Generating code review using {code_review_model}...")
        try:
            code_review_result = asyncio.run(code_review(retriever, review_chain))
            code_review_cost = cb.total_cost - pr_summary_cost
            print(f"Code review complete, cost: ${code_review_cost:.4f}")
        except Exception as e:
            print(f"Code review generation failed: {str(e)}")
            print(traceback.format_exc())
            # Use empty code review
            code_review_result = {"code_reviews": []}

        # Create report
        total_cost = cb.total_cost
        total_time = time.time() - start_time

        reporter = PullRequestReporter(
            pr_summary=pr_summary_result["pr_summary"],
            code_summaries=pr_summary_result["code_summaries"],
            pull_request=retriever.pull_request,
            code_reviews=code_review_result.get("code_reviews", []),
            telemetry={
                "start_time": start_time,
                "time_usage": total_time,
                "cost": total_cost,
                "tokens": cb.total_tokens,
            },
        )

        report = reporter.report()

        # Save report to file
        report_file = f"codedog_pr_{pull_request_number}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to {report_file}")

        # Send email notification if email addresses provided
        if email_addresses:
            subject = f"[CodeDog] Code Review for {repository_name} PR #{pull_request_number}: {retriever.pull_request.title}"
            sent = send_report_email(
                to_emails=email_addresses,
                subject=subject,
                markdown_content=report,
            )
            if sent:
                print(f"Report sent to {', '.join(email_addresses)}")
            else:
                print("Failed to send email notification")

        return report


async def review_commit(
    commit_hash: str,
    repo_path: Optional[str] = None,
    include_extensions: Optional[List[str]] = None,
    exclude_extensions: Optional[List[str]] = None,
    model_name: str = "gpt-3.5",
    output_file: Optional[str] = None,
    email_addresses: Optional[List[str]] = None,
    platform: str = "local",
    gitlab_url: Optional[str] = None,
):
    """Review a specific commit.

    Args:
        commit_hash: The hash of the commit to review
        repo_path: Git repository path or name (e.g. owner/repo for remote repositories)
        include_extensions: List of file extensions to include (e.g. ['.py', '.js'])
        exclude_extensions: List of file extensions to exclude (e.g. ['.md', '.txt'])
        model_name: Name of the model to use for review
        output_file: Path to save the report to
        email_addresses: List of email addresses to send the report to
        platform: Platform to use (github, gitlab, or local)
        gitlab_url: GitLab URL (for GitLab platform only)
    """
    # Generate default output file name if not provided
    if not output_file:
        date_slug = datetime.now().strftime("%Y%m%d")
        output_file = f"codedog_commit_{commit_hash[:8]}_{date_slug}.md"

    # Get model
    model = load_model_by_name(model_name)

    print(f"Reviewing commit {commit_hash}...")

    # Get commit diff based on platform
    commit_diff = {}

    if platform.lower() == "local":
        # Use local git repository
        try:
            commit_diff = get_commit_diff(commit_hash, repo_path, include_extensions, exclude_extensions)
        except Exception as e:
            print(f"Error getting commit diff: {str(e)}")
            return
    elif platform.lower() in ["github", "gitlab"]:
        # Use remote repository
        if not repo_path or "/" not in repo_path:
            print(f"Error: Repository name must be in the format 'owner/repo' for {platform} platform")
            return

        commit_diff = get_remote_commit_diff(
            platform=platform,
            repository_name=repo_path,
            commit_hash=commit_hash,
            include_extensions=include_extensions,
            exclude_extensions=exclude_extensions,
            gitlab_url=gitlab_url,
        )
    else:
        print(f"Error: Unsupported platform '{platform}'. Use 'local', 'github', or 'gitlab'.")
        return

    if not commit_diff:
        print(f"No changes found in commit {commit_hash}")
        return

    print(f"Found {len(commit_diff)} modified files")

    # Initialize evaluator
    evaluator = DiffEvaluator(model)

    # Timing and statistics
    start_time = time.time()

    with get_openai_callback() as cb:
        # Perform review
        print("Reviewing code changes...")
        review_results = await evaluator.evaluate_commit(commit_hash, commit_diff)

        # Generate Markdown report
        report = generate_evaluation_markdown(review_results)

        # Calculate cost and tokens
        total_cost = cb.total_cost
        total_tokens = cb.total_tokens

    # Add review statistics
    elapsed_time = time.time() - start_time
    telemetry_info = (
        f"\n## Review Statistics\n\n"
        f"- **Review Model**: {model_name}\n"
        f"- **Review Time**: {elapsed_time:.2f} seconds\n"
        f"- **Tokens Used**: {total_tokens}\n"
        f"- **Cost**: ${total_cost:.4f}\n"
        f"\n## Code Statistics\n\n"
        f"- **Total Files Modified**: {len(commit_diff)}\n"
        f"- **Lines Added**: {sum(diff.get('additions', 0) for diff in commit_diff.values())}\n"
        f"- **Lines Deleted**: {sum(diff.get('deletions', 0) for diff in commit_diff.values())}\n"
    )

    report += telemetry_info

    # Save report
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {output_file}")

    # Send email report if addresses provided
    if email_addresses:
        subject = f"[CodeDog] Code Review for Commit {commit_hash[:8]}"

        sent = send_report_email(
            to_emails=email_addresses,
            subject=subject,
            markdown_content=report,
        )

        if sent:
            print(f"Report sent to {', '.join(email_addresses)}")
        else:
            print("Failed to send email notification")

    return report


def main():
    """Main function to parse arguments and run the appropriate command."""
    args = parse_args()

    if args.command == "pr":
        # Review a GitHub or GitLab pull request
        email_addresses = parse_emails(args.email or os.environ.get("NOTIFICATION_EMAILS", ""))
        report = generate_full_report(
            repository_name=args.repository,
            pull_request_number=args.pr_number,
            email_addresses=email_addresses,
            platform=args.platform,
            gitlab_url=args.gitlab_url
        )

        print("\n===================== Review Report =====================\n")
        print(report)
        print("\n===================== Report End =====================\n")

    elif args.command == "setup-hooks":
        # Set up git hooks for commit-triggered reviews
        repo_path = args.repo or os.getcwd()
        success = install_git_hooks(repo_path)
        if success:
            print("Git hooks successfully installed.")
            print("CodeDog will now automatically review new commits.")

            # Check if notification emails are configured
            emails = os.environ.get("NOTIFICATION_EMAILS", "")
            if emails:
                print(f"Notification emails configured: {emails}")
            else:
                print("No notification emails configured. Add NOTIFICATION_EMAILS to your .env file to receive email reports.")
        else:
            print("Failed to install git hooks.")

    elif args.command == "eval":
        # Evaluate developer's code commits
        # Process date parameters
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        start_date = args.start_date or week_ago
        end_date = args.end_date or today

        # Process file extension parameters
        include_extensions = None
        if args.include:
            include_extensions = parse_extensions(args.include)
        elif os.environ.get("DEV_EVAL_DEFAULT_INCLUDE"):
            include_extensions = parse_extensions(os.environ.get("DEV_EVAL_DEFAULT_INCLUDE"))

        exclude_extensions = None
        if args.exclude:
            exclude_extensions = parse_extensions(args.exclude)
        elif os.environ.get("DEV_EVAL_DEFAULT_EXCLUDE"):
            exclude_extensions = parse_extensions(os.environ.get("DEV_EVAL_DEFAULT_EXCLUDE"))

        # Get model
        model_name = args.model or os.environ.get("CODE_REVIEW_MODEL", "gpt-3.5")

        # Get email addresses
        email_addresses = parse_emails(args.email or os.environ.get("NOTIFICATION_EMAILS", ""))

        # Run evaluation
        report = asyncio.run(evaluate_developer_code(
            author=args.author,
            start_date=start_date,
            end_date=end_date,
            repo_path=args.repo,
            include_extensions=include_extensions,
            exclude_extensions=exclude_extensions,
            model_name=model_name,
            output_file=args.output,
            email_addresses=email_addresses,
            platform=args.platform,
            gitlab_url=args.gitlab_url,
        ))

        if report:
            print("\n===================== Evaluation Report =====================\n")
            print("Report generated successfully. See output file for details.")
            print("\n===================== Report End =====================\n")

    elif args.command == "commit":
        # Process file extension parameters
        include_extensions = None
        if args.include:
            include_extensions = parse_extensions(args.include)
        elif os.environ.get("DEV_EVAL_DEFAULT_INCLUDE"):
            include_extensions = parse_extensions(os.environ.get("DEV_EVAL_DEFAULT_INCLUDE"))

        exclude_extensions = None
        if args.exclude:
            exclude_extensions = parse_extensions(args.exclude)
        elif os.environ.get("DEV_EVAL_DEFAULT_EXCLUDE"):
            exclude_extensions = parse_extensions(os.environ.get("DEV_EVAL_DEFAULT_EXCLUDE"))

        # Get model
        model_name = args.model or os.environ.get("CODE_REVIEW_MODEL", "gpt-3.5")

        # Get email addresses
        email_addresses = parse_emails(args.email or os.environ.get("NOTIFICATION_EMAILS", ""))

        # Run commit review
        report = asyncio.run(review_commit(
            commit_hash=args.commit_hash,
            repo_path=args.repo,
            include_extensions=include_extensions,
            exclude_extensions=exclude_extensions,
            model_name=model_name,
            output_file=args.output,
            email_addresses=email_addresses,
            platform=args.platform,
            gitlab_url=args.gitlab_url,
        ))

        if report:
            print("\n===================== Commit Review Report =====================\n")
            print("Report generated successfully. See output file for details.")
            print("\n===================== Report End =====================\n")

    else:
        # No command specified, show usage
        print("Please specify a command. Use --help for more information.")
        print("Example: python run_codedog.py pr owner/repo 123                      # GitHub PR review")
        print("Example: python run_codedog.py pr owner/repo 123 --platform gitlab    # GitLab MR review")
        print("Example: python run_codedog.py setup-hooks                           # Set up git hooks")
        print("Example: python run_codedog.py eval username --start-date 2023-01-01 --end-date 2023-01-31  # Evaluate code")
        print("Example: python run_codedog.py commit abc123def                      # Review local commit")
        print("Example: python run_codedog.py commit abc123def --repo owner/repo --platform github  # Review GitHub commit")
        print("Example: python run_codedog.py commit abc123def --repo owner/repo --platform gitlab  # Review GitLab commit")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nDetailed error information:")
        traceback.print_exc()