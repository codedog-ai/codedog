import asyncio
import json
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import re
import logging  # Add logging import
import os
import random
import time
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential
import math
import tiktoken  # 用于精确计算token数量

# 导入 grimoire 模板
from codedog.templates.grimoire_en import CODE_SUGGESTION
from codedog.templates.grimoire_cn import GrimoireCn
# 导入优化的代码评审prompt
from codedog.templates.optimized_code_review_prompt import (
    SYSTEM_PROMPT,
    CODE_REVIEW_PROMPT,
    LANGUAGE_SPECIFIC_CONSIDERATIONS
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from codedog.utils.git_log_analyzer import CommitInfo


class CodeEvaluation(BaseModel):
    """Structured output for code evaluation"""
    readability: int = Field(description="Code readability score (1-10)", ge=1, le=10)
    efficiency: int = Field(description="Code efficiency and performance score (1-10)", ge=1, le=10)
    security: int = Field(description="Code security score (1-10)", ge=1, le=10)
    structure: int = Field(description="Code structure and design score (1-10)", ge=1, le=10)
    error_handling: int = Field(description="Error handling score (1-10)", ge=1, le=10)
    documentation: int = Field(description="Documentation and comments score (1-10)", ge=1, le=10)
    code_style: int = Field(description="Code style score (1-10)", ge=1, le=10)
    overall_score: float = Field(description="Overall score (1-10)", ge=1, le=10)
    estimated_hours: float = Field(description="Estimated working hours for an experienced programmer (5-10+ years)", default=0.0)
    comments: str = Field(description="Evaluation comments and improvement suggestions")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeEvaluation":
        """Create a CodeEvaluation instance from a dictionary, handling float scores."""
        # Convert float scores to integers for all score fields except overall_score
        score_fields = ["readability", "efficiency", "security", "structure",
                       "error_handling", "documentation", "code_style"]

        for field in score_fields:
            if field in data and isinstance(data[field], float):
                data[field] = round(data[field])

        return cls(**data)


@dataclass(frozen=True)  # Make it immutable and hashable
class FileEvaluationResult:
    """文件评价结果"""
    file_path: str
    commit_hash: str
    commit_message: str
    date: datetime
    author: str
    evaluation: CodeEvaluation


class TokenBucket:
    """Token bucket for rate limiting with improved algorithm and better concurrency handling"""
    def __init__(self, tokens_per_minute: int = 10000, update_interval: float = 1.0):
        self.tokens_per_minute = tokens_per_minute
        self.update_interval = update_interval
        self.tokens = tokens_per_minute
        self.last_update = time.time()
        self.lock = asyncio.Lock()
        self.total_tokens_used = 0  # 统计总共使用的令牌数
        self.total_wait_time = 0.0  # 统计总共等待的时间
        self.pending_requests = []  # 待处理的请求队列
        self.request_count = 0  # 请求计数器

    async def get_tokens(self, requested_tokens: int) -> float:
        """Get tokens from the bucket. Returns the wait time needed."""
        # 生成唯一的请求ID
        request_id = self.request_count
        self.request_count += 1

        # 创建一个事件，用于通知请求何时可以继续
        event = asyncio.Event()
        wait_time = 0.0

        async with self.lock:
            now = time.time()
            time_passed = now - self.last_update

            # Replenish tokens
            self.tokens = min(
                self.tokens_per_minute,
                self.tokens + (time_passed * self.tokens_per_minute / 60.0)
            )
            self.last_update = now

            # 检查是否有足够的令牌
            if self.tokens >= requested_tokens:
                # 有足够的令牌，直接处理
                self.tokens -= requested_tokens
                self.total_tokens_used += requested_tokens
                return 0.0
            else:
                # 没有足够的令牌，需要等待
                # 先消耗掉当前所有可用的令牌
                available_tokens = self.tokens
                self.tokens = 0
                self.total_tokens_used += available_tokens

                # 计算还需要多少令牌
                tokens_still_needed = requested_tokens - available_tokens

                # 计算需要等待的时间
                wait_time = (tokens_still_needed * 60.0 / self.tokens_per_minute)

                # 添加一些随机性，避免雇佯效应
                wait_time *= (1 + random.uniform(0, 0.1))

                # 更新统计信息
                self.total_wait_time += wait_time

                # 将请求添加到队列中，包含请求ID、所需令牌数、事件和计算出的等待时间
                self.pending_requests.append((request_id, tokens_still_needed, event, wait_time))

                # 按等待时间排序，使小请求先处理
                self.pending_requests.sort(key=lambda x: x[3])

                # 启动令牌补充任务
                asyncio.create_task(self._replenish_tokens())

        # 等待事件触发
        await event.wait()
        return wait_time

    async def _replenish_tokens(self):
        """Continuously replenish tokens and process pending requests"""
        while True:
            # 等待一小段时间
            await asyncio.sleep(0.1)

            async with self.lock:
                # 如果没有待处理的请求，则退出
                if not self.pending_requests:
                    break

                # 计算经过的时间和新生成的令牌
                now = time.time()
                time_passed = now - self.last_update
                new_tokens = time_passed * self.tokens_per_minute / 60.0

                # 更新令牌数量和时间
                self.tokens += new_tokens
                self.last_update = now

                # 处理待处理的请求
                i = 0
                while i < len(self.pending_requests):
                    _, tokens_needed, event, _ = self.pending_requests[i]

                    # 如果有足够的令牌，则处理这个请求
                    if self.tokens >= tokens_needed:
                        self.tokens -= tokens_needed
                        # 触发事件，通知请求可以继续
                        event.set()
                        # 从待处理列表中移除这个请求
                        self.pending_requests.pop(i)
                    else:
                        # 没有足够的令牌，移动到下一个请求
                        i += 1

                # 如果所有请求都处理完毕，则退出
                if not self.pending_requests:
                    break

    def get_stats(self) -> Dict[str, float]:
        """获取令牌桶的使用统计信息"""
        now = time.time()
        time_passed = now - self.last_update

        # 计算当前可用令牌，考虑从上次更新到现在的时间内生成的令牌
        current_tokens = min(
            self.tokens_per_minute,
            self.tokens + (time_passed * self.tokens_per_minute / 60.0)
        )

        # 计算当前使用率
        usage_rate = 0
        if self.total_tokens_used > 0:
            elapsed_time = now - self.last_update + self.total_wait_time
            if elapsed_time > 0:
                usage_rate = self.total_tokens_used / (elapsed_time / 60.0)

        # 计算当前并发请求数
        pending_requests = len(self.pending_requests)

        # 计算估计的恢复时间
        recovery_time = 0
        if pending_requests > 0 and self.tokens_per_minute > 0:
            # 获取所有待处理请求的总令牌数
            total_pending_tokens = sum(tokens for _, tokens, _, _ in self.pending_requests)
            # 计算恢复时间
            recovery_time = max(0, (total_pending_tokens - current_tokens) * 60.0 / self.tokens_per_minute)

        return {
            "tokens_per_minute": self.tokens_per_minute,
            "current_tokens": current_tokens,
            "total_tokens_used": self.total_tokens_used,
            "total_wait_time": self.total_wait_time,
            "average_wait_time": self.total_wait_time / max(1, self.total_tokens_used / 1000),  # 每1000个令牌的平均等待时间
            "pending_requests": pending_requests,
            "usage_rate": usage_rate,  # 实际使用率（令牌/分钟）
            "recovery_time": recovery_time  # 估计的恢复时间（秒）
        }


def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """精确计算文本的token数量

    Args:
        text: 要计算的文本
        model_name: 模型名称，默认为 gpt-3.5-turbo

    Returns:
        int: token数量
    """
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # 如果模型不在tiktoken的列表中，使用默认编码
        encoding = tiktoken.get_encoding("cl100k_base")

    # 计算token数量
    tokens = encoding.encode(text)
    return len(tokens)


def save_diff_content(file_path: str, diff_content: str, estimated_tokens: int, actual_tokens: int = None):
    """将diff内容保存到中间文件中

    Args:
        file_path: 文件路径
        diff_content: diff内容
        estimated_tokens: 估算的token数量
        actual_tokens: 实际的token数量，如果为None则会计算
    """
    # 创建diffs目录，如果不存在
    os.makedirs("diffs", exist_ok=True)

    # 生成安全的文件名
    safe_name = re.sub(r'[^\w\-_.]', '_', file_path)
    output_path = f"diffs/{safe_name}.diff"

    # 计算实际token数量，如果没有提供
    if actual_tokens is None:
        actual_tokens = count_tokens(diff_content)

    # 添加元数据到diff内容中
    metadata = f"""# File: {file_path}
# Estimated tokens: {estimated_tokens}
# Actual tokens: {actual_tokens}
# Token ratio (actual/estimated): {actual_tokens/estimated_tokens:.2f}
# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(metadata + diff_content)

    logger.info(f"Saved diff content to {output_path} (estimated: {estimated_tokens}, actual: {actual_tokens} tokens)")

    # 如果实际token数量远远超过估计值，记录警告
    if actual_tokens > estimated_tokens * 1.5:
        logger.warning(f"Warning: Actual token count ({actual_tokens}) significantly exceeds estimated value ({estimated_tokens})")


class DiffEvaluator:
    """代码差异评价器"""

    def __init__(self, model: BaseChatModel, tokens_per_minute: int = 9000, max_concurrent_requests: int = 3,
                 save_diffs: bool = False):
        """
        初始化评价器

        Args:
            model: 用于评价代码的语言模型
            tokens_per_minute: 每分钟令牌数量限制，默认为9000
            max_concurrent_requests: 最大并发请求数，默认为3
            save_diffs: 是否保存diff内容到中间文件，默认为False
        """
        self.model = model
        self.parser = PydanticOutputParser(pydantic_object=CodeEvaluation)
        self.save_diffs = save_diffs  # 新增参数，控制是否保存diff内容

        # 获取模型名称，用于计算token
        self.model_name = getattr(model, "model_name", "gpt-3.5-turbo")

        # Rate limiting settings - 自适应速率控制
        self.initial_tokens_per_minute = tokens_per_minute  # 初始令牌生成速率
        self.token_bucket = TokenBucket(tokens_per_minute=self.initial_tokens_per_minute)  # 留出缓冲
        self.MIN_REQUEST_INTERVAL = 1.0  # 请求之间的最小间隔
        self.MAX_CONCURRENT_REQUESTS = max_concurrent_requests  # 最大并发请求数
        self.request_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
        self._last_request_time = 0

        # 自适应控制参数
        self.rate_limit_backoff_factor = 1.5  # 遇到速率限制时的退避因子
        self.rate_limit_recovery_factor = 1.2  # 成功一段时间后的恢复因子
        self.consecutive_failures = 0  # 连续失败次数
        self.consecutive_successes = 0  # 连续成功次数
        self.success_threshold = 10  # 连续成功多少次后尝试恢复速率
        self.rate_limit_errors = 0  # 速率限制错误计数
        self.last_rate_adjustment_time = time.time()  # 上次调整速率的时间

        # 缓存设置
        self.cache = {}  # 简单的内存缓存 {file_hash: evaluation_result}
        self.cache_hits = 0  # 缓存命中次数

        # 创建diffs目录，如果需要保存diff内容
        if self.save_diffs:
            os.makedirs("diffs", exist_ok=True)

        # System prompt - 使用优化的系统提示
        self.system_prompt = """你是一位经验丰富的代码评审专家，擅长评价各种编程语言的代码质量。
请根据以下几个方面对代码进行评价，并给出1-10分的评分（10分为最高）：
1. 可读性：代码是否易于阅读和理解
2. 效率：代码是否高效，是否有性能问题
3. 安全性：代码是否存在安全隐患
4. 结构：代码结构是否合理，是否遵循良好的设计原则
5. 错误处理：是否有适当的错误处理机制
6. 文档和注释：注释是否充分，是否有必要的文档
7. 代码风格：是否遵循一致的代码风格和最佳实践
8. 总体评分：综合以上各项的总体评价

请以JSON格式返回结果，包含以上各项评分和详细评价意见。

重要提示：
1. 即使代码不完整或难以理解，也请尽量给出评价，并在评论中说明情况
2. 如果代码是差异格式（diff），请忽略差异标记（+/-），专注于评价代码本身
3. 如果无法评估，请返回默认评分5分，并在评论中说明原因
4. 始终返回有效的JSON格式"""

        # 添加JSON输出指令
        self.json_output_instruction = """
请以JSON格式返回评价结果，包含7个评分字段和详细评价意见：

```json
{
  "readability": 评分,
  "efficiency": 评分,
  "security": 评分,
  "structure": 评分,
  "error_handling": 评分,
  "documentation": 评分,
  "code_style": 评分,
  "overall_score": 总评分,
  "comments": "详细评价意见和改进建议"
}
```

总评分计算方式：所有7个指标的加权平均值（取一位小数）。
"""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=10),
        retry=tenacity.retry_if_exception_type(Exception)
    )
    def _calculate_file_hash(self, diff_content: str) -> str:
        """计算文件差异内容的哈希值，用于缓存"""
        return hashlib.md5(diff_content.encode('utf-8')).hexdigest()

    def _adjust_rate_limits(self, is_rate_limited: bool = False):
        """根据API响应动态调整速率限制

        Args:
            is_rate_limited: 是否遇到了速率限制错误
        """
        now = time.time()

        # 如果遇到速率限制错误
        if is_rate_limited:
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.rate_limit_errors += 1

            # 减少令牌生成速率
            new_rate = self.token_bucket.tokens_per_minute / self.rate_limit_backoff_factor
            logger.warning(f"Rate limit encountered, reducing token generation rate: {self.token_bucket.tokens_per_minute:.0f} -> {new_rate:.0f} tokens/min")
            print(f"⚠️ Rate limit encountered, reducing request rate: {self.token_bucket.tokens_per_minute:.0f} -> {new_rate:.0f} tokens/min")
            self.token_bucket.tokens_per_minute = new_rate

            # 增加最小请求间隔
            self.MIN_REQUEST_INTERVAL *= self.rate_limit_backoff_factor
            logger.warning(f"Increasing minimum request interval: {self.MIN_REQUEST_INTERVAL:.2f}s")

            # 减少最大并发请求数，但不少于1
            if self.MAX_CONCURRENT_REQUESTS > 1:
                self.MAX_CONCURRENT_REQUESTS = max(1, self.MAX_CONCURRENT_REQUESTS - 1)
                self.request_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
                logger.warning(f"Reducing maximum concurrent requests: {self.MAX_CONCURRENT_REQUESTS}")
        else:
            # 请求成功
            self.consecutive_successes += 1
            self.consecutive_failures = 0

            # 如果连续成功次数达到阈值，尝试恢复速率
            if self.consecutive_successes >= self.success_threshold and (now - self.last_rate_adjustment_time) > 60:
                # 增加令牌生成速率，但不超过初始值
                new_rate = min(self.initial_tokens_per_minute,
                               self.token_bucket.tokens_per_minute * self.rate_limit_recovery_factor)

                if new_rate > self.token_bucket.tokens_per_minute:
                    logger.info(f"After {self.consecutive_successes} consecutive successes, increasing token generation rate: {self.token_bucket.tokens_per_minute:.0f} -> {new_rate:.0f} tokens/min")
                    print(f"✅ After {self.consecutive_successes} consecutive successes, increasing request rate: {self.token_bucket.tokens_per_minute:.0f} -> {new_rate:.0f} tokens/min")
                    self.token_bucket.tokens_per_minute = new_rate

                    # 减少最小请求间隔，但不少于初始值
                    self.MIN_REQUEST_INTERVAL = max(1.0, self.MIN_REQUEST_INTERVAL / self.rate_limit_recovery_factor)

                    # 增加最大并发请求数，但不超过初始值
                    if self.MAX_CONCURRENT_REQUESTS < 3:
                        self.MAX_CONCURRENT_REQUESTS += 1
                        self.request_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
                        logger.info(f"Increasing maximum concurrent requests: {self.MAX_CONCURRENT_REQUESTS}")

                    self.last_rate_adjustment_time = now

    def _split_diff_content(self, diff_content: str, file_path: str = None, max_tokens_per_chunk: int = 8000) -> List[str]:
        """将大型差异内容分割成多个小块，以适应模型的上下文长度限制

        Args:
            diff_content: 差异内容
            file_path: 文件路径，用于保存diff内容
            max_tokens_per_chunk: 每个块的最大令牌数，默认为8000

        Returns:
            List[str]: 分割后的差异内容块列表
        """
        # 粗略估计令牌数
        words = diff_content.split()
        estimated_tokens = len(words) * 1.2

        # 如果启用了保存diff内容，则计算实际token数量
        if self.save_diffs and file_path:
            actual_tokens = count_tokens(diff_content, self.model_name)
            save_diff_content(file_path, diff_content, estimated_tokens, actual_tokens)

        # 如果估计的令牌数小于最大限制，直接返回原始内容
        if estimated_tokens <= max_tokens_per_chunk:
            return [diff_content]

        # 分割差异内容
        chunks = []
        lines = diff_content.split('\n')
        current_chunk = []
        current_tokens = 0

        for line in lines:
            line_tokens = len(line.split()) * 1.2

            # 如果当前块加上这一行会超过限制，则创建新块
            if current_tokens + line_tokens > max_tokens_per_chunk and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_tokens = 0

            # 如果单行就超过限制，则将其分割
            if line_tokens > max_tokens_per_chunk:
                # 将长行分割成多个小块
                words = line.split()
                sub_chunks = []
                sub_chunk = []
                sub_tokens = 0

                for word in words:
                    word_tokens = len(word) * 0.2  # 粗略估计
                    if sub_tokens + word_tokens > max_tokens_per_chunk and sub_chunk:
                        sub_chunks.append(' '.join(sub_chunk))
                        sub_chunk = []
                        sub_tokens = 0

                    sub_chunk.append(word)
                    sub_tokens += word_tokens

                if sub_chunk:
                    sub_chunks.append(' '.join(sub_chunk))

                # 将分割后的小块添加到结果中
                for sub in sub_chunks:
                    chunks.append(sub)
            else:
                # 正常添加行
                current_chunk.append(line)
                current_tokens += line_tokens

        # 添加最后一个块
        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        logger.info(f"Content too large, split into {len(chunks)} chunks for evaluation")
        print(f"ℹ️ File too large, will be processed in {len(chunks)} chunks")

        # 如果启用了保存diff内容，则保存每个分割后的块
        if self.save_diffs and file_path:
            for i, chunk in enumerate(chunks):
                chunk_path = f"{file_path}.chunk{i+1}"
                chunk_tokens = count_tokens(chunk, self.model_name)
                save_diff_content(chunk_path, chunk, len(chunk.split()) * 1.2, chunk_tokens)

        return chunks

    async def _evaluate_single_diff(self, diff_content: str) -> Dict[str, Any]:
        """Evaluate a single diff with improved rate limiting."""
        # 计算文件哈希值用于缓存
        file_hash = self._calculate_file_hash(diff_content)

        # 检查缓存
        if file_hash in self.cache:
            self.cache_hits += 1
            logger.info(f"Cache hit! Retrieved evaluation result from cache (hit rate: {self.cache_hits}/{len(self.cache) + self.cache_hits})")
            return self.cache[file_hash]

        # 检查文件大小，如果过大则分块处理
        words = diff_content.split()
        estimated_tokens = len(words) * 1.2

        # 如果文件可能超过模型的上下文限制，则分块处理
        if estimated_tokens > 12000:  # 留出一些空间给系统提示和其他内容
            chunks = self._split_diff_content(diff_content)

            # 分别评估每个块
            chunk_results = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Evaluating chunk {i+1}/{len(chunks)}")
                chunk_result = await self._evaluate_diff_chunk(chunk)
                chunk_results.append(chunk_result)

            # 合并结果
            merged_result = self._merge_chunk_results(chunk_results)

            # 缓存合并后的结果
            self.cache[file_hash] = merged_result
            return merged_result

        # 对于正常大小的文件，直接评估
        # 更智能地估算令牌数量 - 根据文件大小和复杂度调整系数
        complexity_factor = 1.2  # 基础系数

        # 如果文件很大，降低系数以避免过度估计
        if len(words) > 1000:
            complexity_factor = 1.0
        elif len(words) > 500:
            complexity_factor = 1.1

        estimated_tokens = len(words) * complexity_factor

        # 使用指数退避重试策略
        max_retries = 5
        retry_count = 0
        base_wait_time = 2  # 基础等待时间（秒）

        while retry_count < max_retries:
            try:
                # 获取令牌 - 使用改进的令牌桶算法
                wait_time = await self.token_bucket.get_tokens(estimated_tokens)
                if wait_time > 0:
                    logger.info(f"Rate limit: waiting {wait_time:.2f}s for token replenishment")
                    print(f"⏳ Rate limit: waiting {wait_time:.2f}s for token replenishment (current rate: {self.token_bucket.tokens_per_minute:.0f} tokens/min)")
                    # 不需要显式等待，因为令牌桶算法已经处理了等待

                # 确保请求之间有最小间隔，但使用更短的间隔
                now = time.time()
                time_since_last = now - self._last_request_time
                min_interval = max(0.5, self.MIN_REQUEST_INTERVAL - (wait_time / 2))  # 如果已经等待了一段时间，减少间隔
                if time_since_last < min_interval:
                    await asyncio.sleep(min_interval - time_since_last)

                # 发送请求到模型
                async with self.request_semaphore:
                    # 创建消息 - 使用优化的prompt
                    # 获取文件名和语言
                    file_name = "unknown"
                    language = "unknown"

                    # 尝试从diff内容中提取文件名
                    file_name_match = re.search(r'diff --git a/(.*?) b/', diff_content)
                    if file_name_match:
                        file_name = file_name_match.group(1)
                        # 猜测语言
                        language = self._guess_language(file_name)

                    # 清理代码内容，移除异常字符
                    sanitized_diff = self._sanitize_content(diff_content)

                    # 使用优化的代码评审prompt
                    review_prompt = CODE_REVIEW_PROMPT.format(
                        file_name=file_name,
                        language=language.lower(),
                        code_content=sanitized_diff
                    )

                    # 添加语言特定的考虑因素
                    language_key = language.lower()
                    if language_key in LANGUAGE_SPECIFIC_CONSIDERATIONS:
                        review_prompt += "\n\n" + LANGUAGE_SPECIFIC_CONSIDERATIONS[language_key]

                    # 添加工作时间估计请求
                    review_prompt += "\n\nIn addition to the code evaluation, please also estimate how many effective working hours an experienced programmer (5-10+ years) would need to complete these code changes. Include this estimate in your JSON response as 'estimated_hours'."

                    # 添加JSON输出指令
                    review_prompt += "\n\n" + self.json_output_instruction

                    messages = [
                        SystemMessage(content=self.system_prompt),
                        HumanMessage(content=review_prompt)
                    ]

                    # 调用模型
                    response = await self.model.agenerate(messages=[messages])
                    self._last_request_time = time.time()

                    # 获取响应文本
                    generated_text = response.generations[0][0].text

                # 解析响应
                try:
                    # 提取JSON
                    json_str = self._extract_json(generated_text)
                    if not json_str:
                        logger.warning("Failed to extract JSON from response, attempting to fix")
                        json_str = self._fix_malformed_json(generated_text)

                    if not json_str:
                        logger.error("Could not extract valid JSON from the response")
                        return self._generate_default_scores("JSON解析错误。原始响应: " + str(generated_text)[:500])

                    result = json.loads(json_str)

                    # 验证分数
                    scores = self._validate_scores(result)

                    # 请求成功，调整速率限制
                    self._adjust_rate_limits(is_rate_limited=False)

                    # 缓存结果
                    self.cache[file_hash] = scores

                    return scores

                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")
                    logger.error(f"Raw response: {generated_text}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        return self._generate_default_scores("JSON解析错误。原始响应: " + str(generated_text)[:500])
                    await asyncio.sleep(base_wait_time * (2 ** retry_count))  # 指数退避

            except Exception as e:
                error_message = str(e)
                logger.error(f"Evaluation error: {error_message}")

                # 检查是否是速率限制错误
                is_rate_limited = "rate limit" in error_message.lower() or "too many requests" in error_message.lower()

                if is_rate_limited:
                    self._adjust_rate_limits(is_rate_limited=True)
                    retry_count += 1
                    if retry_count >= max_retries:
                        return self._generate_default_scores(f"评价过程中遇到速率限制: {error_message}")
                    # 使用更长的等待时间
                    wait_time = base_wait_time * (2 ** retry_count)
                    logger.warning(f"Rate limit error, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    # 其他错误直接返回
                    return self._generate_default_scores(f"评价过程中出错: {error_message}")

        # 如果所有重试都失败
        return self._generate_default_scores("达到最大重试次数，评价失败")

    def _validate_scores(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize scores with enhanced format handling."""
        try:
            # 检查并处理不同格式的评分结果
            normalized_result = {}

            # 定义所有必需的字段
            required_fields = [
                "readability", "efficiency", "security", "structure",
                "error_handling", "documentation", "code_style", "overall_score", "comments", "estimated_hours"
            ]

            # 处理可能的不同格式
            # 格式1: {"readability": 8, "efficiency": 7, ...}
            # 格式2: {"score": {"readability": 8, "efficiency": 7, ...}}
            # 格式3: {"readability": {"score": 8}, "efficiency": {"score": 7}, ...}
            # 格式4: CODE_SUGGESTION 模板生成的格式，如 {"readability": 8.5, "efficiency_&_performance": 7.0, ...}

            # 检查是否有嵌套的评分结构
            if "score" in result and isinstance(result["score"], dict):
                # 格式2: 评分在 "score" 字段中
                score_data = result["score"]
                for field in required_fields:
                    if field in score_data:
                        normalized_result[field] = score_data[field]
                    elif field == "comments" and "evaluation" in result:
                        # 评论可能在外层的 "evaluation" 字段中
                        normalized_result["comments"] = result["evaluation"]
            else:
                # 检查格式3: 每个评分字段都是一个包含 "score" 的字典
                format3 = False
                for field in ["readability", "efficiency", "security"]:
                    if field in result and isinstance(result[field], dict) and "score" in result[field]:
                        format3 = True
                        break

                if format3:
                    # 格式3处理
                    for field in required_fields:
                        if field == "comments":
                            if "comments" in result:
                                normalized_result["comments"] = result["comments"]
                            elif "evaluation" in result:
                                normalized_result["comments"] = result["evaluation"]
                            else:
                                normalized_result["comments"] = "无评价意见"
                        elif field in result and isinstance(result[field], dict) and "score" in result[field]:
                            normalized_result[field] = result[field]["score"]
                else:
                    # 检查是否是 CODE_SUGGESTION 模板生成的格式
                    is_code_suggestion_format = False
                    if "efficiency_&_performance" in result or "final_overall_score" in result:
                        is_code_suggestion_format = True

                    if is_code_suggestion_format:
                        # 处理 CODE_SUGGESTION 模板生成的格式
                        field_mapping = {
                            "readability": "readability",
                            "efficiency_&_performance": "efficiency",
                            "efficiency": "efficiency",
                            "security": "security",
                            "structure_&_design": "structure",
                            "structure": "structure",
                            "error_handling": "error_handling",
                            "documentation_&_comments": "documentation",
                            "documentation": "documentation",
                            "code_style": "code_style",
                            "final_overall_score": "overall_score",
                            "overall_score": "overall_score",
                            "comments": "comments"
                        }

                        for source_field, target_field in field_mapping.items():
                            if source_field in result:
                                normalized_result[target_field] = result[source_field]
                    else:
                        # 格式1或其他格式，直接复制字段
                        for field in required_fields:
                            if field in result:
                                normalized_result[field] = result[field]

            # 确保所有必需字段都存在，如果缺少则使用默认值
            for field in required_fields:
                if field not in normalized_result:
                    if field == "comments":
                        # 尝试从其他可能的字段中获取评论
                        for alt_field in ["evaluation", "comment", "description", "feedback"]:
                            if alt_field in result:
                                normalized_result["comments"] = result[alt_field]
                                break
                        else:
                            normalized_result["comments"] = "无评价意见"

                # 处理嵌套的评论结构 - 无论是否在上面的循环中设置
                if field == "comments" and isinstance(normalized_result.get("comments"), dict):
                    # 如果评论是一个字典，尝试提取有用的信息并转换为字符串
                    comments_dict = normalized_result["comments"]
                    comments_str = ""

                    # 处理常见的嵌套结构
                    if "overall" in comments_dict and isinstance(comments_dict["overall"], dict) and "comment" in comments_dict["overall"]:
                        # 如果有overall评论，优先使用它
                        comments_str = comments_dict["overall"]["comment"]
                    else:
                        # 否则，尝试从各个评分字段中提取评论
                        for score_field in ["readability", "efficiency", "security", "structure", "error_handling", "documentation", "code_style"]:
                            if score_field in comments_dict and isinstance(comments_dict[score_field], dict) and "comment" in comments_dict[score_field]:
                                comments_str += f"{score_field.capitalize()}: {comments_dict[score_field]['comment']}\n"

                        # 如果没有找到任何评论，尝试直接将字典转换为字符串
                        if not comments_str:
                            try:
                                comments_str = json.dumps(comments_dict, ensure_ascii=False)
                            except:
                                comments_str = str(comments_dict)

                    normalized_result["comments"] = comments_str
                elif field == "overall_score":
                    # 如果缺少总分，计算其他分数的平均值
                    score_fields = ["readability", "efficiency", "security", "structure",
                                  "error_handling", "documentation", "code_style"]
                    available_scores = [normalized_result.get(f, 5) for f in score_fields if f in normalized_result]
                    if available_scores:
                        normalized_result["overall_score"] = round(sum(available_scores) / len(available_scores), 1)
                    else:
                        normalized_result["overall_score"] = 5.0
                else:
                    # 对于其他评分字段，使用默认值5
                    normalized_result[field] = 5

            # 确保分数在有效范围内
            score_fields = ["readability", "efficiency", "security", "structure",
                          "error_handling", "documentation", "code_style"]

            for field in score_fields:
                # 确保分数是整数并在1-10范围内
                try:
                    score = normalized_result[field]
                    if isinstance(score, str):
                        score = int(score.strip())
                    elif isinstance(score, float):
                        score = round(score)

                    normalized_result[field] = max(1, min(10, score))
                except (ValueError, TypeError):
                    normalized_result[field] = 5

            # 确保overall_score是浮点数并在1-10范围内
            try:
                overall = normalized_result["overall_score"]
                if isinstance(overall, str):
                    overall = float(overall.strip())

                normalized_result["overall_score"] = max(1.0, min(10.0, float(overall)))
            except (ValueError, TypeError):
                normalized_result["overall_score"] = 5.0

            # 检查所有分数是否相同，如果是，则稍微调整以增加差异性
            scores = [normalized_result[field] for field in score_fields]
            if len(set(scores)) <= 1:
                # 所有分数相同，添加一些随机变化
                for field in score_fields[:3]:  # 只修改前几个字段
                    adjustment = random.choice([-1, 1])
                    normalized_result[field] = max(1, min(10, normalized_result[field] + adjustment))

            # 确保comments字段是字符串类型
            if "comments" in normalized_result:
                if not isinstance(normalized_result["comments"], str):
                    try:
                        if isinstance(normalized_result["comments"], dict):
                            # 如果是字典，尝试提取有用的信息
                            comments_dict = normalized_result["comments"]
                            comments_str = ""

                            # 处理常见的嵌套结构
                            if "overall" in comments_dict and isinstance(comments_dict["overall"], dict) and "comment" in comments_dict["overall"]:
                                # 如果有overall评论，优先使用它
                                comments_str = comments_dict["overall"]["comment"]
                            else:
                                # 否则，尝试从各个评分字段中提取评论
                                for field in ["readability", "efficiency", "security", "structure", "error_handling", "documentation", "code_style"]:
                                    if field in comments_dict and isinstance(comments_dict[field], dict) and "comment" in comments_dict[field]:
                                        comments_str += f"{field.capitalize()}: {comments_dict[field]['comment']}\n"

                            # 如果没有找到任何评论，尝试直接将字典转换为字符串
                            if not comments_str:
                                comments_str = json.dumps(comments_dict, ensure_ascii=False)

                            normalized_result["comments"] = comments_str
                        else:
                            # 其他类型直接转换为字符串
                            normalized_result["comments"] = str(normalized_result["comments"])
                    except Exception as e:
                        logger.error(f"Error converting comments to string: {e}")
                        normalized_result["comments"] = f"评论转换错误: {str(e)}"

                # 确保评论不为空
                if not normalized_result["comments"]:
                    normalized_result["comments"] = "无评价意见"

            # 使用from_dict方法创建CodeEvaluation实例进行最终验证
            try:
                evaluation = CodeEvaluation.from_dict(normalized_result)
                return evaluation.model_dump()
            except Exception as e:
                logger.error(f"Error creating CodeEvaluation: {e}")
                logger.error(f"Normalized result: {normalized_result}")
                # 如果创建失败，返回一个安全的默认结果
                return self._generate_default_scores(f"验证失败: {str(e)}")
        except Exception as e:
            logger.error(f"Score validation error: {e}")
            logger.error(f"Original result: {result}")
            return self._generate_default_scores(f"分数验证错误: {str(e)}")

    def _generate_default_scores(self, error_message: str) -> Dict[str, Any]:
        """Generate default scores when evaluation fails."""
        return {
            "readability": 5,
            "efficiency": 5,
            "security": 5,
            "structure": 5,
            "error_handling": 5,
            "documentation": 5,
            "code_style": 5,
            "overall_score": 5.0,
            "estimated_hours": 0.0,
            "comments": error_message
        }

    def _estimate_default_hours(self, additions: int, deletions: int) -> float:
        """Estimate default working hours based on additions and deletions.

        Args:
            additions: Number of added lines
            deletions: Number of deleted lines

        Returns:
            float: Estimated working hours
        """
        # Base calculation: 1 hour per 100 lines of code (additions + deletions)
        total_changes = additions + deletions

        # Base time: minimum 0.25 hours (15 minutes) for any change
        base_time = 0.25

        if total_changes <= 10:
            # Very small changes: 15-30 minutes
            return base_time
        elif total_changes <= 50:
            # Small changes: 30 minutes to 1 hour
            return base_time + (total_changes - 10) * 0.015  # ~0.6 hours for 50 lines
        elif total_changes <= 200:
            # Medium changes: 1-3 hours
            return 0.6 + (total_changes - 50) * 0.016  # ~3 hours for 200 lines
        elif total_changes <= 500:
            # Large changes: 3-6 hours
            return 3.0 + (total_changes - 200) * 0.01  # ~6 hours for 500 lines
        else:
            # Very large changes: 6+ hours
            return 6.0 + (total_changes - 500) * 0.008  # +0.8 hours per 100 lines beyond 500

    def _guess_language(self, file_path: str) -> str:
        """根据文件扩展名猜测编程语言。

        Args:
            file_path: 文件路径

        Returns:
            str: 猜测的编程语言，与 CODE_SUGGESTION 模板中的语言标准匹配
        """
        file_ext = os.path.splitext(file_path)[1].lower()

        # 文件扩展名到语言的映射，与 CODE_SUGGESTION 模板中的语言标准匹配
        ext_to_lang = {
            # Python
            '.py': 'Python',
            '.pyx': 'Python',
            '.pyi': 'Python',
            '.ipynb': 'Python',

            # JavaScript/TypeScript
            '.js': 'JavaScript',
            '.jsx': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript',
            '.mjs': 'JavaScript',

            # Java
            '.java': 'Java',
            '.jar': 'Java',
            '.class': 'Java',

            # C/C++
            '.c': 'C',
            '.cpp': 'C++',
            '.h': 'C',
            '.hpp': 'C++',

            # C#
            '.cs': 'C#',

            # Go
            '.go': 'Go',

            # Ruby
            '.rb': 'Ruby',
            '.erb': 'Ruby',

            # PHP
            '.php': 'PHP',
            '.phtml': 'PHP',

            # Swift
            '.swift': 'Swift',

            # Kotlin
            '.kt': 'Kotlin',
            '.kts': 'Kotlin',

            # Rust
            '.rs': 'Rust',

            # HTML/CSS
            '.html': 'HTML',
            '.htm': 'HTML',
            '.xhtml': 'HTML',
            '.css': 'CSS',
            '.scss': 'CSS',
            '.sass': 'CSS',
            '.less': 'CSS',

            # Shell
            '.sh': 'Shell',
            '.bash': 'Shell',
            '.zsh': 'Shell',

            # SQL
            '.sql': 'SQL',

            # 其他常见文件类型
            '.scala': 'General',
            '.hs': 'General',
            '.md': 'General',
            '.json': 'General',
            '.xml': 'General',
            '.yaml': 'General',
            '.yml': 'General',
            '.toml': 'General',
            '.ini': 'General',
            '.config': 'General',
            '.gradle': 'General',
            '.tf': 'General',
        }

        # 如果扩展名在映射中，返回对应的语言
        if file_ext in ext_to_lang:
            return ext_to_lang[file_ext]

        # 对于特殊文件名的处理
        filename = os.path.basename(file_path).lower()
        if filename == 'dockerfile':
            return 'General'
        elif filename.startswith('docker-compose'):
            return 'General'
        elif filename.startswith('makefile'):
            return 'General'
        elif filename == '.gitignore':
            return 'General'

        # 默认返回通用编程语言
        return 'General'

    def _sanitize_content(self, content: str) -> str:
        """清理内容中的异常字符，确保内容可以安全地发送到OpenAI API。

        Args:
            content: 原始内容

        Returns:
            str: 清理后的内容
        """
        if not content:
            return ""

        try:
            # 检查是否包含Base64编码的内容
            if len(content) > 20 and content.strip().endswith('==') and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in content.strip()):
                print(f"DEBUG: Detected possible Base64 encoded content: '{content[:20]}...'")
                return "这是一段Base64编码的内容，无法进行代码评估。"

            # 移除不可打印字符和控制字符，但保留基本空白字符（空格、换行、制表符）
            sanitized = ""
            for char in content:
                # 保留基本可打印字符和常用空白字符
                if char.isprintable() or char in [' ', '\n', '\t', '\r']:
                    sanitized += char
                else:
                    # 替换不可打印字符为空格
                    sanitized += ' '

            # 如果清理后的内容太短，返回一个提示
            if len(sanitized.strip()) < 10:
                return "代码内容太短或为空，无法进行有效评估。"

            return sanitized
        except Exception as e:
            print(f"DEBUG: Error sanitizing content: {e}")
            # 如果清理过程出错，返回一个安全的默认字符串
            return "内容清理过程中出错，无法处理。"

    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON部分。

        Args:
            text: 原始文本

        Returns:
            str: 提取的JSON字符串，如果没有找到则返回空字符串
        """
        # 检查输入是否为空或None
        if not text:
            logger.warning("Empty response received from API")
            print("DEBUG: Empty response received from API")
            return ""

        # 打印原始文本的类型和长度
        print(f"DEBUG: Response type: {type(text)}, length: {len(text)}")
        print(f"DEBUG: First 100 chars: '{text[:100]}'")

        # 检查是否包含无法评估的提示（如Base64编码内容）
        unevaluable_patterns = [
            r'Base64编码',
            r'无法解码的字符串',
            r'ICAgIA==',
            r'无法评估',
            r'无法对这段代码进行评审',
            r'无法进行评价',
            r'无法对代码进行评估',
            r'代码内容太短',
            r'代码为空',
            r'没有提供实际的代码',
            r'无法理解',
            r'无法解析',
            r'无法分析',
            r'无法读取',
            r'无法识别',
            r'无法处理',
            r'无效的代码',
            r'不是有效的代码',
            r'不是代码',
            r'不包含代码',
            r'只包含了一个无法解码的字符串'
        ]

        for pattern in unevaluable_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                print(f"DEBUG: Detected response indicating unevaluable content: '{pattern}'")
                # 提取评论，如果有的话
                comment = text[:200] if len(text) > 200 else text
                # 创建一个默认的JSON响应
                default_json = {
                    "readability": 5,
                    "efficiency": 5,
                    "security": 5,
                    "structure": 5,
                    "error_handling": 5,
                    "documentation": 5,
                    "code_style": 5,
                    "overall_score": 5.0,
                    "comments": f"无法评估代码: {comment}"
                }
                return json.dumps(default_json)

        # 尝试查找JSON代码块
        json_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', text)
        if json_match:
            return json_match.group(1)

        # 尝试直接查找JSON对象
        json_pattern = r'({[\s\S]*?"readability"[\s\S]*?"efficiency"[\s\S]*?"security"[\s\S]*?"structure"[\s\S]*?"error_handling"[\s\S]*?"documentation"[\s\S]*?"code_style"[\s\S]*?"overall_score"[\s\S]*?"comments"[\s\S]*?})'
        json_match = re.search(json_pattern, text)
        if json_match:
            return json_match.group(1)

        # 尝试提取 CODE_SUGGESTION 模板生成的评分部分
        scores_section = re.search(r'### SCORES:\s*\n([\s\S]*?)(?:\n\n|\Z)', text)
        if scores_section:
            scores_text = scores_section.group(1)
            scores_dict = {}

            # 提取各个评分
            for line in scores_text.split('\n'):
                match = re.search(r'- ([\w\s&]+):\s*(\d+(\.\d+)?)\s*/10', line)
                if match:
                    key = match.group(1).strip().lower().replace(' & ', '_').replace(' ', '_')
                    value = float(match.group(2))
                    scores_dict[key] = value

            # 提取评论部分
            analysis_match = re.search(r'## Detailed Code Analysis\s*\n([\s\S]*?)(?:\n##|\Z)', text)
            if analysis_match:
                scores_dict['comments'] = analysis_match.group(1).strip()
            else:
                # 尝试提取改进建议部分
                improvement_match = re.search(r'## Improvement Recommendations\s*\n([\s\S]*?)(?:\n##|\Z)', text)
                if improvement_match:
                    scores_dict['comments'] = improvement_match.group(1).strip()
                else:
                    scores_dict['comments'] = "No detailed analysis provided."

            # 转换为 JSON 字符串
            if scores_dict and len(scores_dict) >= 8:  # 至少包含7个评分项和评论
                return json.dumps(scores_dict)

        # 尝试查找任何可能的JSON对象
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return text[start_idx:end_idx+1]

        # 尝试提取评分信息，即使没有完整的JSON结构
        scores_dict = {}

        # 查找评分模式，如 "Readability: 8/10" 或 "Readability score: 8"
        score_patterns = [
            r'(readability|efficiency|security|structure|error handling|documentation|code style):\s*(\d+)(?:/10)?',
            r'(readability|efficiency|security|structure|error handling|documentation|code style) score:\s*(\d+)',
        ]

        for pattern in score_patterns:
            for match in re.finditer(pattern, text.lower()):
                key = match.group(1).replace(' ', '_')
                value = int(match.group(2))
                scores_dict[key] = value

        # 如果找到了至少4个评分，认为是有效的评分信息
        if len(scores_dict) >= 4:
            # 填充缺失的评分
            for field in ["readability", "efficiency", "security", "structure", "error_handling", "documentation", "code_style"]:
                if field not in scores_dict:
                    scores_dict[field] = 5  # 默认分数

            # 计算总分
            scores_dict["overall_score"] = round(sum(scores_dict.values()) / len(scores_dict), 1)

            # 提取评论
            comment_match = re.search(r'(comments|summary|analysis|evaluation):(.*?)(?=\n\w+:|$)', text.lower(), re.DOTALL)
            if comment_match:
                scores_dict["comments"] = comment_match.group(2).strip()
            else:
                # 使用整个文本作为评论，但限制长度
                scores_dict["comments"] = text[:500] + "..." if len(text) > 500 else text

            return json.dumps(scores_dict)

        return ""

    def _fix_malformed_json(self, json_str: str) -> str:
        """尝试修复格式不正确的JSON字符串。

        Args:
            json_str: 可能格式不正确的JSON字符串

        Returns:
            str: 修复后的JSON字符串，如果无法修复则返回空字符串
        """
        # 检查输入是否为空或None
        if not json_str:
            logger.warning("Empty string passed to _fix_malformed_json")
            # 创建一个默认的JSON
            default_scores = {
                "readability": 5,
                "efficiency": 5,
                "security": 5,
                "structure": 5,
                "error_handling": 5,
                "documentation": 5,
                "code_style": 5,
                "overall_score": 5.0,
                "estimated_hours": 0.0,
                "comments": "API返回空响应，显示默认分数。"
            }
            return json.dumps(default_scores)

        # 检查是否是错误消息而不是JSON
        error_patterns = [
            "I'm sorry",
            "there is no code",
            "please provide",
            "cannot review",
            "unable to"
        ]

        for pattern in error_patterns:
            if pattern.lower() in json_str.lower():
                logger.warning(f"API returned an error message: {json_str[:100]}...")
                print(f"DEBUG: API returned an error message: {json_str[:100]}...")
                # 创建一个默认的JSON，包含错误消息
                default_scores = {
                    "readability": 5,
                    "efficiency": 5,
                    "security": 5,
                    "structure": 5,
                    "error_handling": 5,
                    "documentation": 5,
                    "code_style": 5,
                    "overall_score": 5.0,
                    "estimated_hours": 0.0,
                    "comments": f"API返回错误消息: {json_str[:200]}..."
                }
                return json.dumps(default_scores)

        original_json = json_str  # 保存原始字符串以便比较

        try:
            # 基本清理
            json_str = json_str.replace("'", '"')  # 单引号替换为双引号
            json_str = re.sub(r',\s*}', '}', json_str)  # 移除结尾的逗号
            json_str = re.sub(r',\s*]', ']', json_str)  # 移除数组结尾的逗号

            # 添加缺失的引号
            json_str = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', json_str)  # 给键添加引号

            # 修复缺失的逗号
            json_str = re.sub(r'("\w+":\s*\d+|"\w+":\s*"[^"]*"|"\w+":\s*true|"\w+":\s*false|"\w+":\s*null)\s*("\w+")', r'\1,\2', json_str)

            # 尝试解析清理后的JSON
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError as e:
            error_msg = str(e)
            logger.warning(f"第一次尝试修复JSON失败: {error_msg}")

            # 如果错误与分隔符相关，尝试修复
            if "delimiter" in error_msg or "Expecting ',' delimiter" in error_msg:
                try:
                    # 获取错误位置
                    pos = e.pos
                    # 在错误位置插入逗号
                    json_str = json_str[:pos] + "," + json_str[pos:]

                    # 再次尝试
                    json.loads(json_str)
                    return json_str
                except (json.JSONDecodeError, IndexError):
                    pass

            # 尝试查找任何可能的JSON对象
            json_pattern = r'{[\s\S]*?}'
            json_matches = re.findall(json_pattern, original_json)

            if json_matches:
                # 尝试每个匹配的JSON对象
                for potential_json in json_matches:
                    try:
                        # 尝试解析
                        json.loads(potential_json)
                        return potential_json
                    except json.JSONDecodeError:
                        # 尝试基本清理
                        cleaned_json = potential_json.replace("'", '"')
                        cleaned_json = re.sub(r',\s*}', '}', cleaned_json)
                        cleaned_json = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', cleaned_json)

                        try:
                            json.loads(cleaned_json)
                            return cleaned_json
                        except json.JSONDecodeError:
                            continue

            # 尝试提取分数并创建最小可用的JSON
            try:
                # 提取分数
                scores = {}
                for field in ["readability", "efficiency", "security", "structure", "error_handling", "documentation", "code_style"]:
                    # 尝试多种模式匹配
                    patterns = [
                        f'"{field}"\\s*:\\s*(\\d+)',  # "field": 8
                        f'{field}\\s*:\\s*(\\d+)',    # field: 8
                        f'{field.replace("_", " ")}\\s*:\\s*(\\d+)',  # field name: 8
                        f'{field.capitalize()}\\s*:\\s*(\\d+)',  # Field: 8
                        f'{field.replace("_", " ").title()}\\s*:\\s*(\\d+)'  # Field Name: 8
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, original_json, re.IGNORECASE)
                        if match:
                            scores[field] = int(match.group(1))
                            break

                    if field not in scores:
                        scores[field] = 5  # 默认分数

                # 尝试提取总分
                overall_patterns = [
                    r'"overall_score"\s*:\s*(\d+(?:\.\d+)?)',
                    r'overall_score\s*:\s*(\d+(?:\.\d+)?)',
                    r'overall\s*:\s*(\d+(?:\.\d+)?)',
                    r'总分\s*:\s*(\d+(?:\.\d+)?)'
                ]

                for pattern in overall_patterns:
                    overall_match = re.search(pattern, original_json, re.IGNORECASE)
                    if overall_match:
                        scores["overall_score"] = float(overall_match.group(1))
                        break

                if "overall_score" not in scores:
                    # 计算总分为其他分数的平均值
                    scores["overall_score"] = round(sum(scores.values()) / len(scores), 1)

                # 尝试提取评论
                comment_patterns = [
                    r'"comments"\s*:\s*"(.*?)"',
                    r'comments\s*:\s*(.*?)(?=\n\w+:|$)',
                    r'评价\s*:\s*(.*?)(?=\n\w+:|$)',
                    r'建议\s*:\s*(.*?)(?=\n\w+:|$)'
                ]

                for pattern in comment_patterns:
                    comment_match = re.search(pattern, original_json, re.DOTALL | re.IGNORECASE)
                    if comment_match:
                        scores["comments"] = comment_match.group(1).strip()
                        break

                if "comments" not in scores:
                    # 使用原始文本的一部分作为评论
                    scores["comments"] = "JSON解析错误，显示提取的分数。原始响应: " + original_json[:200] + "..."

                # 转换为JSON字符串
                return json.dumps(scores)
            except Exception as final_e:
                logger.error(f"所有JSON修复尝试失败: {final_e}")
                logger.error(f"原始响应: {original_json[:500]}")
                print(f"无法修复JSON: {e} -> {final_e}")

                # 最后尝试：创建一个默认的JSON
                default_scores = {
                    "readability": 5,
                    "efficiency": 5,
                    "security": 5,
                    "structure": 5,
                    "error_handling": 5,
                    "documentation": 5,
                    "code_style": 5,
                    "overall_score": 5.0,
                    "estimated_hours": 0.0,
                    "comments": f"JSON解析错误，显示默认分数。错误: {str(e)}"
                }
                return json.dumps(default_scores)

            return ""

    async def _evaluate_diff_chunk(self, chunk: str) -> Dict[str, Any]:
        """评估单个差异块

        Args:
            chunk: 差异内容块

        Returns:
            Dict[str, Any]: 评估结果
        """
        # 使用指数退避重试策略
        max_retries = 5
        retry_count = 0
        base_wait_time = 2  # 基础等待时间（秒）

        # 更智能地估算令牌数量
        words = chunk.split()
        complexity_factor = 1.2
        if len(words) > 1000:
            complexity_factor = 1.0
        elif len(words) > 500:
            complexity_factor = 1.1

        estimated_tokens = len(words) * complexity_factor

        while retry_count < max_retries:
            try:
                # 获取令牌
                wait_time = await self.token_bucket.get_tokens(estimated_tokens)
                if wait_time > 0:
                    logger.info(f"Rate limit: waiting {wait_time:.2f}s for token replenishment")
                    await asyncio.sleep(wait_time)

                # 确保请求之间有最小间隔
                now = time.time()
                time_since_last = now - self._last_request_time
                if time_since_last < self.MIN_REQUEST_INTERVAL:
                    await asyncio.sleep(self.MIN_REQUEST_INTERVAL - time_since_last)

                # 发送请求到模型
                async with self.request_semaphore:
                    # 创建消息 - 使用优化的prompt
                    # 获取文件名和语言
                    file_name = "unknown"
                    language = "unknown"

                    # 尝试从diff内容中提取文件名
                    file_name_match = re.search(r'diff --git a/(.*?) b/', chunk)
                    if file_name_match:
                        file_name = file_name_match.group(1)
                        # 猜测语言
                        language = self._guess_language(file_name)

                    # 使用更详细的代码评审prompt，确保模型理解任务
                    # 清理代码内容，移除异常字符
                    sanitized_chunk = self._sanitize_content(chunk)

                    review_prompt = f"""请评价以下代码：

