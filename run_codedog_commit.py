#!/usr/bin/env python3
import argparse
import asyncio
import os
import sys
import time
import traceback
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.chains import CodeReviewChain, PRSummaryChain
from codedog.models.pull_request import PullRequest
from codedog.utils.git_hooks import create_commit_pr_data
from codedog.utils.email_utils import send_report_email
from codedog.utils.langchain_utils import load_model_by_name
from langchain_community.callbacks.manager import get_openai_callback


class CommitReviewer:
    """Class to handle commit-triggered code reviews."""
    
    def __init__(self, commit_hash: str, repo_path: Optional[str] = None):
        """Initialize the commit reviewer.
        
        Args:
            commit_hash: The commit hash to review
            repo_path: Path to the git repository (defaults to current directory)
        """
        self.commit_hash = commit_hash
        self.repo_path = repo_path or os.getcwd()
        
        # Get models from environment variables
        self.code_summary_model = os.environ.get("CODE_SUMMARY_MODEL", "gpt-3.5")
        self.pr_summary_model = os.environ.get("PR_SUMMARY_MODEL", "gpt-4")
        self.code_review_model = os.environ.get("CODE_REVIEW_MODEL", "gpt-3.5")
        
        # Get notification settings
        self.notification_emails = self._parse_emails(os.environ.get("NOTIFICATION_EMAILS", ""))
        
        # Create PR data from commit
        print(f"Processing commit: {commit_hash}")
        self.pr_data = create_commit_pr_data(commit_hash, repo_path)
        
        # Initialize chains with models
        self.summary_chain = PRSummaryChain.from_llm(
            code_summary_llm=load_model_by_name(self.code_summary_model),
            pr_summary_llm=load_model_by_name(self.pr_summary_model),
            verbose=True
        )
        
        self.review_chain = CodeReviewChain.from_llm(
            llm=load_model_by_name(self.code_review_model),
            verbose=True
        )
    
    def _parse_emails(self, emails_str: str) -> List[str]:
        """Parse comma-separated email addresses.
        
        Args:
            emails_str: Comma-separated email addresses
            
        Returns:
            List[str]: List of email addresses
        """
        return [email.strip() for email in emails_str.split(",") if email.strip()]
    
    async def generate_pr_summary(self):
        """Generate PR summary for the commit.
        
        Returns:
            dict: PR summary results
        """
        print(f"Generating summary for commit {self.commit_hash[:8]}...")
        
        # Create a PullRequest object from the PR data
        pull_request = PullRequest(
            number=self.pr_data["number"],
            title=self.pr_data["title"],
            body=self.pr_data["body"],
            author=self.pr_data["author"],
            files=self.pr_data["files"],
            # Add additional fields as needed by your PullRequest model
        )
        
        result = await self.summary_chain.ainvoke(
            {"pull_request": pull_request}, include_run_info=True
        )
        return result
    
    async def generate_code_review(self, pull_request):
        """Generate code review for the commit.
        
        Args:
            pull_request: PullRequest object
            
        Returns:
            dict: Code review results
        """
        print(f"Generating code review for commit {self.commit_hash[:8]}...")
        
        result = await self.review_chain.ainvoke(
            {"pull_request": pull_request}, include_run_info=True
        )
        return result
    
    def generate_full_report(self):
        """Generate a full report including summary and code review.
        
        Returns:
            str: Markdown report
        """
        start_time = time.time()
        
        with get_openai_callback() as cb:
            try:
                # Get PR summary
                print("Generating PR summary...")
                pr_summary_result = asyncio.run(self.generate_pr_summary())
                pr_summary_cost = cb.total_cost
                print(f"PR summary complete, cost: ${pr_summary_cost:.4f}")
                
                # Get code review
                print("Generating code review...")
                try:
                    code_review_result = asyncio.run(self.generate_code_review(pr_summary_result["pull_request"]))
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
                    pull_request=pr_summary_result["pull_request"],
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
                report_file = f"codedog_commit_{self.commit_hash[:8]}.md"
                with open(report_file, "w", encoding="utf-8") as f:
                    f.write(report)
                print(f"Report saved to {report_file}")
                
                # Send email notification if enabled
                if self.notification_emails:
                    subject = f"[CodeDog] Code Review for Commit {self.commit_hash[:8]}: {self.pr_data['title']}"
                    sent = send_report_email(
                        to_emails=self.notification_emails,
                        subject=subject,
                        markdown_content=report,
                    )
                    if sent:
                        print(f"Report sent to {', '.join(self.notification_emails)}")
                    else:
                        print("Failed to send email notification")
                
                return report
                
            except Exception as e:
                error_msg = f"Error generating report: {str(e)}\n{traceback.format_exc()}"
                print(error_msg)
                return error_msg


def main():
    """Main function to parse arguments and run the commit reviewer."""
    parser = argparse.ArgumentParser(description="CodeDog Commit Review - Analyze git commits with AI")
    parser.add_argument("--commit", required=True, help="Commit hash to review")
    parser.add_argument("--repo", help="Path to git repository (defaults to current directory)")
    
    args = parser.parse_args()
    
    reviewer = CommitReviewer(args.commit, args.repo)
    report = reviewer.generate_full_report()
    
    print("\n==================== Review Report ====================\n")
    print(report)
    print("\n==================== Report End ====================\n")


if __name__ == "__main__":
    main() 