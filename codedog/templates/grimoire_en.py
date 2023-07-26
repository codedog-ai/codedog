# flake8: noqa

"""Grimoire of CodeDog. English version."""

# -- PR Review Prompt Template ---------------------------------------------------

# this template is used for format diff file summary list seperate important and housekeeping changes.
PR_FILES_SUMMARY_HEADER = """
**Main changes**
{important_changes}
**Secondary changes**
{unimportant_changes}
"""

PR_FILE_SUMMARY_HEADER = "{path}: {summary}"


# this template is used for review single file change.
PR_CHANGE_REVIEW_SUMMARY = "summary of diff"
PR_CHANGE_REVIEW_MAIN_CHANGE = """this diff contains the major part of logical changes in this change list"""

PR_CHANGE_REVIEW_TEMPLATE = """
Act as a code reviewer, I will be your assistant, provide you a file diff in a change list,
please review the code change according to the following requirements:

1. Determine whether the file is a code file containing major logic changes. Generally speaking,
such files often have some function logic changes

2. Briefly summarize the content of the diff change in Chinese, no more than 100 words,
do not include the results of the first step, just summarize the content of the change.

{format_instructions}

Please act as a code reviewer, review the file {name} change. I want you to give:
1. Determine whether the file contains major logic changes. Generally speaking,
2. A brief summary of the diff change, no more than 100 words. Do not include the results of the first step

review the code according to the instructions:

{format_instructions}

here is the diff content:
```
{text}
```"""

PR_CHANGE_REVIEW_FALLBACK_TEMPLATE = """
Please act as a code reviewer, review the file {name} change. I want you to give:

give a brief summary of the diff change, no more than 100 words.

here is the diff content:
```
{text}
```"""

# this template is for starting sequentially summarize PR content.
PR_SUMMARIZE_TEMPLATE = """
Summarize a git pull request by the given information:

pull request information (for better understand the context, not part of the pull request):
```
{pull_request_info}
```
related issue information (for better understand the context, not part of the pull request):
```
{issue_info}
```

changes summary:
```
{summary}
```

Please note that I want you to summarize the entire pull request, not specific files.
The summary should be no more than 200 words:"""


PR_SIMPLE_FEEDBACK_TEMPLATE = """
Act as a code reviewer, I will be your assistant, provide you a file diff from a change list,
please review the code change according to the following requirements:

1. Don't give subjective comments on the code quality, such as "this code is bad", "this code is good", etc.
2. Don't give general suggestions that are not specific to the code, such as "this code needs to be refactored", "this code needs to be optimized", etc.

If you can't judge whether the code is good or bad, please reply "ok" and don't reply any other content except "ok".

Here's the code:
{text}
"""


CODE_SUMMARY = """Act as a Code Reviewer Assistant. I will give a code diff content.
And I want you to briefly summarize the content of the diff to helper reviewers understand what happened in this file
faster and more convienently.

Your summary must be totaly objective and contains no opinions or suggestions.
For example: ```This diff contains change in functions `create_database`,`delete_database`,
it add a parameter `force` to these functions.
```

Here's the diff of file {name}:
```{language}
{content}
```
"""

PR_SUMMARY = """Act as a Code Reviewer Assistant. I want you to provide some information aboud below Pull Request(PR)
to help reviewers understand it better and review it faster.

The items I want you to provide are:
- Describe the changes of this PR and it's objective.
- Categorize this PR into one of the following types: Feature,Fix,Refactor,Perf,Doc,Test,Ci,Style,Housekeeping
- If it's a feature/refactor PR. List the important change files which you believe
    contains the major logical changes of this PR.

Below is informations about this PR I can provide to you:
PR Metadata:
```text
{metadata}
```
Change Files (with status):
```text
{change_files}
```
Code change summaries (if this pr contains no code files, this will be empty):
```text
{code_summaries}
```

{format_instructions}
"""

CODE_SUGGESTION = """Act as a Code Reviewer Assistant. I will give a code diff content.
And I want you to check whether the code change is correct and give some suggestions to the author.

Here's the code diff from file {name}:
```{language}
{content}
```
"""
