import os
import subprocess
import sys
from datetime import datetime

def get_latest_commit_hash():
    """Get the hash of the latest commit."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error getting latest commit: {e}")
        sys.exit(1)

def get_commit_info(commit_hash):
    """Get detailed information about a commit."""
    try:
        result = subprocess.run(
            ["git", "show", "-s", "--format=%an <%ae>%n%cd%n%s%n%b", commit_hash],
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.strip().split('\n')
        author = lines[0]
        date = lines[1]
        subject = lines[2]
        body = '\n'.join(lines[3:]) if len(lines) > 3 else ""
        
        return {
            "author": author,
            "date": date,
            "subject": subject,
            "body": body
        }
    except subprocess.CalledProcessError as e:
        print(f"Error getting commit info: {e}")
        sys.exit(1)

def get_changed_files(commit_hash):
    """Get list of files changed in the commit."""
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip().split('\n')
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed files: {e}")
        sys.exit(1)

def get_file_diff(commit_hash, file_path):
    """Get diff for a specific file in the commit."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{commit_hash}^..{commit_hash}", "--", file_path],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting file diff: {e}")
        return "Error: Unable to get diff"

def generate_report(commit_hash):
    """Generate a simple report for the commit."""
    commit_info = get_commit_info(commit_hash)
    changed_files = get_changed_files(commit_hash)
    
    report = f"""# Commit Review - {commit_hash[:8]}

## Commit Information
- **Author:** {commit_info['author']}
- **Date:** {commit_info['date']}
- **Subject:** {commit_info['subject']}

## Commit Message
{commit_info['body']}

## Changed Files
{len(changed_files)} files were changed in this commit:

"""
    
    for file in changed_files:
        if file:  # Skip empty entries
            report += f"- {file}\n"
    
    report += "\n## File Changes\n"
    
    for file in changed_files:
        if not file:  # Skip empty entries
            continue
            
        report += f"\n### {file}\n"
        report += "```diff\n"
        report += get_file_diff(commit_hash, file)
        report += "\n```\n"
    
    return report

def main():
    print("Generating report for the latest commit...")
    
    commit_hash = get_latest_commit_hash()
    report = generate_report(commit_hash)
    
    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"commit_review_{timestamp}.md"
    
    with open(report_file, "w") as f:
        f.write(report)
    
    print(f"Report saved to {report_file}")
    
    # Print summary to console
    commit_info = get_commit_info(commit_hash)
    changed_files = get_changed_files(commit_hash)
    
    print("\n==== Commit Summary ====")
    print(f"Commit: {commit_hash[:8]}")
    print(f"Author: {commit_info['author']}")
    print(f"Subject: {commit_info['subject']}")
    print(f"Files changed: {len([f for f in changed_files if f])}")
    print(f"Full report in: {report_file}")

if __name__ == "__main__":
    main() 