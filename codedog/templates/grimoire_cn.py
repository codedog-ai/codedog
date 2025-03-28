"""
Chinese grimoire template for code review guidelines.
"""

CODE_REVIEW_GUIDELINES = """
代码审查指南：

1. 代码质量
   - 代码是否清晰易读
   - 是否遵循项目的编码规范
   - 是否有适当的注释和文档
   - 是否避免了代码重复

2. 功能完整性
   - 是否完整实现了需求
   - 是否处理了边界情况
   - 是否有适当的错误处理
   - 是否添加了必要的测试

3. 性能考虑
   - 是否有性能优化的空间
   - 是否避免了不必要的计算
   - 是否合理使用了资源

4. 安全性
   - 是否处理了潜在的安全风险
   - 是否保护了敏感数据
   - 是否遵循安全最佳实践

5. 可维护性
   - 代码结构是否合理
   - 是否遵循SOLID原则
   - 是否便于后续维护和扩展
"""

PR_SUMMARY_TEMPLATE = """
# 拉取请求摘要

## 变更概述
{changes_summary}

## 主要变更
{main_changes}

## 潜在影响
{potential_impact}

## 建议
{recommendations}
"""

CODE_REVIEW_TEMPLATE = """
# 代码审查报告

## 文件：{file_path}

### 变更概述
{changes_summary}

### 详细审查
{detailed_review}

### 建议改进
{improvement_suggestions}

### 安全考虑
{security_considerations}

### 性能影响
{performance_impact}
"""
