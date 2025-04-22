#!/usr/bin/env python
import argparse
import asyncio
import os
import sys
import time
import traceback
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables from .env file
# This will load GitHub or GitLab tokens from the .env file
load_dotenv()

from langchain_community.callbacks.manager import get_openai_callback

from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.chains import CodeReviewChain, PRSummaryChain
from codedog.models import PullRequest, ChangeFile, ChangeStatus, Repository
from codedog.models.diff import DiffContent
from codedog.processors.pull_request_processor import PullRequestProcessor
from codedog.utils.langchain_utils import load_model_by_name
from codedog.utils.email_utils import send_report_email
from codedog.utils.git_hooks import create_commit_pr_data, get_commit_files
import subprocess


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="CodeDog - Automatic commit code review for GitHub and GitLab repositories")
    parser.add_argument("--commit", help="Commit hash to review (defaults to HEAD)")
    parser.add_argument("--repo", help="Path to git repository (defaults to current directory)")
    parser.add_argument("--email", help="Email addresses to send the report to (comma-separated)")
    parser.add_argument("--output", help="Output file path (defaults to codedog_commit_<hash>.md)")
    parser.add_argument("--model", help="Model to use for code review (defaults to CODE_REVIEW_MODEL env var or gpt-3.5)")
    parser.add_argument("--summary-model", help="Model to use for PR summary (defaults to PR_SUMMARY_MODEL env var or gpt-4)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    return parser.parse_args()


def parse_emails(emails_str: Optional[str]) -> List[str]:
    """Parse comma-separated email addresses."""
    if not emails_str:
        return []

    return [email.strip() for email in emails_str.split(",") if email.strip()]


def get_file_diff(commit_hash: str, file_path: str, repo_path: Optional[str] = None) -> str:
    """Get diff for a specific file in the commit.

    Args:
        commit_hash: The commit hash
        file_path: Path to the file
        repo_path: Path to git repository (defaults to current directory)

    Returns:
        str: The diff content
    """
    cwd = repo_path or os.getcwd()

    try:
        # Get diff for the file
        result = subprocess.run(
            ["git", "diff", f"{commit_hash}^..{commit_hash}", "--", file_path],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )

        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting file diff for {file_path}: {e}")
        return f"Error: Unable to get diff for {file_path}"


def create_change_files(commit_hash: str, repo_path: Optional[str] = None) -> List[ChangeFile]:
    """Create ChangeFile objects for files changed in the commit."""
    cwd = repo_path or os.getcwd()
    repo_name = os.path.basename(os.path.abspath(cwd))

    # Get list of files changed in the commit
    files = get_commit_files(commit_hash, repo_path)

    # Create a unique ID for the commit
    commit_id = int(commit_hash[:8], 16)

    change_files = []
    for file_path in files:
        # Get file name and suffix
        file_name = os.path.basename(file_path)
        suffix = file_path.split('.')[-1] if '.' in file_path else ""

        # Get diff content
        diff_content_str = get_file_diff(commit_hash, file_path, repo_path)

        # Create DiffContent object
        diff_content = DiffContent(
            add_count=diff_content_str.count('\n+') - diff_content_str.count('\n+++'),
            remove_count=diff_content_str.count('\n-') - diff_content_str.count('\n---'),
            content=diff_content_str
        )

        # Create ChangeFile object
        change_file = ChangeFile(
            blob_id=abs(hash(file_path)) % (10 ** 8),  # Generate a stable ID from file path
            sha=commit_hash,
            full_name=file_path,
            source_full_name=file_path,
            status=ChangeStatus.modified,  # Assume modified for simplicity
            pull_request_id=commit_id,
            start_commit_id=int(commit_hash[:8], 16) - 1,  # Previous commit
            end_commit_id=int(commit_hash[:8], 16),  # Current commit
            name=file_name,
            suffix=suffix,
            diff_content=diff_content
        )

        change_files.append(change_file)

    return change_files


def create_pull_request_from_commit(commit_hash: str, repo_path: Optional[str] = None) -> PullRequest:
    """Create a PullRequest object from a commit."""
    # Get commit data in PR-like format
    commit_data = create_commit_pr_data(commit_hash, repo_path)

    # Create change files
    change_files = create_change_files(commit_hash, repo_path)

    # Create repository object
    cwd = repo_path or os.getcwd()
    repo_name = os.path.basename(os.path.abspath(cwd))
    repository = Repository(
        repository_id=abs(hash(repo_name)) % (10 ** 8),
        repository_name=repo_name,
        repository_full_name=repo_name,
        repository_url=cwd
    )

    # Create PullRequest object
    pull_request = PullRequest(
        pull_request_id=commit_data["pull_request_id"],
        repository_id=commit_data["repository_id"],
        pull_request_number=int(commit_hash[:8], 16),
        title=commit_data["title"],
        body=commit_data["body"],
        url="",
        repository_name=repo_name,
        related_issues=[],
        change_files=change_files,
        repository=repository,
        source_repository=repository
    )

    return pull_request


async def pr_summary(pull_request, summary_chain):
    """Generate PR summary asynchronously."""
    result = await summary_chain.ainvoke(
        {"pull_request": pull_request}, include_run_info=True
    )
    return result


async def code_review(pull_request, review_chain):
    """Generate code review asynchronously."""
    result = await review_chain.ainvoke(
        {"pull_request": pull_request}, include_run_info=True
    )
    return result


def generate_commit_review(commit_hash: str, repo_path: Optional[str] = None,
                          email_addresses: Optional[List[str]] = None,
                          output_file: Optional[str] = None,
                          code_review_model: str = None,
                          pr_summary_model: str = None,
                          verbose: bool = False) -> str:
    """Generate a code review for a commit.

    This function works with both GitHub and GitLab repositories by analyzing local Git commits.
    It doesn't require direct API access to GitHub or GitLab as it works with the local repository.

    Args:
        commit_hash: The commit hash to review
        repo_path: Path to git repository (defaults to current directory)
        email_addresses: List of email addresses to send the report to
        output_file: Output file path (defaults to codedog_commit_<hash>.md)
        code_review_model: Model to use for code review
        pr_summary_model: Model to use for PR summary
        verbose: Enable verbose output

    Returns:
        str: The generated review report in markdown format
    """
    start_time = time.time()

    # Set default models from environment variables
    code_review_model = code_review_model or os.environ.get("CODE_REVIEW_MODEL", "gpt-3.5")
    pr_summary_model = pr_summary_model or os.environ.get("PR_SUMMARY_MODEL", "gpt-4")
    code_summary_model = os.environ.get("CODE_SUMMARY_MODEL", "gpt-3.5")

    # Create PullRequest object from commit
    pull_request = create_pull_request_from_commit(commit_hash, repo_path)

    if verbose:
        print(f"Reviewing commit: {commit_hash}")
        print(f"Title: {pull_request.title}")
        print(f"Files changed: {len(pull_request.change_files)}")

    # Initialize chains with specified models
    summary_chain = PRSummaryChain.from_llm(
        code_summary_llm=load_model_by_name(code_summary_model),
        pr_summary_llm=load_model_by_name(pr_summary_model),
        verbose=verbose
    )

    review_chain = CodeReviewChain.from_llm(
        llm=load_model_by_name(code_review_model),
        verbose=verbose
    )

    with get_openai_callback() as cb:
        # Get PR summary
        if verbose:
            print(f"Generating commit summary using {pr_summary_model}...")

        pr_summary_result = asyncio.run(pr_summary(pull_request, summary_chain))
        pr_summary_cost = cb.total_cost

        if verbose:
            print(f"Commit summary complete, cost: ${pr_summary_cost:.4f}")

        # Get code review
        if verbose:
            print(f"Generating code review using {code_review_model}...")

        try:
            code_review_result = asyncio.run(code_review(pull_request, review_chain))
            code_review_cost = cb.total_cost - pr_summary_cost

            if verbose:
                print(f"Code review complete, cost: ${code_review_cost:.4f}")
        except Exception as e:
            print(f"Code review generation failed: {str(e)}")
            if verbose:
                print(traceback.format_exc())
            # Use empty code review
            code_review_result = {"code_reviews": []}

        # Create report
        total_cost = cb.total_cost
        total_time = time.time() - start_time

        reporter = PullRequestReporter(
            pr_summary=pr_summary_result["pr_summary"],
            code_summaries=pr_summary_result["code_summaries"],
            pull_request=pull_request,
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
        if not output_file:
            output_file = f"codedog_commit_{commit_hash[:8]}.md"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)

        if verbose:
            print(f"Report saved to {output_file}")

        # Send email notification if email addresses provided
        if email_addresses:
            subject = f"[CodeDog] Code Review for Commit {commit_hash[:8]}: {pull_request.title}"
            sent = send_report_email(
                to_emails=email_addresses,
                subject=subject,
                markdown_content=report,
            )
            if sent and verbose:
                print(f"Report sent to {', '.join(email_addresses)}")
            elif not sent and verbose:
                print("Failed to send email notification")

        return report


def main():
    """Main function to parse arguments and run the commit review.

    This works with both GitHub and GitLab repositories by analyzing local Git commits.
    """
    args = parse_args()

    # Get commit hash (default to HEAD if not provided)
    commit_hash = args.commit
    if not commit_hash:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()

    # Get email addresses from args, env var, or use the default address
    default_email = "kratosxie@gmail.com"  # Default email address
    email_from_args = args.email or os.environ.get("NOTIFICATION_EMAILS", "")

    # If no email is specified in args or env, use the default
    if not email_from_args:
        email_addresses = [default_email]
        print(f"No email specified, using default: {default_email}")
    else:
        email_addresses = parse_emails(email_from_args)

    # Generate review
    report = generate_commit_review(
        commit_hash=commit_hash,
        repo_path=args.repo,
        email_addresses=email_addresses,
        output_file=args.output,
        code_review_model=args.model,
        pr_summary_model=args.summary_model,
        verbose=args.verbose
    )

    if args.verbose:
        print("\n===================== Review Report =====================\n")
        print(f"Report generated for commit {commit_hash[:8]}")
        if email_addresses:
            print(f"Report sent to: {', '.join(email_addresses)}")
        print("\n===================== Report End =====================\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nDetailed error information:")
        traceback.print_exc()
