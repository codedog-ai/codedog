# Codedog: AI-Powered Code Review Assistant

[![Python Version](https://img.shields.io/pypi/pyversions/codedog)](https://pypi.org/project/codedog/)
[![PyPI Version](https://img.shields.io/pypi/v/codedog.svg)](https://pypi.org/project/codedog/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Codedog leverages Large Language Models (LLMs) like GPT to automatically review your pull requests on platforms like GitHub and GitLab, providing summaries and potential suggestions.

## Features

*   **Pull Request Summarization**: Generates concise summaries of PR changes, including categorization (feature, fix, etc.) and identification of major files.
*   **Code Change Summarization**: Summarizes individual file diffs.
*   **Code Review Suggestions**: Provides feedback and suggestions on code changes (experimental).
*   **Multi-language Support**: Includes templates for English and Chinese reports.
*   **Platform Support**: Works with GitHub and GitLab.
*   **Automated Code Review**: Uses LLMs to analyze code changes, provide feedback, and suggest improvements
*   **Scoring System**: Evaluates code across multiple dimensions, including correctness, readability, and maintainability
*   **Multiple LLM Support**: Works with OpenAI (including GPT-4o), Azure OpenAI, DeepSeek, and DeepSeek R1 models (see [Models Guide](docs/models.md))
*   **Email Notifications**: Sends code review reports via email (see [Email Setup Guide](docs/email_setup.md))
*   **Commit-Triggered Reviews**: Automatically reviews code when commits are made (see [Commit Review Guide](docs/commit_review.md))
*   **Developer Evaluation**: Evaluates a developer's code over a specific time period

## Prerequisites

*   **Python**: Version 3.10 or higher (as the project now requires `^3.10`).
*   **Poetry**: A dependency management tool for Python. Installation instructions: [Poetry Docs](https://python-poetry.org/docs/#installation).
*   **Git**: For interacting with repositories.
*   **(Optional) Homebrew**: For easier installation of Python versions on macOS.
*   **API Keys**:
    *   OpenAI API Key (or Azure OpenAI credentials).
    *   GitHub Personal Access Token (with `repo` scope) or GitLab Personal Access Token (with `api` scope).

## Setup

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/codedog-ai/codedog.git # Or your fork
    cd codedog
    ```

2.  **Configure Python Version (if needed)**:
    The project requires Python `^3.10` (3.10 or higher, but less than 4.0).
    *   If your default Python doesn't meet this, install a compatible version (e.g., using Homebrew `brew install python@3.12`, pyenv, etc.).
    *   Tell Poetry to use the correct Python executable (replace path if necessary):
        ```bash
        poetry env use /opt/homebrew/bin/python3.12 # Example for Homebrew on Apple Silicon
        # or
        poetry env use /path/to/your/python3.10+
        ```

3.  **Install Dependencies**:
    Poetry will create a virtual environment and install all necessary packages defined in `pyproject.toml` and `poetry.lock`.
    ```bash
    poetry install --with test,dev # Include optional dev and test dependencies
    ```
    *(Note: If you encounter issues connecting to package sources, ensure you have internet access. The configuration previously used a mirror but has been reverted to the default PyPI.)*

## Configuration

Codedog uses environment variables for configuration. You can set these directly in your shell, or use a `.env` file (you might need to install `python-dotenv` separately in your environment: `poetry run pip install python-dotenv`).

**Required:**

*   **Platform Token**:
    *   For GitHub: `GITHUB_TOKEN="your_github_personal_access_token"`
    *   For GitLab: `GITLAB_TOKEN="your_gitlab_personal_access_token"`
    *   For GitLab (if using a self-hosted instance): `GITLAB_URL="https://your.gitlab.instance.com"`

*   **LLM Credentials**:
    *   **OpenAI**: `OPENAI_API_KEY="sk-your_openai_api_key"`
    *   **Azure OpenAI**: Set `AZURE_OPENAI="true"` (or any non-empty string) **and** provide:
        *   `AZURE_OPENAI_API_KEY="your_azure_api_key"`
        *   `AZURE_OPENAI_API_BASE="https://your_azure_endpoint.openai.azure.com/"`
        *   `AZURE_OPENAI_DEPLOYMENT_ID="your_gpt_35_turbo_deployment_name"` (Used for code summaries/reviews)
        *   `AZURE_OPENAI_GPT4_DEPLOYMENT_ID="your_gpt_4_deployment_name"` (Used for PR summary)
        *   *(Optional)* `AZURE_OPENAI_API_VERSION="YYYY-MM-DD"` (Defaults to a recent preview version if not set)
    *   **DeepSeek Models**: Set the following for DeepSeek models:
        *   `DEEPSEEK_API_KEY="your_deepseek_api_key"`
        *   *(Optional)* `DEEPSEEK_MODEL="deepseek-chat"` (Default model, options include: "deepseek-chat", "deepseek-coder", etc.)
        *   *(Optional)* `DEEPSEEK_API_BASE="https://api.deepseek.com"` (Default API endpoint)
        *   For **DeepSeek R1 model** specifically:
            *   Set `DEEPSEEK_MODEL="deepseek-r1"`
            *   *(Optional)* `DEEPSEEK_R1_API_BASE="https://your-r1-endpoint"` (If different from standard DeepSeek endpoint)

**Example `.env` file:**

```dotenv
# Platform
GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# LLM (OpenAI example)
OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# LLM (Azure OpenAI example)
# AZURE_OPENAI="true"
# AZURE_OPENAI_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
# AZURE_OPENAI_API_BASE="https://your-instance.openai.azure.com/"
# AZURE_OPENAI_DEPLOYMENT_ID="gpt-35-turbo-16k"
# AZURE_OPENAI_GPT4_DEPLOYMENT_ID="gpt-4-turbo"

# LLM (DeepSeek example)
# DEEPSEEK_API_KEY="your_deepseek_api_key"
# DEEPSEEK_MODEL="deepseek-chat"
# DEEPSEEK_API_BASE="https://api.deepseek.com"

# LLM (DeepSeek R1 example)
# DEEPSEEK_API_KEY="your_deepseek_api_key"
# DEEPSEEK_MODEL="deepseek-r1"
# DEEPSEEK_R1_API_BASE="https://your-r1-endpoint"

# Model selection (optional)
CODE_SUMMARY_MODEL="gpt-3.5"
PR_SUMMARY_MODEL="gpt-4"
CODE_REVIEW_MODEL="deepseek"  # Can use "deepseek" or "deepseek-r1" here

# Email notification (optional)
EMAIL_ENABLED="true"
NOTIFICATION_EMAILS="your_email@example.com,another_email@example.com"
SMTP_SERVER="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USERNAME="your_email@gmail.com"
SMTP_PASSWORD="your_app_password"  # For Gmail, you must use an App Password, see docs/email_setup.md
```

## Running the Example (Quickstart)

The `README.md` in the project root (and `codedog/__init__.py`) contains a quickstart Python script demonstrating the core workflow.

1.  **Save the Quickstart Code**: Copy the Python code from the quickstart section into a file, e.g., `run_codedog.py`.

2.  **Update Placeholders**: Modify the script with:
    *   Your actual GitHub/GitLab token.
    *   Your OpenAI/Azure API key and relevant details.
    *   The target repository (e.g., `"codedog-ai/codedog"` or your fork/project).
    *   The target Pull Request / Merge Request number/iid.

3.  **Load Environment Variables**: If using a `.env` file, ensure it's loaded. You might need to add `from dotenv import load_dotenv; load_dotenv()` at the beginning of your script.

4.  **Run the Script**: Execute the script within the Poetry environment:
    ```bash
    # For GitHub PR review
    poetry run python run_codedog.py pr "owner/repo" 123

    # For GitLab MR review
    poetry run python run_codedog.py pr "owner/repo" 123 --platform gitlab

    # For GitLab MR review with custom GitLab instance
    poetry run python run_codedog.py pr "owner/repo" 123 --platform gitlab --gitlab-url "https://your.gitlab.instance.com"
    ```

This will:
*   Initialize the appropriate retriever (GitHub/GitLab).
*   Fetch the PR/MR data.
*   Use the configured LLMs to generate code summaries and a PR summary.
*   Use the configured LLM to generate code review suggestions.
*   Print a formatted Markdown report to the console.

## GitLab Integration

Codedog fully supports GitLab integration for reviewing merge requests. This feature allows you to analyze code quality in GitLab merge requests just like GitHub pull requests. To use GitLab integration:

1. **Set up GitLab Token**: Generate a personal access token with `api` scope from your GitLab account settings.

2. **Configure Environment Variables**: Add the following to your `.env` file:
   ```
   GITLAB_TOKEN="your_gitlab_personal_access_token"
   GITLAB_URL="https://gitlab.com"  # Or your self-hosted GitLab URL
   ```

3. **Run GitLab MR Review**: Use the following command to review a GitLab merge request:
   ```bash
   python run_codedog.py pr "owner/repo" 123 --platform gitlab
   ```

   Replace `owner/repo` with your GitLab project path and `123` with your merge request IID.

4. **Self-hosted GitLab**: If you're using a self-hosted GitLab instance, specify the URL:
   ```bash
   python run_codedog.py pr "owner/repo" 123 --platform gitlab --gitlab-url "https://your.gitlab.instance.com"
   ```

## Running Tests

To ensure the package is working correctly after setup or changes:

```bash
poetry run pytest
```

## Development

*   **Code Style**: Uses `black` for formatting and `flake8` for linting.
    ```bash
    poetry run black .
    poetry run flake8 .
    ```
*   **Dependencies**: Managed via `poetry`. Use `poetry add <package>` to add new dependencies.

## Contributing

Contributions are welcome! Please refer to the project's contribution guidelines (if available) or open an issue/PR on the repository.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
