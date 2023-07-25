CHANGE_SUMMARY = """
| Main Change |
|---|
{important_changes}

| Secondary Change |
|---|
{housekeeping_changes}
"""

TABLE_LINE = """| {{idx}}. **[{file_name}]({url})** |\n| {text} |"""

TABLE_LINE_NODATA = "-"

T3_TITLE_LINE = """### {idx}. [{file_name}]({url})"""


REPORT_HEADER = (
    """# [{repo_name} #{pr_number}]({url}) Code Review Report\n\n*powered by GPT and Codedog {version}*\n\n"""
)

REPORT_TELEMETRY = """## Execution Record
- Start at: {start_time}
- Time usage: {time_usage}s
- Reviewed files: {files}
- Openai api tokens: {tokens} (${cost:.4f})\n\n
"""


REPORT_PR_SUMMARY = """## PR Summary
{pr_summary}

{pr_changes_summary}\n\n
"""
REPORT_PR_CHANGES_SUMMARY = """
**Main Change**

{important_changes}

**Secondary Change**

{housekeeping_changes}\n\n
"""

REPORT_PR_CHANGE_SUMMARY = """{idx}. [{path}]({url})\n\n{summary}\n\n"""

REPORT_NO_CHANGES = ""

REPORT_FEEDBACK = """## Suggestions (preview)

** Suggestions are still under development, please use with caution **

{feedback}\n\n
"""


# --- pr summary --------------------------------------------------------------
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
