# flake8: noqa
"""Grimoire of CodeDog. Chinese version."""


# -- PR Review 模版 ---------------------------------------------------

# this template is used for format diff file summary list seperate important and housekeeping changes.
PR_FILES_SUMMARY_HEADER = """
**重要变动**
{important_changes}
**次要变动**
{unimportant_changes}
"""

PR_FILE_SUMMARY_HEADER = "{path}: {summary}"


# this template is used for review single file change.
PR_CHANGE_REVIEW_SUMMARY = "summary of diff"
PR_CHANGE_REVIEW_MAIN_CHANGE = """this diff contains the major part of logical changes in this change list"""
PR_CHANGE_REVIEW_SCORE = "代码变动质量打分，取值为1或2或3或4或5"

PR_CHANGE_REVIEW_TEMPLATE = """
请你扮演代码审查者，我会作为你的助手，为你提供一个change list中一个文件的代码改动，请按照以下要求对这段代码改动内容进行审查：
1. 判断该文件是否是一个包含大量的业务逻辑改动的代码文件，一般来说，这样的文件中往往会有一些函数逻辑变动

2. 用中文简要概括该diff改动的内容，不超过100字，不要包含第一步的结果，只概括改动内容即可


{format_instructions}

请注意，在概括内容中只概括代码改动的内容即可，不要提任何判断改动是否为housekeeping改动的结论
根据以上指示，审查文件{name}变更:
```
{text}
```"""

PR_CHANGE_REVIEW_FALLBACK_TEMPLATE = """请你扮演代码审查者，我会作为你的助手，将一段代码文件的diff提供给你，
请用中文简要概括该diff改动的内容，不超过100字

根据指示审查文件{name}变更:
```
{text}
```"""

# this template is for starting sequentially summarize PR content.
PR_SUMMARIZE_TEMPLATE = """
请根据以下我提供的信息，概括一次git pull request的内容:
pull request information (for better understand the context, not part of the pull request):
```
{pull_request_info}
```
related issue information (for better understand the context, not part of the pull request):
```
{issue_info}
```

主要改动:
```
{summary}
```
请注意，我希望你对整个pull request进行概括，不要具体说明某个文件做了什么事情，在你的概括中不应当具体提到某个文件
概括结果应为不超过200字的中文内容:"""


PR_SIMPLE_FEEDBACK_TEMPLATE = """
请你扮演代码审查者，我会作为你的助手，发给你一个文件的diff改动，请说明你觉得代码中需要修复的部分
如果代码看起来没什么问题或者你无法判断，请回复ok，并且除ok外不要回复任何其他的内容

{text}

关于你的修改意见，请遵守以下几条规则：
1. 禁止提出不涉及具体代码，概括性、指导性的意见
2. 不要用主观的口吻对代码质量进行评价
3. 你的回复内容应当尽量的精确、简洁，每句话都做到言之有物
"""
