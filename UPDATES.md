# CodeDog项目更新说明

## 更新内容

### 1. 改进评分系统

我们对代码评估系统进行了以下改进：

- **评分系统升级**：从5分制升级到更详细的10分制评分系统
- **评分维度更新**：使用更全面的评估维度
  - 可读性 (Readability)
  - 效率与性能 (Efficiency & Performance)
  - 安全性 (Security)
  - 结构与设计 (Structure & Design)
  - 错误处理 (Error Handling)
  - 文档与注释 (Documentation & Comments)
  - 代码风格 (Code Style)
- **详细评分标准**：为每个评分范围（1-3分、4-6分、7-10分）提供了明确的标准
- **报告格式优化**：改进了评分报告的格式，使其更加清晰明了

### 2. 修复DeepSeek API调用问题

修复了DeepSeek API调用问题，特别是"deepseek-reasoner不支持连续用户消息"的错误：
- 将原来的两个连续HumanMessage合并为一个消息
- 确保消息格式符合DeepSeek API要求

### 3. 改进电子邮件通知系统

- 增强了错误处理，提供更详细的故障排除信息
- 添加了Gmail应用密码使用的详细说明
- 更新了.env文件中的SMTP配置注释，使其更加明确
- 新增了详细的电子邮件设置指南 (docs/email_setup.md)
- 开发了高级诊断工具 (test_email.py)，帮助用户测试和排查邮件配置问题
- 改进了Gmail SMTP认证错误的诊断信息，提供明确的步骤解决问题

## 运行项目

### 环境设置

1. 确保已正确配置.env文件，特别是：
   - 平台令牌（GitHub或GitLab）
   - LLM API密钥（OpenAI、DeepSeek等）
   - SMTP服务器设置（如果启用邮件通知）

2. 如果使用Gmail发送邮件通知，需要：
   - 启用Google账户的两步验证
   - 生成应用专用密码（https://myaccount.google.com/apppasswords）
   - 在.env文件中使用应用密码

### 运行命令

1. **评估开发者代码**：
   ```bash
   python run_codedog.py eval "开发者名称" --start-date YYYY-MM-DD --end-date YYYY-MM-DD
   ```

2. **审查PR**：
   ```bash
   python run_codedog.py pr "仓库名称" PR编号
   ```

3. **设置Git钩子**：
   ```bash
   python run_codedog.py setup-hooks
   ```

### 注意事项

- 对于较大的代码差异，可能会遇到上下文长度限制。在这种情况下，考虑使用`gpt-4-32k`或其他有更大上下文窗口的模型。
- DeepSeek模型有特定的消息格式要求，请确保按照上述修复进行使用。

## 进一步改进方向

1. 实现更好的文本分块和处理，以处理大型代码差异
2. 针对不同文件类型的更专业评分标准
3. 进一步改进报告呈现，添加可视化图表
4. 与CI/CD系统的更深入集成 