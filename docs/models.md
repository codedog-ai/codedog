# 支持的模型

CodeDog 支持多种 AI 模型，可以根据需要选择不同的模型进行代码评估和分析。

## 可用模型

| 模型名称 | 描述 | 上下文窗口 | 相对成本 | 适用场景 |
|---------|------|-----------|---------|---------|
| `gpt-3.5` | OpenAI 的 GPT-3.5 Turbo | 16K tokens | 低 | 一般代码评估，适合大多数场景 |
| `gpt-4` | OpenAI 的 GPT-4 | 8K tokens | 中 | 复杂代码分析，需要更高质量的评估 |
| `gpt-4o` | OpenAI 的 GPT-4o | 128K tokens | 中高 | 大型文件评估，需要处理大量上下文 |
| `deepseek` | DeepSeek 的模型 | 根据配置而定 | 低 | 中文代码评估，本地化场景 |
| `deepseek-r1` | DeepSeek 的 R1 模型 | 根据配置而定 | 低 | 推理能力更强的中文评估 |

## 如何使用

您可以通过命令行参数 `--model` 指定要使用的模型：

```bash
python run_codedog_eval.py "开发者名称" --model gpt-4o
```

或者在环境变量中设置默认模型：

```
# .env 文件
CODE_REVIEW_MODEL=gpt-4o
```

### 使用完整的模型名称

您也可以直接使用 OpenAI 的完整模型名称：

```bash
python run_codedog_eval.py "开发者名称" --model gpt-4-turbo
python run_codedog_eval.py "开发者名称" --model gpt-3.5-turbo-16k
python run_codedog_eval.py "开发者名称" --model gpt-4o-mini
```

系统会自动识别这些模型名称并使用适当的配置。

### 自定义模型版本

您可以在 `.env` 文件中设置特定的模型版本：

```
# 指定 GPT-3.5 的具体版本
GPT35_MODEL="gpt-3.5-turbo-16k"

# 指定 GPT-4 的具体版本
GPT4_MODEL="gpt-4-turbo"

# 指定 GPT-4o 的具体版本
GPT4O_MODEL="gpt-4o-mini"
```

## GPT-4o 模型

GPT-4o 是 OpenAI 的最新模型，具有以下优势：

1. **大型上下文窗口**：支持高达 128K tokens 的上下文窗口，可以处理非常大的文件
2. **更好的代码理解**：对代码的理解和分析能力更强
3. **更快的响应速度**：比 GPT-4 更快，提高评估效率

### 使用建议

- 对于大型文件或复杂代码库，推荐使用 GPT-4o
- 由于成本较高，对于简单的代码评估，可以继续使用 GPT-3.5
- 如果遇到上下文长度限制问题，切换到 GPT-4o 可以解决大多数情况

### 配置示例

```bash
# 使用 GPT-4o 评估代码
python run_codedog_eval.py "开发者名称" --model gpt-4o --tokens-per-minute 6000 --max-concurrent 2

# 使用简写形式
python run_codedog_eval.py "开发者名称" --model 4o
```

## 模型比较

- **GPT-3.5**：适合日常代码评估，成本低，速度快
- **GPT-4**：适合需要深入分析的复杂代码，质量更高
- **GPT-4o**：适合大型文件和需要大量上下文的评估
- **DeepSeek**：适合中文环境和本地化需求

选择合适的模型可以在成本和质量之间取得平衡。
