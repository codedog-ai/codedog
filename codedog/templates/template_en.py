# --- PR Markdown Report ------------------------------------------------------
REPORT_PR_REVIEW = """# [{repo_name} #{pr_number} - {pr_name}]({url}) Pull Request Report

*powered by GPT and {project} {version}*

{telemetry}


{pr_report}


{cr_report}

"""


REPORT_TELEMETRY = """## Execution
- Start at: {start_time}
- Time usage: {time_usage:.2f}s
- Openai api tokens: {tokens}
- Openai api costs: ${cost:.4f}
"""

# --- PR Summary Markdown Report ----------------------------------------------

REPORT_PR_SUMMARY = """
## PR Summary

### PR Overview
{overview}

### Change Details
{file_changes}

<details>
<summary><h3>Change File List</h3></summary>

{change_overview}

</details>
"""

REPORT_PR_SUMMARY_OVERVIEW = """{type_desc}

{overview}

"""


REPORT_PR_TYPE_DESC_MAPPING = {
    "feature": "This PR is a new feature :sparkles:",
    "fix": "This PR is fixing bug :bug:",
    "refactor": "This PR is a refactor :hammer_and_wrench:",
    "perf": "This PR try to improve performance :rocket:",
    "test": "This PR try to improve tests :white_check_mark:",
    "doc": "This PR try to improve documentation :memo:",
    "ci": "This PR changes CI/CD :gear:",
    "style": "This PR improves code style :art:",
    "chore": "This PR is a chore :broom:",
    "unknown": "This PR type is not recognized by codedog :dog: :question:",
}

REPORT_CHANGE_OVERVIEW = """| **[{name}]({url} "{full_name}")** | {content} |"""

REPORT_FILE_CHANGES_MAJOR = """
| Major Changes | Description |
|---|---|
{major_changes}
"""

REPORT_FILE_CHANGES = """
| Changes | Description |
|---|---|
{changes}
"""

# --- Code Review Markdown Report ---------------------------------------------
REPORT_CODE_REVIEW = """## Code Review (preview)

*This feature is still under test. Suggestions are given by AI and might be incorrect.*

{feedback}

"""
REPORT_CODE_REVIEW_SEGMENT = """**[{full_name}]({url})**

{review}
"""

REPORT_CODE_REVIEW_NO_FEEDBACK = """No suggestions for this PR."""


# --- Materials ---------------------------------------------------------------

MATERIAL_STATUS_HEADER_MAPPING = {
    "A": "Added files:",
    "C": "Copied files:",
    "D": "Deleted files:",
    "M": "Modified files:",
    "R": "Renamed files:",
    "T": "Type changed files:",
    "U": "Other files:",
    "X": "Unknown(X) files:",
}

MATERIAL_CODE_SUMMARY = """File `{name}` Change: {summary}"""

MATERIAL_PR_METADATA = """Pull Request Metadata:
---
1. Title: {pr_title}

2. Body:
```text
{pr_body}
```

3. Issues:
```text
{issues}
```
---
"""
