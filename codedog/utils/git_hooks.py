import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def install_git_hooks(repo_path: str) -> bool:
    """Install git hooks to trigger code reviews on commits.

    Args:
        repo_path: Path to the git repository

    Returns:
        bool: True if hooks were installed successfully, False otherwise
    """
    hooks_dir = os.path.join(repo_path, ".git", "hooks")

    if not os.path.exists(hooks_dir):
        print(f"Git hooks directory not found: {hooks_dir}")
        return False

    # Create post-commit hook
    post_commit_path = os.path.join(hooks_dir, "post-commit")

    # Get the absolute path to the codedog directory
    codedog_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    # Create hook script content
    hook_content = f"""#!/bin/sh
# CodeDog post-commit hook for triggering code reviews

# Get the latest commit hash
COMMIT_HASH=$(git rev-parse HEAD)

# Run the review script with the commit hash
# Enable verbose mode to see progress and set EMAIL_ENABLED=true to ensure emails are sent
export EMAIL_ENABLED=true
python {codedog_path}/run_codedog_commit.py --commit $COMMIT_HASH --verbose
"""

    # Write hook file
    with open(post_commit_path, "w") as f:
        f.write(hook_content)

    # Make hook executable
    os.chmod(post_commit_path, 0o755)

    print(f"Git post-commit hook installed successfully: {post_commit_path}")
    return True


def get_commit_files(commit_hash: str, repo_path: Optional[str] = None) -> List[str]:
    """Get list of files changed in a specific commit.

    Args:
        commit_hash: The commit hash to check
        repo_path: Path to git repository (defaults to current directory)

    Returns:
        List[str]: List of changed file paths
    """
    cwd = repo_path or os.getcwd()

    try:
        # Get list of files changed in the commit
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )

        # Return list of files (filtering empty lines)
        files = [f for f in result.stdout.split("\n") if f.strip()]
        return files

    except subprocess.CalledProcessError as e:
        print(f"Error getting files from commit {commit_hash}: {e}")
        print(f"Error output: {e.stderr}")
        return []


def create_commit_pr_data(commit_hash: str, repo_path: Optional[str] = None) -> dict:
    """Create PR-like data structure from a commit for code review.

    Args:
        commit_hash: The commit hash to check
        repo_path: Path to git repository (defaults to current directory)

    Returns:
        dict: PR-like data structure with commit info and files
    """
    cwd = repo_path or os.getcwd()

    try:
        # Get commit info
        commit_info = subprocess.run(
            ["git", "show", "--pretty=format:%s%n%b", commit_hash],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )

        # Parse commit message
        lines = commit_info.stdout.strip().split("\n")
        title = lines[0] if lines else "Unknown commit"
        body = "\n".join(lines[1:]) if len(lines) > 1 else ""

        # Get author information
        author_info = subprocess.run(
            ["git", "show", "--pretty=format:%an <%ae>", "-s", commit_hash],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
        author = author_info.stdout.strip()

        # Get changed files
        files = get_commit_files(commit_hash, repo_path)

        # Get repository name from path
        repo_name = os.path.basename(os.path.abspath(cwd))

        # Create PR-like structure
        pr_data = {
            "pull_request_id": int(commit_hash[:8], 16),  # Convert first 8 chars of commit hash to integer
            "repository_id": abs(hash(repo_name)) % (10 ** 8),  # Convert repo name to stable integer
            "number": commit_hash[:8],  # Use shortened commit hash as "PR number"
            "title": title,
            "body": body,
            "author": author,
            "commit_hash": commit_hash,
            "files": files,
            "is_commit_review": True,  # Flag to indicate this is a commit review, not a real PR
        }

        return pr_data

    except subprocess.CalledProcessError as e:
        print(f"Error creating PR data from commit {commit_hash}: {e}")
        print(f"Error output: {e.stderr}")
        return {
            "pull_request_id": int(commit_hash[:8], 16),
            "repository_id": abs(hash(repo_name)) % (10 ** 8),
            "number": commit_hash[:8] if commit_hash else "unknown",
            "title": "Error retrieving commit data",
            "body": str(e),
            "author": "Unknown",
            "commit_hash": commit_hash,
            "files": [],
            "is_commit_review": True,
        }