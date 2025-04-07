# CodeDog 产品文档

## 1. 产品概述

CodeDog 是一款基于大语言模型（LLM）的智能代码评审工具，旨在通过自动化代码分析提高开发团队的代码质量和开发效率。它能够自动分析代码提交，生成详细的评审报告，并通过电子邮件通知相关人员。

### 1.1 核心功能

- **自动代码评审**：在代码提交时自动触发评审流程，分析代码质量
- **多维度评分**：从可读性、效率、安全性等多个维度评估代码
- **详细报告生成**：生成结构化的 Markdown 格式评审报告
- **邮件通知**：将评审结果通过邮件发送给相关人员
- **多模型支持**：支持 OpenAI、Azure OpenAI 和 DeepSeek 等多种 LLM 模型

### 1.2 应用场景

- 个人开发者的代码自我评审
- 团队协作中的代码质量控制
- 拉取请求（PR）的自动评审
- 开发者代码质量评估和绩效分析

## 2. 系统架构

CodeDog 采用模块化设计，主要包含以下组件：

- **Git 钩子处理器**：捕获 Git 事件并触发评审流程
- **代码分析引擎**：解析和分析代码结构和内容
- **LLM 集成层**：与各种大语言模型 API 交互
- **评审生成器**：基于 LLM 输出生成结构化评审
- **报告格式化器**：将评审结果转换为可读性强的报告
- **通知系统**：处理电子邮件发送和其他通知

## 3. 功能详解

### 3.1 自动代码评审

CodeDog 可以在代码提交时自动触发评审流程，通过 Git 钩子机制捕获提交事件，分析更改的代码，并生成评审报告。

**工作流程**：
1. 开发者提交代码到 Git 仓库
2. Git 钩子脚本被触发（如 post-commit）
3. 系统获取提交信息和更改的文件
4. LLM 生成代码评审和摘要
5. 系统格式化评审结果为结构化报告
6. 通知系统将报告发送给相关人员

**安装 Git 钩子**：
```python
from codedog.utils.git_hooks import install_git_hooks
install_git_hooks("/path/to/your/repo")
```

### 3.2 多维度代码评估

系统从多个维度对代码进行全面评估，包括：

- **可读性**：代码结构、命名规范、注释质量
- **效率与性能**：算法效率、资源利用、潜在瓶颈
- **安全性**：输入验证、错误处理、安全编码实践
- **结构与设计**：模块化、整体架构、设计原则
- **错误处理**：异常处理、边缘情况处理
- **文档与注释**：文档完整性、注释清晰度
- **代码风格**：符合语言特定编码标准

每个维度满分 10 分，最终总分为各维度的加权平均值。

### 3.3 报告生成与通知

CodeDog 生成结构化的 Markdown 格式评审报告，包含：

- 提交摘要和概述
- 文件级别的详细评审
- 多维度评分表格
- 具体改进建议
- 代码量统计信息

评审报告可以通过电子邮件发送给相关人员，支持 HTML 格式的邮件内容，使用配置的 SMTP 服务器发送。

### 3.4 多模型支持

CodeDog 支持多种大语言模型，以满足不同的需求和预算：

- **OpenAI GPT-3.5/GPT-4o**：通用模型，适合日常代码评审
- **Azure OpenAI**：企业级安全性，适合需要数据合规的场景
- **DeepSeek Chat/Reasoner**：专业模型，适合复杂代码分析

可以为不同任务配置不同模型：
```
CODE_SUMMARY_MODEL="gpt-3.5"  # 代码摘要
PR_SUMMARY_MODEL="gpt-4o"     # PR摘要
CODE_REVIEW_MODEL="deepseek"  # 代码评审
```

## 4. 使用指南

### 4.1 环境要求

- Python 3.8+
- Git
- 互联网连接（用于 API 调用）
- SMTP 服务器访问（用于邮件通知）

### 4.2 安装与配置

1. **安装 CodeDog**：
   ```bash
   pip install codedog
   ```

2. **配置环境变量**：
   创建 `.env` 文件，添加必要的配置：
   ```
   # API密钥
   OPENAI_API_KEY=your_openai_api_key
   
   # 模型选择
   CODE_REVIEW_MODEL=gpt-3.5
   PR_SUMMARY_MODEL=gpt-4o
   
   # 邮件配置
   EMAIL_ENABLED=true
   NOTIFICATION_EMAILS=your_email@example.com
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your_email@gmail.com
   SMTP_PASSWORD=your_app_specific_password
   ```

3. **安装 Git 钩子**：
   ```python
   from codedog.utils.git_hooks import install_git_hooks
   install_git_hooks(".")
   ```

### 4.3 基本使用

#### 评估单个提交

```bash
# 评审最新提交
python run_codedog_commit.py --verbose

# 评审特定提交
python run_codedog_commit.py --commit <commit_hash> --verbose
```

#### 评估时间段内的提交

```bash
python run_codedog.py eval "<author>" --start-date YYYY-MM-DD --end-date YYYY-MM-DD --include .py
```

#### 评估 GitHub PR

```bash
python run_codedog.py pr "owner/repo" <pr_number>
```

### 4.4 配置选项

CodeDog 提供多种配置选项，可以通过环境变量或命令行参数设置：

- **平台配置**：GitHub/GitLab 访问令牌
- **LLM 配置**：API 密钥和端点设置
- **模型选择**：用于不同任务的模型选择
- **电子邮件配置**：SMTP 服务器和通知设置
- **评审配置**：文件类型包含/排除规则

## 5. 最佳实践

### 5.1 个人开发者

- 在提交前评审代码，发现潜在问题
- 使用 Git 钩子自动触发评审
- 关注评审中反复出现的问题模式
- 定期运行评估跟踪进步

### 5.2 团队协作

- 将 CodeDog 集成到 CI/CD 流程中
- 为每个 PR 生成自动评审
- 使用评审报告作为讨论的起点
- 定期回顾团队评审趋势，识别系统性问题

## 6. 常见问题解答

**Q: 如何处理大文件或大量文件的评审？**  
A: CodeDog 会自动处理文件分割和批处理，但对于特别大的文件，可能需要增加超时设置或选择更快的模型。

**Q: 如何解决 API 限制问题？**  
A: 可以调整请求频率、使用缓存或升级 API 计划。对于 DeepSeek API 错误，系统会自动重试两次，如果仍然失败，则放弃评估并给出 0 分。

**Q: 如何配置 Gmail SMTP？**  
A: 需要在 Google 账户开启两步验证，然后创建应用专用密码用于 SMTP 认证。详细步骤请参考文档。

## 7. 技术规格

- **支持的语言**：Python、JavaScript、Java、TypeScript 等主流编程语言
- **支持的模型**：GPT-3.5、GPT-4o、DeepSeek Chat、DeepSeek Reasoner、Azure OpenAI
- **支持的平台**：GitHub、GitLab、本地 Git 仓库
- **报告格式**：Markdown、HTML 邮件
- **评分维度**：7个维度（可读性、效率、安全性、结构、错误处理、文档、代码风格）

---

*CodeDog - 智能代码评审，提升开发效率*
