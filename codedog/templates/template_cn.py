# --- PR Markdown Report ------------------------------------------------------
REPORT_PR_REVIEW = """# [{repo_name} #{pr_number} - {pr_name}]({url}) Pull Request 分析报告

*powered by GPT and {project} {version}*

{telemetry}


{pr_report}


{cr_report}

"""


REPORT_TELEMETRY = """## 执行信息
- 开始时间: {start_time}
- 执行耗时: {time_usage:.2f}s
- Openai Token 使用数量: {tokens}
- Openai Api 调用成本: ${cost:.4f}
"""

# --- PR Summary Markdown Report ----------------------------------------------

REPORT_PR_SUMMARY = """
## PR 概要

### PR 总结
{overview}

### 变动文件说明
{file_changes}

<details>
<summary><h3>改动列表</h3></summary>

{change_overview}

</details>
"""

REPORT_PR_SUMMARY_OVERVIEW = """{type_desc}

{overview}

"""


REPORT_PR_TYPE_DESC_MAPPING = {
    "feature": "该 PR 添加了新的功能、特性 :sparkles:",
    "fix": "该 PR 修复了代码中的问题 :bug:",
    "refactor": "该 PR 对代码进行重构 :hammer_and_wrench:",
    "perf": "该 PR 尝试进行性能优化 :rocket:",
    "test": "该 PR 主要添加了一些测试 :white_check_mark:",
    "doc": "该 PR 主要为文档变动 :memo:",
    "ci": "该 PR 主要为 CI/CD 变动 :gear:",
    "style": "该 PR 主要为 code style 变动 :art:",
    "chore": "该 PR 做了一些和项目本身无关的事务 :broom:",
    "unknown": "该 PR 的主题未能被识别 :dog: :question:",
}

REPORT_CHANGE_OVERVIEW = """| **[{name}]({url} "{full_name}")** | {content} |"""

REPORT_FILE_CHANGES_MAJOR = """
| 主要变动 | 描述 |
|---|---|
{major_changes}
"""

REPORT_FILE_CHANGES = """
| 其他变动 | 描述 |
|---|---|
{changes}
"""

# --- Code Review Markdown Report ---------------------------------------------
REPORT_CODE_REVIEW = """## 代码审查 (预览版)

*该功能仍在测试中，由 AI 提供的建议可能不正确。*

{feedback}

"""
REPORT_CODE_REVIEW_SEGMENT = """**[{full_name}]({url})**

{review}
"""

REPORT_CODE_REVIEW_NO_FEEDBACK = """对该 PR 没有代码审查建议"""

# --- Code Review Summary Table -----------------------------------------------
PR_REVIEW_SUMMARY_TABLE = """
## PR 审查总结

| 文件 | 可读性 | 效率与性能 | 安全性 | 结构与设计 | 错误处理 | 文档与注释 | 代码风格 | 总分 |
|------|-------------|------------------------|----------|-------------------|---------------|-------------------------|-----------|---------|
{file_scores}
| **平均分** | **{avg_readability:.1f}** | **{avg_efficiency:.1f}** | **{avg_security:.1f}** | **{avg_structure:.1f}** | **{avg_error_handling:.1f}** | **{avg_documentation:.1f}** | **{avg_code_style:.1f}** | **{avg_overall:.1f}** |

### 评分说明:
- 9.0-10.0: 优秀
- 7.0-8.9: 很好
- 5.0-6.9: 良好
- 3.0-4.9: 需要改进
- 1.0-2.9: 较差

### PR 质量评估:
{quality_assessment}
"""

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
