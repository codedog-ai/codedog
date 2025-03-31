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
PR_CHANGE_REVIEW_MAIN_CHANGE = (
    """this diff contains the major part of logical changes in this change list"""
)

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
And I want you to review the code changes, provide detailed feedback, and score the changes based on language-specific standards and best practices.

## Review Requirements:
1. Check correctness and logic of the code changes
2. Evaluate adherence to language-specific coding standards 
3. Identify potential bugs, performance issues, or security vulnerabilities
4. Provide specific, actionable suggestions for improvement
5. Score the code in multiple dimensions (see scoring system below)

## Language-Specific Standards:
{language} code should follow these standards:

### Python:
- PEP 8 style guide (spacing, naming conventions, line length)
- Proper docstrings (Google, NumPy, or reST style)
- Type hints for function parameters and return values
- Error handling with specific exceptions
- Avoid circular imports and global variables
- Follow SOLID principles and avoid anti-patterns

### JavaScript/TypeScript:
- ESLint/TSLint standards
- Proper async/await or Promise handling
- Consistent styling (following project's style guide)
- Proper error handling
- Type definitions (for TypeScript)
- Avoid direct DOM manipulation in frameworks

### Java:
- Follow Oracle Code Conventions
- Proper exception handling
- Appropriate access modifiers
- Clear Javadoc comments
- Correct resource management and memory handling
- Follow SOLID principles

### General (for all languages):
- DRY (Don't Repeat Yourself) principle
- Clear naming conventions
- Appropriate comments for complex logic
- Proper error handling
- Security best practices

## Scoring System (1-5 scale, where 5 is excellent):
- **Correctness** (does the code function as intended?)
- **Readability** (is the code easy to understand?)
- **Maintainability** (how easy will this code be to maintain?)
- **Standards Compliance** (does it follow language/framework conventions?)
- **Performance** (any obvious performance issues?)
- **Security** (any security concerns?)

## Overall Score:
- Calculate a weighted average as follows:
  - Correctness: 30%
  - Readability: 20%
  - Maintainability: 20%
  - Standards Compliance: 15%
  - Performance: 10%
  - Security: 5%

## Format your review as follows:
1. Brief summary of the changes (1-2 sentences)
2. Detailed feedback with line references where appropriate
3. Specific suggestions for improvement
4. Scoring table with justifications for each dimension
5. Overall score with brief conclusion

## IMPORTANT: Scores Summary
At the end of your review, include a clearly formatted score summary section like this:

### SCORES:
- Correctness: [score] /5
- Readability: [score] /5
- Maintainability: [score] /5
- Standards Compliance: [score] /5
- Performance: [score] /5
- Security: [score] /5
- Overall: [calculated_overall_score] /5

Replace [score] with your actual numeric scores (e.g., 4.5).

Here's the code diff from file {name}:
```{language}
{content}
```
"""


TRANSLATE_PR_REVIEW = """Help me translate some content into {language}.
It belongs to a pull request review and is about {description}.

Content:
---
{content}
---

Note that the content might be used in markdown or other formatted text,
so don't change the paragraph layout of the content or add symbols.
Your translation:"""

# Template for the summary score table at the end of PR review
PR_REVIEW_SUMMARY_TABLE = """
## PR Review Summary

| File | Correctness | Readability | Maintainability | Standards | Performance | Security | Overall |
|------|-------------|-------------|----------------|-----------|-------------|----------|---------|
{file_scores}
| **Average** | **{avg_correctness:.2f}** | **{avg_readability:.2f}** | **{avg_maintainability:.2f}** | **{avg_standards:.2f}** | **{avg_performance:.2f}** | **{avg_security:.2f}** | **{avg_overall:.2f}** |

### Score Legend:
- 5.00: Excellent
- 4.00-4.99: Very Good
- 3.00-3.99: Good
- 2.00-2.99: Needs Improvement
- 1.00-1.99: Poor

### PR Quality Assessment:
{quality_assessment}
"""
