# Automatic Commit Code Review

CodeDog can automatically review your code commits and send the review results via email. This guide explains how to set up and use this feature.

## Setup

1. **Install Git Hooks**

   Run the following command to set up the git hooks that will trigger automatic code reviews when you make commits:

   ```bash
   python run_codedog.py setup-hooks
   ```

   This will install a post-commit hook in your repository's `.git/hooks` directory.

2. **Configure Email Notifications**

   To receive email notifications with the review results, you need to configure email settings. You have two options:

   a) **Using Environment Variables**:
   
   Add the following to your `.env` file:

   ```
   # Email notification settings
   EMAIL_ENABLED="true"
   NOTIFICATION_EMAILS="your.email@example.com"  # Can be comma-separated for multiple recipients
   
   # SMTP server settings
   SMTP_SERVER="smtp.gmail.com"  # Use your email provider's SMTP server
   SMTP_PORT="587"              # Common port for TLS connections
   SMTP_USERNAME="your.email@gmail.com"  # The email that will send notifications
   SMTP_PASSWORD="your_app_password"    # See Gmail-specific instructions in docs/email_setup.md
   ```

   b) **Default Email**:
   
   If you don't configure any email settings, the system will automatically send review results to `kratosxie@gmail.com`.

3. **Configure LLM Models**

   You can specify which models to use for different parts of the review process:

   ```
   # Model selection (optional)
   CODE_SUMMARY_MODEL="gpt-3.5"
   PR_SUMMARY_MODEL="gpt-4"
   CODE_REVIEW_MODEL="gpt-3.5"
   ```

## How It Works

1. When you make a commit, the post-commit hook automatically runs.
2. The hook executes `run_codedog_commit.py` with your commit hash.
3. The script:
   - Retrieves information about your commit
   - Analyzes the code changes
   - Generates a summary and review
   - Saves the review to a file named `codedog_commit_<commit_hash>.md`
   - Sends the review via email to the configured address(es)

## Manual Execution

You can also manually run the commit review script:

```bash
python run_codedog_commit.py --commit <commit-hash> --verbose
```

### Command-line Options

- `--commit`: Specify the commit hash to review (defaults to HEAD)
- `--repo`: Path to git repository (defaults to current directory)
- `--email`: Email addresses to send the report to (comma-separated)
- `--output`: Output file path (defaults to codedog_commit_<hash>.md)
- `--model`: Model to use for code review
- `--summary-model`: Model to use for PR summary
- `--verbose`: Enable verbose output

## Troubleshooting

If you're not receiving email notifications:

1. Check that `EMAIL_ENABLED` is set to "true" in your `.env` file
2. Verify your SMTP settings (see [Email Setup Guide](email_setup.md))
3. Make sure your email provider allows sending emails via SMTP
4. Check your spam/junk folder

If the review isn't running automatically:

1. Verify that the git hook was installed correctly:
   ```bash
   cat .git/hooks/post-commit
   ```
2. Make sure the hook is executable:
   ```bash
   chmod +x .git/hooks/post-commit
   ```
3. Try running the script manually to see if there are any errors

## Example Output

The review report includes:

- A summary of the commit
- Analysis of the code changes
- Suggestions for improvements
- Potential issues or bugs
- Code quality feedback

The report is formatted in Markdown and sent as both plain text and HTML in the email.
