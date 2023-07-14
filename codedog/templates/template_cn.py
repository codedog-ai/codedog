CHANGE_SUMMARY = """
| 主要变动 |
|---|
{important_changes}

| 次要变动 |
|---|
{housekeeping_changes}
"""

TABLE_LINE = """| {{idx}}. **[{file_name}]({url})** |\n| {text} |"""

TABLE_LINE_NODATA = "无"

T3_TITLE_LINE = """### {idx}. [{file_name}]({url})"""

REPORT_HEADER = """# [{repo_name} #{pr_number}]({url}) 代码审查报告\n\n*powered by GPT and Codedog {version}*\n\n"""


REPORT_TELEMETRY = """## 执行记录
- 开始时间: {start_time}
- 审查耗时: {time_usage}秒
- 审查文件数量: {files}
- OPENAI API TOKEN数量: {tokens} (约${cost:.4f})\n\n
"""

REPORT_PR_SUMMARY = """## PR概要
{pr_summary}

{pr_changes_summary}\n\n
"""
REPORT_PR_CHANGES_SUMMARY = """
**主要改动**

{important_changes}

**次要改动**

{housekeeping_changes}\n\n
"""

REPORT_PR_CHANGE_SUMMARY = """{idx}. [{path}]({url})\n\n{summary}\n\n"""

REPORT_NO_CHANGES = "无"

REPORT_FEEDBACK = """## PR改进建议 preview

** 目前改进建议功能仍在调试中，建议仅供参考 **

{feedback}\n\n
"""