文件名：{file_name}
语言：{language}

```
{sanitized_chunk}
```

请对这段代码进行全面评价，并给出1-10分的评分（10分为最高）。评价应包括以下几个方面：
1. 可读性 (readability)：代码是否易于阅读和理解
2. 效率 (efficiency)：代码是否高效，是否有性能问题
3. 安全性 (security)：代码是否存在安全隐患
4. 结构 (structure)：代码结构是否合理，是否遵循良好的设计原则
5. 错误处理 (error_handling)：是否有适当的错误处理机制
6. 文档和注释 (documentation)：注释是否充分，是否有必要的文档
7. 代码风格 (code_style)：是否遵循一致的代码风格和最佳实践
8. 总体评分 (overall_score)：综合以上各项的总体评价

请以JSON格式返回结果，格式如下：
```json
{{
  "readability": 评分,
  "efficiency": 评分,
  "security": 评分,
  "structure": 评分,
  "error_handling": 评分,
  "documentation": 评分,
  "code_style": 评分,
  "overall_score": 总评分,
  "comments": "详细评价意见和改进建议"
}}
```

总评分应该是所有评分的加权平均值，保留一位小数。如果代码很小或者只是配置文件的修改，请根据实际情况给出合理的评分。

重要提示：请确保返回有效的JSON格式。如果无法评估代码（例如代码不完整或无法理解），请仍然返回JSON格式，但在comments中说明原因，并给出默认评分5分。"""

                    # 打印完整的代码块用于调试
                    print(f"DEBUG: File name: {file_name}")
                    print(f"DEBUG: Language: {language}")
                    print(f"DEBUG: Code chunk length: {len(chunk)}")
                    print(f"DEBUG: Code chunk first 100 chars: '{chunk[:100]}'")
                    if len(chunk) < 10:
                        print(f"DEBUG: EMPTY CODE CHUNK: '{chunk}'")
                    elif len(chunk) < 100:
                        print(f"DEBUG: FULL CODE CHUNK: '{chunk}'")

                    # 如果代码块为空或太短，使用默认评分
                    if len(chunk.strip()) < 10:
                        print("DEBUG: Code chunk is too short, using default scores")
                        default_scores = {
                            "readability": 5,
                            "efficiency": 5,
                            "security": 5,
                            "structure": 5,
                            "error_handling": 5,
                            "documentation": 5,
                            "code_style": 5,
                            "overall_score": 5.0,
                            "estimated_hours": 0.25,  # Minimum 15 minutes for any change
                            "comments": f"无法评估代码，因为代码块为空或太短: '{chunk}'"
                        }
                        return default_scores

                    # 检查是否包含Base64编码的内容
                    if chunk.strip().endswith('==') and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in chunk.strip()):
                        print(f"DEBUG: Detected possible Base64 encoded content in chunk")
                        default_scores = {
                            "readability": 5,
                            "efficiency": 5,
                            "security": 5,
                            "structure": 5,
                            "error_handling": 5,
                            "documentation": 5,
                            "code_style": 5,
                            "overall_score": 5.0,
                            "estimated_hours": 0.25,  # Minimum 15 minutes for any change
                            "comments": f"无法评估代码，因为内容可能是Base64编码: '{chunk[:50]}...'"
                        }
                        return default_scores

                    messages = [
                        SystemMessage(content=self.system_prompt),
                        HumanMessage(content=review_prompt)
                    ]

                    # 打印用户输入内容的前100个字符用于调试
                    user_message = messages[1].content if len(messages) > 1 else "No user message"
                    print(f"DEBUG: User input first 100 chars: '{user_message[:100]}...'")
                    print(f"DEBUG: User input length: {len(user_message)}")

                    # 调用模型
                    response = await self.model.agenerate(messages=[messages])
                    self._last_request_time = time.time()

                    # 获取响应文本
                    generated_text = response.generations[0][0].text

                    # 打印原始响应用于调试
                    print(f"\n==== RAW OPENAI RESPONSE ====\n{generated_text}\n==== END RESPONSE ====\n")

                # 解析响应
                try:
                    # 提取JSON
                    json_str = self._extract_json(generated_text)
                    if not json_str:
                        logger.warning("Failed to extract JSON from response, attempting to fix")
                        json_str = self._fix_malformed_json(generated_text)

                    if not json_str:
                        logger.error("Could not extract valid JSON from the response")
                        return self._generate_default_scores("JSON解析错误。原始响应: " + str(generated_text)[:500])

                    result = json.loads(json_str)

                    # 验证分数
                    scores = self._validate_scores(result)

                    # 请求成功，调整速率限制
                    self._adjust_rate_limits(is_rate_limited=False)

                    return scores

                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")
                    logger.error(f"Raw response: {generated_text}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        return self._generate_default_scores("JSON解析错误。原始响应: " + str(generated_text)[:500])
                    await asyncio.sleep(base_wait_time * (2 ** retry_count))  # 指数退避

            except Exception as e:
                error_message = str(e)
                logger.error(f"Evaluation error: {error_message}")

                # 检查是否是速率限制错误
                is_rate_limited = "rate limit" in error_message.lower() or "too many requests" in error_message.lower()

                # 检查是否是上下文长度限制错误
                is_context_length_error = "context length" in error_message.lower() or "maximum context length" in error_message.lower()

                # 检查是否是DeepSeek API错误
                is_deepseek_error = "deepseek" in error_message.lower() or "deepseek api" in error_message.lower()

                if is_context_length_error:
                    # 如果是上下文长度错误，尝试进一步分割
                    logger.warning(f"Context length limit error, attempting further content splitting")
                    smaller_chunks = self._split_diff_content(chunk, max_tokens_per_chunk=4000)  # 使用更小的块大小

                    if len(smaller_chunks) > 1:
                        # 如果成功分割成多个小块，分别评估并合并结果
                        sub_results = []
                        for i, sub_chunk in enumerate(smaller_chunks):
                            logger.info(f"Evaluating sub-chunk {i+1}/{len(smaller_chunks)}")
                            sub_result = await self._evaluate_diff_chunk(sub_chunk)  # 递归调用
                            sub_results.append(sub_result)

                        return self._merge_chunk_results(sub_results)
                    else:
                        # 如果无法进一步分割，返回默认评分
                        return self._generate_default_scores(f"文件过大，无法进行评估: {error_message}")
                elif is_rate_limited:
                    self._adjust_rate_limits(is_rate_limited=True)
                    retry_count += 1
                    if retry_count >= max_retries:
                        return self._generate_default_scores(f"评价过程中遇到速率限制: {error_message}")
                    # 使用更长的等待时间
                    wait_time = base_wait_time * (2 ** retry_count)
                    logger.warning(f"Rate limit error, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(wait_time)
                elif is_deepseek_error:
                    # 对于DeepSeek API错误，最多重试两次，然后放弃
                    retry_count += 1
                    if retry_count >= 2:  # 只重试两次
                        logger.error(f"DeepSeek API error after 2 retries, abandoning evaluation: {error_message}")
                        return self._generate_default_scores(f"DeepSeek API错误，放弃评估: {error_message}")
                    # 使用较短的等待时间
                    wait_time = 3  # 固定3秒等待时间
                    logger.warning(f"DeepSeek API error, retrying in {wait_time}s (attempt {retry_count}/2)")
                    await asyncio.sleep(wait_time)
                else:
                    # 其他错误直接返回
                    return self._generate_default_scores(f"评价过程中出错: {error_message}")

        # 如果所有重试都失败
        return self._generate_default_scores("达到最大重试次数，评价失败")

    def _merge_chunk_results(self, chunk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并多个块的评估结果

        Args:
            chunk_results: 多个块的评估结果列表

        Returns:
            Dict[str, Any]: 合并后的评估结果
        """
        if not chunk_results:
            return self._generate_default_scores("没有可用的块评估结果")

        if len(chunk_results) == 1:
            return chunk_results[0]

        # 计算各个维度的平均分数
        score_fields = ["readability", "efficiency", "security", "structure",
                       "error_handling", "documentation", "code_style"]

        merged_scores = {}
        for field in score_fields:
            scores = [result.get(field, 5) for result in chunk_results]
            merged_scores[field] = round(sum(scores) / len(scores))

        # 计算总分
        overall_scores = [result.get("overall_score", 5.0) for result in chunk_results]
        merged_scores["overall_score"] = round(sum(overall_scores) / len(overall_scores), 1)

        # 计算估计工作时间 - 累加所有块的工作时间
        estimated_hours = sum(result.get("estimated_hours", 0.0) for result in chunk_results)
        # 应用一个折扣因子，因为并行处理多个块通常比顺序处理更有效率
        discount_factor = 0.8 if len(chunk_results) > 1 else 1.0
        merged_scores["estimated_hours"] = round(estimated_hours * discount_factor, 1)

        # 合并评价意见
        comments = []
        for i, result in enumerate(chunk_results):
            comment = result.get("comments", "")
            if comment:
                comments.append(f"[块 {i+1}] {comment}")

        # 如果评价意见太长，只保留前几个块的评价
        if len(comments) > 3:
            merged_comments = "\n\n".join(comments[:3]) + f"\n\n[共 {len(comments)} 个块的评价，只显示前3个块]"
        else:
            merged_comments = "\n\n".join(comments)

        merged_scores["comments"] = merged_comments or "文件分块评估，无详细评价意见。"

        return merged_scores

    async def evaluate_commit_file(
        self,
        file_path: str,
        file_diff: str,
        file_status: str = "M",
        additions: int = 0,
        deletions: int = 0,
    ) -> Dict[str, Any]:
        """
        评价单个文件的代码差异（新版本，用于commit评估）

        Args:
            file_path: 文件路径
            file_diff: 文件差异内容
            file_status: 文件状态（A=添加，M=修改，D=删除）
            additions: 添加的行数
            deletions: 删除的行数

        Returns:
            Dict[str, Any]: 文件评价结果字典，包含估计的工作时间
        """
        logger.info(f"Evaluating file: {file_path} (status: {file_status}, additions: {additions}, deletions: {deletions})")
        logger.debug(f"File diff size: {len(file_diff)} characters")
        # 如果未设置语言，根据文件扩展名猜测语言
        language = self._guess_language(file_path)
        logger.info(f"Detected language for {file_path}: {language}")

        # 清理代码内容，移除异常字符
        sanitized_diff = self._sanitize_content(file_diff)
        logger.debug(f"Sanitized diff size: {len(sanitized_diff)} characters")

        # 检查文件大小，如果过大则分块处理
        words = sanitized_diff.split()
        estimated_tokens = len(words) * 1.2
        logger.info(f"Estimated tokens for {file_path}: {estimated_tokens:.0f}")

        # 如果文件可能超过模型的上下文限制，则分块处理
        if estimated_tokens > 12000:  # 留出一些空间给系统提示和其他内容
            logger.info(f"File {file_path} is too large (estimated {estimated_tokens:.0f} tokens), will be processed in chunks")
            chunks = self._split_diff_content(sanitized_diff)
            logger.info(f"Split file into {len(chunks)} chunks")
            print(f"ℹ️ File too large, will be processed in {len(chunks)} chunks")

            # 分别评估每个块
            chunk_results = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Evaluating chunk {i+1}/{len(chunks)} of {file_path}")
                logger.debug(f"Chunk {i+1} size: {len(chunk)} characters, ~{len(chunk.split())} words")
                start_time = time.time()
                chunk_result = await self._evaluate_diff_chunk(chunk)
                end_time = time.time()
                logger.info(f"Chunk {i+1} evaluation completed in {end_time - start_time:.2f} seconds")
                chunk_results.append(chunk_result)

            # 合并结果
            logger.info(f"Merging {len(chunk_results)} chunk results for {file_path}")
            merged_result = self._merge_chunk_results(chunk_results)
            logger.info(f"Merged result: overall score {merged_result.get('overall_score', 'N/A')}")

            # 添加文件信息
            result = {
                "path": file_path,
                "status": file_status,
                "additions": additions,
                "deletions": deletions,
                "readability": merged_result["readability"],
                "efficiency": merged_result["efficiency"],
                "security": merged_result["security"],
                "structure": merged_result["structure"],
                "error_handling": merged_result["error_handling"],
                "documentation": merged_result["documentation"],
                "code_style": merged_result["code_style"],
                "overall_score": merged_result["overall_score"],
                "summary": merged_result["comments"][:100] + "..." if len(merged_result["comments"]) > 100 else merged_result["comments"],
                "comments": merged_result["comments"]
            }

            return result

        # 使用 grimoire 中的 CODE_SUGGESTION 模板
        # 将模板中的占位符替换为实际值
        prompt = CODE_SUGGESTION.format(
            language=language,
            name=file_path,
            content=sanitized_diff
        )
        logger.info(f"Preparing prompt for {file_path} with language: {language}")
        logger.debug(f"Prompt size: {len(prompt)} characters")

        try:
            # 发送请求到模型
            messages = [
                HumanMessage(content=prompt)
            ]

            # 打印用户输入内容的前20个字符用于调试
            user_message = messages[0].content if len(messages) > 0 else "No user message"
            logger.debug(f"User input first 20 chars: '{user_message[:20]}...'")
            print(f"DEBUG: User input first 20 chars: '{user_message[:20]}...'")

            logger.info(f"Sending request to model for {file_path}")
            start_time = time.time()
            response = await self.model.agenerate(messages=[messages])
            end_time = time.time()
            logger.info(f"Model response received in {end_time - start_time:.2f} seconds")

            generated_text = response.generations[0][0].text
            logger.debug(f"Response size: {len(generated_text)} characters")

            # 打印原始响应用于调试
            logger.debug(f"Raw model response (first 200 chars): {generated_text[:200]}...")
            print(f"\n==== RAW OPENAI RESPONSE ====\n{generated_text[:200]}...\n==== END RESPONSE ====\n")

            # 尝试提取JSON部分
            logger.info(f"Extracting JSON from response for {file_path}")
            json_str = self._extract_json(generated_text)
            if not json_str:
                logger.warning(f"Failed to extract JSON from response for {file_path}, attempting to fix")
                json_str = self._fix_malformed_json(generated_text)
                if json_str:
                    logger.info("Successfully fixed malformed JSON")
                else:
                    logger.warning("Failed to fix malformed JSON")

            if not json_str:
                logger.error(f"Could not extract valid JSON from the response for {file_path}")
                # 创建默认评价
                logger.info("Generating default scores")
                eval_data = self._generate_default_scores(f"解析错误。原始响应: {generated_text[:500]}...")
                logger.debug(f"Default scores: {eval_data}")
            else:
                # 解析JSON
                try:
                    logger.info(f"Parsing JSON for {file_path}")
                    logger.debug(f"JSON string: {json_str[:200]}...")
                    eval_data = json.loads(json_str)
                    logger.info(f"Successfully parsed JSON for {file_path}")

                    # 确保所有必要字段存在
                    required_fields = ["readability", "efficiency", "security", "structure",
                                      "error_handling", "documentation", "code_style", "overall_score", "comments"]
                    missing_fields = []
                    for field in required_fields:
                        if field not in eval_data:
                            if field != "overall_score":  # overall_score可以计算得出
                                missing_fields.append(field)
                                logger.warning(f"Missing field {field} in evaluation for {file_path}, setting default value")
                                eval_data[field] = 5

                    if missing_fields:
                        logger.warning(f"Missing fields in evaluation for {file_path}: {', '.join(missing_fields)}")

                    # 如果没有提供overall_score，计算一个
                    if "overall_score" not in eval_data or not eval_data["overall_score"]:
                        logger.info(f"Calculating overall score for {file_path}")
                        score_fields = ["readability", "efficiency", "security", "structure",
                                       "error_handling", "documentation", "code_style"]
                        scores = [eval_data.get(field, 5) for field in score_fields]
                        eval_data["overall_score"] = round(sum(scores) / len(scores), 1)
                        logger.info(f"Calculated overall score: {eval_data['overall_score']}")

                    # Log all scores
                    logger.info(f"Evaluation scores for {file_path}: " +
                               f"readability={eval_data.get('readability', 'N/A')}, " +
                               f"efficiency={eval_data.get('efficiency', 'N/A')}, " +
                               f"security={eval_data.get('security', 'N/A')}, " +
                               f"structure={eval_data.get('structure', 'N/A')}, " +
                               f"error_handling={eval_data.get('error_handling', 'N/A')}, " +
                               f"documentation={eval_data.get('documentation', 'N/A')}, " +
                               f"code_style={eval_data.get('code_style', 'N/A')}, " +
                               f"overall_score={eval_data.get('overall_score', 'N/A')}")

                except Exception as e:
                    logger.error(f"Error parsing evaluation for {file_path}: {e}", exc_info=True)
                    logger.debug(f"JSON string that caused the error: {json_str[:500]}...")
                    eval_data = self._generate_default_scores(f"解析错误。原始响应: {generated_text[:500]}...")
                    logger.debug(f"Default scores: {eval_data}")
        except Exception as e:
            logger.error(f"Error during evaluation: {e}")
            eval_data = self._generate_default_scores(f"评价过程中出错: {str(e)}")

        # 确保分数不全是相同的，如果发现全是相同的评分，增加一些微小差异
        scores = [eval_data["readability"], eval_data["efficiency"], eval_data["security"],
                 eval_data["structure"], eval_data["error_handling"], eval_data["documentation"], eval_data["code_style"]]

        # 检查是否所有分数都相同，或者是否有超过75%的分数相同（例如5个3分，1个4分）
        score_counts = {}
        for score in scores:
            score_counts[score] = score_counts.get(score, 0) + 1

        most_common_score = max(score_counts, key=score_counts.get)
        most_common_count = score_counts[most_common_score]

        # 如果所有分数都相同，或者大部分分数相同，则根据文件类型调整分数
        if most_common_count >= 5:  # 如果至少5个分数相同
            logger.warning(f"Most scores are identical ({most_common_score}, count: {most_common_count}), adjusting for variety")
            print(f"检测到评分缺乏差异性 ({most_common_score}，{most_common_count}个相同)，正在调整评分使其更具差异性")

            # 根据文件扩展名和内容进行智能评分调整
            file_ext = os.path.splitext(file_path)[1].lower()

            # 设置基础分数
            base_scores = {
                "readability": most_common_score,
                "efficiency": most_common_score,
                "security": most_common_score,
                "structure": most_common_score,
                "error_handling": most_common_score,
                "documentation": most_common_score,
                "code_style": most_common_score
            }

            # 根据文件类型调整分数
            if file_ext in ['.py', '.js', '.ts', '.java', '.cs', '.cpp', '.c']:
                # 代码文件根据路径和名称进行评分调整
                if 'test' in file_path.lower():
                    # 测试文件通常:
                    # - 结构设计很重要
                    # - 但可能文档/注释稍差
                    # - 安全性通常不是重点
                    base_scores["structure"] = min(10, most_common_score + 2)
                    base_scores["documentation"] = max(1, most_common_score - 1)
                    base_scores["security"] = max(1, most_common_score - 1)
                elif 'util' in file_path.lower() or 'helper' in file_path.lower():
                    # 工具类文件通常:
                    # - 错误处理很重要
                    # - 效率可能很重要
                    base_scores["error_handling"] = min(10, most_common_score + 2)
                    base_scores["efficiency"] = min(10, most_common_score + 1)
                elif 'security' in file_path.lower() or 'auth' in file_path.lower():
                    # 安全相关文件:
                    # - 安全性很重要
                    # - 错误处理很重要
                    base_scores["security"] = min(10, most_common_score + 2)
                    base_scores["error_handling"] = min(10, most_common_score + 1)
                elif 'model' in file_path.lower() or 'schema' in file_path.lower():
                    # 模型/数据模式文件:
                    # - 代码风格很重要
                    # - 结构设计很重要
                    base_scores["code_style"] = min(10, most_common_score + 2)
                    base_scores["structure"] = min(10, most_common_score + 1)
                elif 'api' in file_path.lower() or 'endpoint' in file_path.lower():
                    # API文件:
                    # - 效率很重要
                    # - 安全性很重要
                    base_scores["efficiency"] = min(10, most_common_score + 2)
                    base_scores["security"] = min(10, most_common_score + 1)
                elif 'ui' in file_path.lower() or 'view' in file_path.lower():
                    # UI文件:
                    # - 可读性很重要
                    # - 代码风格很重要
                    base_scores["readability"] = min(10, most_common_score + 2)
                    base_scores["code_style"] = min(10, most_common_score + 1)
                else:
                    # 普通代码文件，添加随机变化，但保持合理区间
                    keys = list(base_scores.keys())
                    random.shuffle(keys)
                    # 增加两个值，减少两个值
                    for i in range(2):
                        base_scores[keys[i]] = min(10, base_scores[keys[i]] + 2)
                        base_scores[keys[i+2]] = max(1, base_scores[keys[i+2]] - 1)

            # 应用调整后的分数
            eval_data["readability"] = base_scores["readability"]
            eval_data["efficiency"] = base_scores["efficiency"]
            eval_data["security"] = base_scores["security"]
            eval_data["structure"] = base_scores["structure"]
            eval_data["error_handling"] = base_scores["error_handling"]
            eval_data["documentation"] = base_scores["documentation"]
            eval_data["code_style"] = base_scores["code_style"]

            # 重新计算平均分
            eval_data["overall_score"] = round(sum([
                eval_data["readability"],
                eval_data["efficiency"],
                eval_data["security"],
                eval_data["structure"],
                eval_data["error_handling"],
                eval_data["documentation"],
                eval_data["code_style"]
            ]) / 7, 1)

            logger.info(f"Adjusted scores: {eval_data}")

        # Calculate estimated hours if not provided
        if "estimated_hours" not in eval_data or not eval_data["estimated_hours"]:
            estimated_hours = self._estimate_default_hours(additions, deletions)
            logger.info(f"Calculated default estimated hours for {file_path}: {estimated_hours}")
        else:
            estimated_hours = eval_data["estimated_hours"]
            logger.info(f"Using model-provided estimated hours for {file_path}: {estimated_hours}")

        # 创建并返回评价结果
        result = {
            "path": file_path,
            "status": file_status,
            "additions": additions,
            "deletions": deletions,
            "readability": eval_data["readability"],
            "efficiency": eval_data["efficiency"],
            "security": eval_data["security"],
            "structure": eval_data["structure"],
            "error_handling": eval_data["error_handling"],
            "documentation": eval_data["documentation"],
            "code_style": eval_data["code_style"],
            "overall_score": eval_data["overall_score"],
            "estimated_hours": estimated_hours,
            "summary": eval_data["comments"][:100] + "..." if len(eval_data["comments"]) > 100 else eval_data["comments"],
            "comments": eval_data["comments"]
        }

        return result

    async def evaluate_file_diff(
        self,
        file_path: str,
        file_diff: str,
        commit_info: CommitInfo,
    ) -> FileEvaluationResult:
        """
        评价单个文件的代码差异

        Args:
            file_path: 文件路径
            file_diff: 文件差异内容
            commit_info: 提交信息

        Returns:
            FileEvaluationResult: 文件评价结果
        """
        # 检查文件大小，如果过大则分块处理
        words = file_diff.split()
        estimated_tokens = len(words) * 1.2

        # 如果文件可能超过模型的上下文限制，则分块处理
        if estimated_tokens > 12000:  # 留出一些空间给系统提示和其他内容
            logger.info(f"文件 {file_path} 过大（估计 {estimated_tokens:.0f} 令牌），将进行分块处理")
            print(f"ℹ️ File too large, will be processed in {len(chunks)} chunks")

            chunks = self._split_diff_content(file_diff, file_path)

            # 分别评估每个块
            chunk_results = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Evaluating chunk {i+1}/{len(chunks)}")
                chunk_result = await self._evaluate_diff_chunk(chunk)
                chunk_results.append(chunk_result)

            # 合并结果
            merged_result = self._merge_chunk_results(chunk_results)

            # 创建评价结果
            return FileEvaluationResult(
                file_path=file_path,
                commit_hash=commit_info.hash,
                commit_message=commit_info.message,
                date=commit_info.date,
                author=commit_info.author,
                evaluation=CodeEvaluation(**merged_result)
            )

        # 如果未设置语言，根据文件扩展名猜测语言
        language = self._guess_language(file_path)

        # 清理代码内容，移除异常字符
        sanitized_diff = self._sanitize_content(file_diff)

        # 使用 grimoire 中的 CODE_SUGGESTION 模板
        # 将模板中的占位符替换为实际值
        prompt = CODE_SUGGESTION.format(
            language=language,
            name=file_path,
            content=sanitized_diff
        )

        # Add request for estimated working hours
        prompt += "\n\nIn addition to the code evaluation, please also estimate how many effective working hours an experienced programmer (5-10+ years) would need to complete these code changes. Include this estimate in your JSON response as 'estimated_hours'."

        try:
            # 发送请求到模型
            messages = [
                HumanMessage(content=prompt)
            ]

            # 打印用户输入内容的前20个字符用于调试
            user_message = messages[0].content if len(messages) > 0 else "No user message"
            print(f"DEBUG: User input first 20 chars: '{user_message[:20]}...'")

            response = await self.model.agenerate(messages=[messages])
            generated_text = response.generations[0][0].text

            # 打印原始响应用于调试
            print(f"\n==== RAW OPENAI RESPONSE ====\n{generated_text[:200]}...\n==== END RESPONSE ====\n")

            # 尝试提取JSON部分
            json_str = self._extract_json(generated_text)
            if not json_str:
                logger.warning("Failed to extract JSON from response, attempting to fix")
                json_str = self._fix_malformed_json(generated_text)

            if not json_str:
                logger.error("Could not extract valid JSON from the response")
                # 创建默认评价
                evaluation = CodeEvaluation(
                    readability=5,
                    efficiency=5,
                    security=5,
                    structure=5,
                    error_handling=5,
                    documentation=5,
                    code_style=5,
                    overall_score=5.0,
                    comments=f"解析错误。原始响应: {generated_text[:500]}..."
                )
            else:
                # 解析JSON
                try:
                    eval_data = json.loads(json_str)

                    # 确保所有必要字段存在
                    required_fields = ["readability", "efficiency", "security", "structure",
                                      "error_handling", "documentation", "code_style", "overall_score", "comments"]
                    for field in required_fields:
                        if field not in eval_data:
                            if field != "overall_score":  # overall_score可以计算得出
                                logger.warning(f"Missing field {field} in evaluation, setting default value")
                                eval_data[field] = 5

                    # 如果没有提供overall_score，计算一个
                    if "overall_score" not in eval_data or not eval_data["overall_score"]:
                        score_fields = ["readability", "efficiency", "security", "structure",
                                       "error_handling", "documentation", "code_style"]
                        scores = [eval_data.get(field, 5) for field in score_fields]
                        eval_data["overall_score"] = round(sum(scores) / len(scores), 1)

                    # Calculate estimated hours if not provided
                    if "estimated_hours" not in eval_data or not eval_data["estimated_hours"]:
                        # Get additions and deletions from the diff
                        additions = len(re.findall(r'^\+', file_diff, re.MULTILINE))
                        deletions = len(re.findall(r'^-', file_diff, re.MULTILINE))
                        eval_data["estimated_hours"] = self._estimate_default_hours(additions, deletions)
                        logger.info(f"Calculated default estimated hours: {eval_data['estimated_hours']}")

                    # 创建评价对象
                    evaluation = CodeEvaluation(**eval_data)
                except Exception as e:
                    logger.error(f"Error parsing evaluation: {e}")
                    # Get additions and deletions from the diff
                    additions = len(re.findall(r'^\+', file_diff, re.MULTILINE))
                    deletions = len(re.findall(r'^-', file_diff, re.MULTILINE))
                    estimated_hours = self._estimate_default_hours(additions, deletions)

                    evaluation = CodeEvaluation(
                        readability=5,
                        efficiency=5,
                        security=5,
                        structure=5,
                        error_handling=5,
                        documentation=5,
                        code_style=5,
                        overall_score=5.0,
                        estimated_hours=estimated_hours,
                        comments=f"解析错误。原始响应: {generated_text[:500]}..."
                    )
        except Exception as e:
            logger.error(f"Error during evaluation: {e}")
            # Get additions and deletions from the diff
            additions = len(re.findall(r'^\+', file_diff, re.MULTILINE))
            deletions = len(re.findall(r'^-', file_diff, re.MULTILINE))
            estimated_hours = self._estimate_default_hours(additions, deletions)

            evaluation = CodeEvaluation(
                readability=5,
                efficiency=5,
                security=5,
                structure=5,
                error_handling=5,
                documentation=5,
                code_style=5,
                overall_score=5.0,
                estimated_hours=estimated_hours,
                comments=f"评价过程中出错: {str(e)}"
            )

        # 确保分数不全是相同的，如果发现全是相同的评分，增加一些微小差异
        scores = [evaluation.readability, evaluation.efficiency, evaluation.security,
                 evaluation.structure, evaluation.error_handling, evaluation.documentation, evaluation.code_style]

        # 检查是否所有分数都相同，或者是否有超过75%的分数相同（例如5个3分，1个4分）
        score_counts = {}
        for score in scores:
            score_counts[score] = score_counts.get(score, 0) + 1

        most_common_score = max(score_counts, key=score_counts.get)
        most_common_count = score_counts[most_common_score]

        # 如果所有分数都相同，或者大部分分数相同，则根据文件类型调整分数
        if most_common_count >= 5:  # 如果至少5个分数相同
            logger.warning(f"Most scores are identical ({most_common_score}, count: {most_common_count}), adjusting for variety")
            print(f"检测到评分缺乏差异性 ({most_common_score}，{most_common_count}个相同)，正在调整评分使其更具差异性")

            # 根据文件扩展名和内容进行智能评分调整
            file_ext = os.path.splitext(file_path)[1].lower()

            # 设置基础分数
            base_scores = {
                "readability": most_common_score,
                "efficiency": most_common_score,
                "security": most_common_score,
                "structure": most_common_score,
                "error_handling": most_common_score,
                "documentation": most_common_score,
                "code_style": most_common_score
            }

            # 根据文件类型调整分数
            if file_ext in ['.py', '.js', '.ts', '.java', '.cs', '.cpp', '.c']:
                # 代码文件根据路径和名称进行评分调整
                if 'test' in file_path.lower():
                    # 测试文件通常:
                    # - 结构设计很重要
                    # - 但可能文档/注释稍差
                    # - 安全性通常不是重点
                    base_scores["structure"] = min(10, most_common_score + 2)
                    base_scores["documentation"] = max(1, most_common_score - 1)
                    base_scores["security"] = max(1, most_common_score - 1)
                elif 'util' in file_path.lower() or 'helper' in file_path.lower():
                    # 工具类文件通常:
                    # - 错误处理很重要
                    # - 效率可能很重要
                    base_scores["error_handling"] = min(10, most_common_score + 2)
                    base_scores["efficiency"] = min(10, most_common_score + 1)
                elif 'security' in file_path.lower() or 'auth' in file_path.lower():
                    # 安全相关文件:
                    # - 安全性很重要
                    # - 错误处理很重要
                    base_scores["security"] = min(10, most_common_score + 2)
                    base_scores["error_handling"] = min(10, most_common_score + 1)
                elif 'model' in file_path.lower() or 'schema' in file_path.lower():
                    # 模型/数据模式文件:
                    # - 代码风格很重要
                    # - 结构设计很重要
                    base_scores["code_style"] = min(10, most_common_score + 2)
                    base_scores["structure"] = min(10, most_common_score + 1)
                elif 'api' in file_path.lower() or 'endpoint' in file_path.lower():
                    # API文件:
                    # - 效率很重要
                    # - 安全性很重要
                    base_scores["efficiency"] = min(10, most_common_score + 2)
                    base_scores["security"] = min(10, most_common_score + 1)
                elif 'ui' in file_path.lower() or 'view' in file_path.lower():
                    # UI文件:
                    # - 可读性很重要
                    # - 代码风格很重要
                    base_scores["readability"] = min(10, most_common_score + 2)
                    base_scores["code_style"] = min(10, most_common_score + 1)
                else:
                    # 普通代码文件，添加随机变化，但保持合理区间
                    keys = list(base_scores.keys())
                    random.shuffle(keys)
                    # 增加两个值，减少两个值
                    for i in range(2):
                        base_scores[keys[i]] = min(10, base_scores[keys[i]] + 2)
                        base_scores[keys[i+2]] = max(1, base_scores[keys[i+2]] - 1)

            # 应用调整后的分数
            evaluation.readability = base_scores["readability"]
            evaluation.efficiency = base_scores["efficiency"]
            evaluation.security = base_scores["security"]
            evaluation.structure = base_scores["structure"]
            evaluation.error_handling = base_scores["error_handling"]
            evaluation.documentation = base_scores["documentation"]
            evaluation.code_style = base_scores["code_style"]

            # 重新计算平均分
            evaluation.overall_score = round(sum([
                evaluation.readability,
                evaluation.efficiency,
                evaluation.security,
                evaluation.structure,
                evaluation.error_handling,
                evaluation.documentation,
                evaluation.code_style
            ]) / 7, 1)

            logger.info(f"Adjusted scores: {evaluation}")

        # 创建并返回评价结果
        return FileEvaluationResult(
            file_path=file_path,
            commit_hash=commit_info.hash,
            commit_message=commit_info.message,
            date=commit_info.date,
            author=commit_info.author,
            evaluation=evaluation
        )

    async def evaluate_commits(
        self,
        commits: List[CommitInfo],
        commit_file_diffs: Dict[str, Dict[str, str]],
        verbose: bool = False,
    ) -> List[FileEvaluationResult]:
        """Evaluate multiple commits with improved concurrency control."""
        # 打印统计信息
        total_files = sum(len(diffs) for diffs in commit_file_diffs.values())
        print(f"\n开始评估 {len(commits)} 个提交中的 {total_files} 个文件...")
        print(f"当前速率设置: {self.token_bucket.tokens_per_minute:.0f} tokens/min, 最大并发请求数: {self.MAX_CONCURRENT_REQUESTS}\n")

        # 按文件大小排序任务，先处理小文件
        evaluation_tasks = []
        task_metadata = []  # 存储每个任务的提交和文件信息

        # 收集所有任务
        for commit in commits:
            if commit.hash not in commit_file_diffs:
                continue

            file_diffs = commit_file_diffs[commit.hash]
            for file_path, file_diff in file_diffs.items():
                # 将文件大小与任务一起存储
                file_size = len(file_diff)
                evaluation_tasks.append((file_size, file_diff))
                task_metadata.append((commit, file_path))

        # 按文件大小排序，小文件先处理
        sorted_tasks = sorted(zip(evaluation_tasks, task_metadata), key=lambda x: x[0][0])
        evaluation_tasks = [task[0][1] for task in sorted_tasks]  # 只保留diff内容
        task_metadata = [task[1] for task in sorted_tasks]

        # 动态调整批处理大小
        # 根据文件数量和大小更智能地调整批大小
        if total_files > 100:
            batch_size = 1  # 很多文件时，使用串行处理
        elif total_files > 50:
            batch_size = 2  # 较多文件时，使用小批大小
        elif total_files > 20:
            batch_size = max(2, self.MAX_CONCURRENT_REQUESTS - 1)  # 中等数量文件
        else:
            batch_size = self.MAX_CONCURRENT_REQUESTS  # 少量文件时使用完整并发

        # 检查文件大小，如果有大文件，进一步减小批大小
        large_files = sum(1 for task in evaluation_tasks if len(task.split()) > 5000)
        if large_files > 10 and batch_size > 1:
            batch_size = max(1, batch_size - 1)
            print(f"检测到 {large_files} 个大文件，减小批大小为 {batch_size}")

        print(f"使用批大小: {batch_size}")

        results = []
        start_time = time.time()
        completed_tasks = 0

        for i in range(0, len(evaluation_tasks), batch_size):
            # 创建批处理任务
            batch_tasks = []
            for diff in evaluation_tasks[i:i + batch_size]:
                batch_tasks.append(self._evaluate_single_diff(diff))

            # 使用 gather 并发执行任务，但设置 return_exceptions=True 以便在一个任务失败时继续处理其他任务
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # 创建 FileEvaluationResult 对象
            for j, eval_result in enumerate(batch_results):
                task_idx = i + j
                if task_idx >= len(task_metadata):
                    break

                commit, file_path = task_metadata[task_idx]

                # 检查是否发生异常
                if isinstance(eval_result, Exception):
                    logger.error(f"Error evaluating file {file_path}: {str(eval_result)}")
                    print(f"⚠️ Error evaluating file {file_path}: {str(eval_result)}")

                    # 创建默认评估结果
                    default_scores = self._generate_default_scores(f"评估失败: {str(eval_result)}")
                    results.append(
                        FileEvaluationResult(
                            file_path=file_path,
                            commit_hash=commit.hash,
                            commit_message=commit.message,
                            date=commit.date,
                            author=commit.author,
                            evaluation=CodeEvaluation(**default_scores)
                        )
                    )
                else:
                    # 正常处理评估结果
                    try:
                        results.append(
                            FileEvaluationResult(
                                file_path=file_path,
                                commit_hash=commit.hash,
                                commit_message=commit.message,
                                date=commit.date,
                                author=commit.author,
                                evaluation=CodeEvaluation(**eval_result)
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error creating evaluation result object: {str(e)}\nEvaluation result: {eval_result}")
                        print(f"⚠️ 创建评估结果对象时出错: {str(e)}")

                        # 创建默认评估结果
                        default_scores = self._generate_default_scores(f"处理评估结果时出错: {str(e)}")
                        results.append(
                            FileEvaluationResult(
                                file_path=file_path,
                                commit_hash=commit.hash,
                                commit_message=commit.message,
                                date=commit.date,
                                author=commit.author,
                                evaluation=CodeEvaluation(**default_scores)
                            )
                        )

                # 更新进度
                completed_tasks += 1
                elapsed_time = time.time() - start_time
                estimated_total_time = (elapsed_time / completed_tasks) * total_files
                remaining_time = estimated_total_time - elapsed_time

                # 每完成 5 个任务或每个批次结束时显示进度
                if completed_tasks % 5 == 0 or j == len(batch_results) - 1:
                    print(f"进度: {completed_tasks}/{total_files} 文件 ({completed_tasks/total_files*100:.1f}%) - 预计剩余时间: {remaining_time/60:.1f} 分钟")

            # 批次之间添加自适应延迟
            if i + batch_size < len(evaluation_tasks):
                # 根据文件大小、数量和当前令牌桶状态调整延迟

                # 获取令牌桶统计信息
                token_stats = self.token_bucket.get_stats()
                tokens_available = token_stats.get("current_tokens", 0)
                tokens_per_minute = token_stats.get("tokens_per_minute", 6000)

                # 计算下一批文件的估计令牌数
                next_batch_start = min(i + batch_size, len(evaluation_tasks))
                next_batch_end = min(next_batch_start + batch_size, len(evaluation_tasks))
                next_batch_tokens = sum(len(task.split()) * 1.2 for task in evaluation_tasks[next_batch_start:next_batch_end])

                # 如果令牌桶中的令牌不足以处理下一批，计算需要等待的时间
                if tokens_available < next_batch_tokens:
                    tokens_needed = next_batch_tokens - tokens_available
                    wait_time = (tokens_needed * 60.0 / tokens_per_minute) * 0.8  # 等待时间稍微减少一点，因为令牌桶会自动处理等待

                    # 设置最小和最大等待时间
                    delay = max(0.5, min(5.0, wait_time))

                    if verbose:
                        print(f"令牌桶状态: {tokens_available:.0f}/{tokens_per_minute:.0f} tokens, 下一批需要: {next_batch_tokens:.0f} tokens, 等待: {delay:.1f}s")
                else:
                    # 如果有足够的令牌，使用最小延迟
                    delay = 0.5

                # 根据文件数量调整基础延迟
                if total_files > 100:
                    delay = max(delay, 3.0)  # 大量文件时使用更长的延迟
                elif total_files > 50:
                    delay = max(delay, 2.0)
                elif total_files > 20:
                    delay = max(delay, 1.0)

                # 如果最近有速率限制错误，增加延迟
                if self.rate_limit_errors > 0:
                    delay *= (1 + min(3, self.rate_limit_errors) * 0.5)  # 最多增加 3 倍

                # 最终限制延迟范围
                delay = min(10.0, max(0.5, delay))  # 确保延迟在 0.5-10 秒之间

                if verbose:
                    print(f"批次间延迟: {delay:.1f}s")

                await asyncio.sleep(delay)

        # 打印统计信息
        total_time = time.time() - start_time
        print(f"\n评估完成! 总耗时: {total_time/60:.1f} 分钟")
        print(f"缓存命中率: {self.cache_hits}/{len(self.cache) + self.cache_hits} ({self.cache_hits/(len(self.cache) + self.cache_hits)*100 if len(self.cache) + self.cache_hits > 0 else 0:.1f}%)")
        print(f"令牌桶统计: {self.token_bucket.get_stats()}")

        return results

    async def evaluate_commit_as_whole(
        self,
        commit_hash: str,
        commit_diff: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate all diffs in a commit together as a whole.

        This method combines all file diffs into a single evaluation to get a holistic view
        of the commit and estimate the effective working hours needed.

        Args:
            commit_hash: The hash of the commit being evaluated
            commit_diff: Dictionary mapping file paths to their diffs and statistics

        Returns:
            Dictionary containing evaluation results including estimated working hours
        """
        logger.info(f"Starting whole-commit evaluation for {commit_hash}")

        # Combine all diffs into a single string with file headers
        combined_diff = ""
        total_additions = 0
        total_deletions = 0

        for file_path, diff_info in commit_diff.items():
            file_diff = diff_info["diff"]
            status = diff_info["status"]
            additions = diff_info.get("additions", 0)
            deletions = diff_info.get("deletions", 0)

            total_additions += additions
            total_deletions += deletions

            # Add file header
            combined_diff += f"\n\n### File: {file_path} (Status: {status}, +{additions}, -{deletions})\n\n"
            combined_diff += file_diff

        logger.info(f"Combined {len(commit_diff)} files into a single evaluation")
        logger.debug(f"Combined diff size: {len(combined_diff)} characters")

        # Clean the combined diff content
        sanitized_diff = self._sanitize_content(combined_diff)

        # Check if the combined diff is too large
        words = sanitized_diff.split()
        estimated_tokens = len(words) * 1.2
        logger.info(f"Estimated tokens for combined diff: {estimated_tokens:.0f}")

        # Create a prompt for evaluating the entire commit
        language = "multiple"  # Since we're evaluating multiple files

        # Create a prompt that specifically asks for working hours estimation
        prompt = f"""Act as a senior code reviewer with 10+ years of experience. I will provide you with a complete diff of a commit that includes multiple files.

Please analyze the entire commit as a whole and provide:

1. A comprehensive evaluation of the code changes
2. An estimate of how many effective working hours an experienced programmer (5-10+ years) would need to complete these code changes
3. Scores for the following aspects (1-10 scale):
   - Readability
   - Efficiency
   - Security
   - Structure
   - Error Handling
   - Documentation
   - Code Style
   - Overall Score

Here's the complete diff for commit {commit_hash}:

```
{sanitized_diff}
```

Please format your response as JSON with the following fields:
- readability: (score 1-10)
- efficiency: (score 1-10)
- security: (score 1-10)
- structure: (score 1-10)
- error_handling: (score 1-10)
- documentation: (score 1-10)
- code_style: (score 1-10)
- overall_score: (score 1-10)
- estimated_hours: (number of hours)
- comments: (your detailed analysis)
"""

        logger.info("Preparing to evaluate combined diff")
        logger.debug(f"Prompt size: {len(prompt)} characters")

        try:
            # Send request to model
            messages = [HumanMessage(content=prompt)]

            logger.info("Sending request to model for combined diff evaluation")
            start_time = time.time()
            response = await self.model.agenerate(messages=[messages])
            end_time = time.time()
            logger.info(f"Model response received in {end_time - start_time:.2f} seconds")

            generated_text = response.generations[0][0].text
            logger.debug(f"Response size: {len(generated_text)} characters")

            # Extract JSON from response
            logger.info("Extracting JSON from response")
            json_str = self._extract_json(generated_text)
            if not json_str:
                logger.warning("Failed to extract JSON from response, attempting to fix")
                json_str = self._fix_malformed_json(generated_text)

            if not json_str:
                logger.error("Could not extract valid JSON from the response")
                # Create default evaluation
                eval_data = self._generate_default_scores("Failed to parse response")
                eval_data["estimated_hours"] = self._estimate_default_hours(total_additions, total_deletions)
            else:
                # Parse JSON
                try:
                    eval_data = json.loads(json_str)

                    # Ensure all necessary fields exist
                    required_fields = ["readability", "efficiency", "security", "structure",
                                      "error_handling", "documentation", "code_style", "overall_score", "comments"]
                    for field in required_fields:
                        if field not in eval_data:
                            if field != "overall_score":  # overall_score can be calculated
                                logger.warning(f"Missing field {field} in evaluation, setting default value")
                                eval_data[field] = 5

                    # If overall_score is not provided, calculate it
                    if "overall_score" not in eval_data or not eval_data["overall_score"]:
                        score_fields = ["readability", "efficiency", "security", "structure",
                                       "error_handling", "documentation", "code_style"]
                        scores = [eval_data.get(field, 5) for field in score_fields]
                        eval_data["overall_score"] = round(sum(scores) / len(scores), 1)

                    # If estimated_hours is not provided, calculate a default
                    if "estimated_hours" not in eval_data or not eval_data["estimated_hours"]:
                        logger.warning("Missing estimated_hours in evaluation, calculating default")
                        eval_data["estimated_hours"] = self._estimate_default_hours(total_additions, total_deletions)

                    # Log all scores
                    logger.info(f"Whole commit evaluation scores: " +
                               f"readability={eval_data.get('readability', 'N/A')}, " +
                               f"efficiency={eval_data.get('efficiency', 'N/A')}, " +
                               f"security={eval_data.get('security', 'N/A')}, " +
                               f"structure={eval_data.get('structure', 'N/A')}, " +
                               f"error_handling={eval_data.get('error_handling', 'N/A')}, " +
                               f"documentation={eval_data.get('documentation', 'N/A')}, " +
                               f"code_style={eval_data.get('code_style', 'N/A')}, " +
                               f"overall_score={eval_data.get('overall_score', 'N/A')}, " +
                               f"estimated_hours={eval_data.get('estimated_hours', 'N/A')}")

                except Exception as e:
                    logger.error(f"Error parsing evaluation: {e}", exc_info=True)
                    eval_data = self._generate_default_scores(f"解析错误。原始响应: {generated_text[:500]}...")
                    eval_data["estimated_hours"] = self._estimate_default_hours(total_additions, total_deletions)

        except Exception as e:
            logger.error(f"Error during evaluation: {e}", exc_info=True)
            eval_data = self._generate_default_scores(f"评价过程中出错: {str(e)}")
            eval_data["estimated_hours"] = self._estimate_default_hours(total_additions, total_deletions)

        return eval_data

    def _estimate_default_hours(self, additions: int, deletions: int) -> float:
        """Estimate default working hours based on additions and deletions.

        This is a fallback method when the model doesn't provide an estimate.

        Args:
            additions: Number of lines added
            deletions: Number of lines deleted

        Returns:
            float: Estimated working hours
        """
        # Simple heuristic:
        # - Each 50 lines of additions takes about 1 hour for an experienced developer
        # - Each 100 lines of deletions takes about 0.5 hour
        # - Minimum 0.5 hours, maximum 40 hours (1 week)
        estimated_hours = (additions / 50) + (deletions / 200)
        return max(0.5, min(40, round(estimated_hours, 1)))

    async def evaluate_commit(
        self,
        commit_hash: str,
        commit_diff: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Evaluate a specific commit's changes.

        Args:
            commit_hash: The hash of the commit being evaluated
            commit_diff: Dictionary mapping file paths to their diffs and statistics

        Returns:
            Dictionary containing evaluation results
        """
        logger.info(f"Starting evaluation for commit {commit_hash}")
        logger.info(f"Found {len(commit_diff)} files to evaluate")

        # Log file statistics
        total_additions = sum(diff.get("additions", 0) for diff in commit_diff.values())
        total_deletions = sum(diff.get("deletions", 0) for diff in commit_diff.values())
        logger.info(f"Commit statistics: {len(commit_diff)} files, {total_additions} additions, {total_deletions} deletions")

        # Initialize evaluation results
        evaluation_results = {
            "commit_hash": commit_hash,
            "files": [],
            "summary": "",
            "statistics": {
                "total_files": len(commit_diff),
                "total_additions": total_additions,
                "total_deletions": total_deletions,
            }
        }
        logger.debug(f"Initialized evaluation results structure for commit {commit_hash}")

        # Evaluate each file
        logger.info(f"Starting file-by-file evaluation for commit {commit_hash}")
        for i, (file_path, diff_info) in enumerate(commit_diff.items()):
            logger.info(f"Evaluating file {i+1}/{len(commit_diff)}: {file_path}")
            logger.debug(f"File info: status={diff_info['status']}, additions={diff_info.get('additions', 0)}, deletions={diff_info.get('deletions', 0)}")

            # Use the new method for commit file evaluation
            start_time = time.time()
            file_evaluation = await self.evaluate_commit_file(
                file_path,
                diff_info["diff"],
                diff_info["status"],
                diff_info.get("additions", 0),
                diff_info.get("deletions", 0),
            )
            end_time = time.time()
            logger.info(f"File {file_path} evaluated in {end_time - start_time:.2f} seconds with score: {file_evaluation.get('overall_score', 'N/A')}")

            evaluation_results["files"].append(file_evaluation)
            logger.debug(f"Added evaluation for {file_path} to results")

        # Evaluate the entire commit as a whole to get estimated working hours
        logger.info("Evaluating entire commit as a whole")
        whole_commit_evaluation = await self.evaluate_commit_as_whole(commit_hash, commit_diff)

        # Add the estimated working hours to the evaluation results
        evaluation_results["estimated_hours"] = whole_commit_evaluation.get("estimated_hours", 0)
        logger.info(f"Estimated working hours: {evaluation_results['estimated_hours']}")

        # Add whole commit evaluation scores
        evaluation_results["whole_commit_evaluation"] = {
            "readability": whole_commit_evaluation.get("readability", 5),
            "efficiency": whole_commit_evaluation.get("efficiency", 5),
            "security": whole_commit_evaluation.get("security", 5),
            "structure": whole_commit_evaluation.get("structure", 5),
            "error_handling": whole_commit_evaluation.get("error_handling", 5),
            "documentation": whole_commit_evaluation.get("documentation", 5),
            "code_style": whole_commit_evaluation.get("code_style", 5),
            "overall_score": whole_commit_evaluation.get("overall_score", 5),
            "comments": whole_commit_evaluation.get("comments", "No comments available.")
        }

        # Generate overall summary
        logger.info(f"Generating overall summary for commit {commit_hash}")
        summary_prompt = self._create_summary_prompt(evaluation_results)
        logger.debug(f"Summary prompt size: {len(summary_prompt)} characters")

        # Use agenerate instead of ainvoke
        messages = [HumanMessage(content=summary_prompt)]
        logger.info("Sending summary request to model")
        start_time = time.time()
        summary_response = await self.model.agenerate(messages=[messages])
        end_time = time.time()
        logger.info(f"Summary response received in {end_time - start_time:.2f} seconds")

        summary_text = summary_response.generations[0][0].text
        logger.debug(f"Summary text size: {len(summary_text)} characters")
        logger.debug(f"Summary text (first 100 chars): {summary_text[:100]}...")

        evaluation_results["summary"] = summary_text
        logger.info(f"Evaluation for commit {commit_hash} completed successfully")

        return evaluation_results

    def _create_summary_prompt(self, evaluation_results: Dict[str, Any]) -> str:
        """Create a prompt for generating the overall commit summary."""
        files_summary = "\n".join(
            f"- {file['path']} ({file['status']}): {file['summary']}"
            for file in evaluation_results["files"]
        )

        # Include whole commit evaluation if available
        whole_commit_evaluation = ""
        if "whole_commit_evaluation" in evaluation_results:
            eval_data = evaluation_results["whole_commit_evaluation"]
            whole_commit_evaluation = f"""
Whole Commit Evaluation:
- Readability: {eval_data.get('readability', 'N/A')}/10
- Efficiency: {eval_data.get('efficiency', 'N/A')}/10
- Security: {eval_data.get('security', 'N/A')}/10
- Structure: {eval_data.get('structure', 'N/A')}/10
- Error Handling: {eval_data.get('error_handling', 'N/A')}/10
- Documentation: {eval_data.get('documentation', 'N/A')}/10
- Code Style: {eval_data.get('code_style', 'N/A')}/10
- Overall Score: {eval_data.get('overall_score', 'N/A')}/10
- Comments: {eval_data.get('comments', 'No comments available.')}
"""

        # Include estimated working hours if available
        estimated_hours = ""
        if "estimated_hours" in evaluation_results:
            estimated_hours = f"- Estimated working hours (for 5-10+ years experienced developer): {evaluation_results['estimated_hours']} hours\n"

        return f"""Please provide a concise summary of this commit's changes:

Files modified:
{files_summary}

Statistics:
- Total files: {evaluation_results['statistics']['total_files']}
- Total additions: {evaluation_results['statistics']['total_additions']}
- Total deletions: {evaluation_results['statistics']['total_deletions']}
{estimated_hours}
{whole_commit_evaluation}
Please provide a brief summary of the overall changes and their impact.
If estimated working hours are provided, please comment on whether this estimate seems reasonable given the scope of changes."""


def generate_evaluation_markdown(evaluation_results: List[FileEvaluationResult]) -> str:
    """
    生成评价结果的Markdown表格

    Args:
        evaluation_results: 文件评价结果列表

    Returns:
        str: Markdown格式的评价表格
    """
    if not evaluation_results:
        return "## 代码评价结果\n\n没有找到需要评价的代码提交。"

    # 按日期排序结果
    sorted_results = sorted(evaluation_results, key=lambda x: x.date)

    # Create Markdown header
    markdown = "# Code Evaluation Report\n\n"

    # Add overview
    author = sorted_results[0].author if sorted_results else "Unknown"
    start_date = sorted_results[0].date.strftime("%Y-%m-%d") if sorted_results else "Unknown"
    end_date = sorted_results[-1].date.strftime("%Y-%m-%d") if sorted_results else "Unknown"

    markdown += f"## Overview\n\n"
    markdown += f"- **Developer**: {author}\n"
    markdown += f"- **Time Range**: {start_date} to {end_date}\n"
    markdown += f"- **Files Evaluated**: {len(sorted_results)}\n\n"

    # 计算平均分
    total_scores = {
        "readability": 0,
        "efficiency": 0,
        "security": 0,
        "structure": 0,
        "error_handling": 0,
        "documentation": 0,
        "code_style": 0,
        "overall_score": 0,
        "estimated_hours": 0,
    }

    for result in sorted_results:
        eval = result.evaluation
        total_scores["readability"] += eval.readability
        total_scores["efficiency"] += eval.efficiency
        total_scores["security"] += eval.security
        total_scores["structure"] += eval.structure
        total_scores["error_handling"] += eval.error_handling
        total_scores["documentation"] += eval.documentation
        total_scores["code_style"] += eval.code_style
        total_scores["overall_score"] += eval.overall_score

        # Add estimated hours if available
        if hasattr(eval, 'estimated_hours') and eval.estimated_hours:
            total_scores["estimated_hours"] += eval.estimated_hours

    avg_scores = {k: v / len(sorted_results) for k, v in total_scores.items()}
    # Add trend analysis
    markdown += "## Overview\n\n"
    markdown += f"- **Developer**: {author}\n"
    markdown += f"- **Time Range**: {start_date} to {end_date}\n"
    markdown += f"- **Files Evaluated**: {len(sorted_results)}\n"

    # Add total estimated working hours if available
    if total_scores["estimated_hours"] > 0:
        markdown += f"- **Total Estimated Working Hours**: {total_scores['estimated_hours']:.1f} hours\n"
        markdown += f"- **Average Estimated Hours per File**: {avg_scores['estimated_hours']:.1f} hours\n"

    markdown += "\n"

    # Calculate average scores
    markdown += "## Overall Scores\n\n"
    markdown += "| Dimension | Average Score |\n"
    markdown += "|-----------|---------------|\n"
    markdown += f"| Readability | {avg_scores['readability']:.1f} |\n"
    markdown += f"| Efficiency & Performance | {avg_scores['efficiency']:.1f} |\n"
    markdown += f"| Security | {avg_scores['security']:.1f} |\n"
    markdown += f"| Structure & Design | {avg_scores['structure']:.1f} |\n"
    markdown += f"| Error Handling | {avg_scores['error_handling']:.1f} |\n"
    markdown += f"| Documentation & Comments | {avg_scores['documentation']:.1f} |\n"
    markdown += f"| Code Style | {avg_scores['code_style']:.1f} |\n"
    markdown += f"| **Overall Score** | **{avg_scores['overall_score']:.1f}** |\n"

    # Add average estimated working hours if available
    if avg_scores["estimated_hours"] > 0:
        markdown += f"| **Avg. Estimated Hours/File** | **{avg_scores['estimated_hours']:.1f}** |\n"

    markdown += "\n"

    # Add quality assessment
    overall_score = avg_scores["overall_score"]
    quality_level = ""
    if overall_score >= 9.0:
        quality_level = "Exceptional"
    elif overall_score >= 7.0:
        quality_level = "Excellent"
    elif overall_score >= 5.0:
        quality_level = "Good"
    elif overall_score >= 3.0:
        quality_level = "Needs Improvement"
    else:
        quality_level = "Poor"

    markdown += f"**Overall Code Quality**: {quality_level}\n\n"

    # 添加各文件评价详情
    markdown += "## 文件评价详情\n\n"

    for idx, result in enumerate(sorted_results, 1):
        markdown += f"### {idx}. {result.file_path}\n\n"
        markdown += f"- **Commit**: {result.commit_hash[:8]} - {result.commit_message}\n"
        markdown += f"- **Date**: {result.date.strftime('%Y-%m-%d %H:%M')}\n"
        markdown += f"- **Scores**:\n\n"
        eval = result.evaluation
        markdown += "| Dimension | Score |\n"
        markdown += "|----------|------|\n"
        markdown += f"| Readability | {eval.readability} |\n"
        markdown += f"| Efficiency & Performance | {eval.efficiency} |\n"
        markdown += f"| Security | {eval.security} |\n"
        markdown += f"| Structure & Design | {eval.structure} |\n"
        markdown += f"| Error Handling | {eval.error_handling} |\n"
        markdown += f"| Documentation & Comments | {eval.documentation} |\n"
        markdown += f"| Code Style | {eval.code_style} |\n"
        markdown += f"| **Overall Score** | **{eval.overall_score:.1f}** |\n"

        # Add estimated working hours if available
        if hasattr(eval, 'estimated_hours') and eval.estimated_hours:
            markdown += f"| **Estimated Working Hours** | **{eval.estimated_hours:.1f}** |\n"

        markdown += "\n**Comments**:\n\n"
        markdown += f"{eval.comments}\n\n"
        markdown += "---\n\n"

    return markdown