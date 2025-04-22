import argparse
import asyncio
import time
import traceback
from dotenv import load_dotenv
from typing import List, Optional
import os
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
from codedog.utils.git_log_analyzer import get_file_diffs_by_timeframe
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
    eval_parser.add_argument("--repo", help="Git repository path, defaults to current directory")
    eval_parser.add_argument("--include", help="Included file extensions, comma separated, e.g. .py,.js")
    eval_parser.add_argument("--exclude", help="Excluded file extensions, comma separated, e.g. .md,.txt")
    eval_parser.add_argument("--model", help="Evaluation model, defaults to CODE_REVIEW_MODEL env var or gpt-3.5")
    eval_parser.add_argument("--email", help="Email addresses to send the report to (comma-separated)")
    eval_parser.add_argument("--output", help="Report output path, defaults to codedog_eval_<author>_<date>.md")

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

    # Get commits and diffs
    commits, commit_file_diffs = get_file_diffs_by_timeframe(
        author,
        start_date,
        end_date,
        repo_path,
        include_extensions,
        exclude_extensions
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
        ))

        if report:
            print("\n===================== Evaluation Report =====================\n")
            print("Report generated successfully. See output file for details.")
            print("\n===================== Report End =====================\n")

    else:
        # No command specified, show usage
        print("Please specify a command. Use --help for more information.")
        print("Example: python run_codedog.py pr owner/repo 123                      # GitHub PR review")
        print("Example: python run_codedog.py pr owner/repo 123 --platform gitlab    # GitLab MR review")
        print("Example: python run_codedog.py setup-hooks                           # Set up git hooks")
        print("Example: python run_codedog.py eval username --start-date 2023-01-01 --end-date 2023-01-31  # Evaluate code")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nDetailed error information:")
        traceback.print_exc()