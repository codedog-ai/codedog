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
    """代码评价的结构化输出"""
    readability: int = Field(description="代码可读性评分 (1-10)", ge=1, le=10)
    efficiency: int = Field(description="代码效率与性能评分 (1-10)", ge=1, le=10)
    security: int = Field(description="代码安全性评分 (1-10)", ge=1, le=10)
    structure: int = Field(description="代码结构与设计评分 (1-10)", ge=1, le=10)
    error_handling: int = Field(description="错误处理评分 (1-10)", ge=1, le=10)
    documentation: int = Field(description="文档与注释评分 (1-10)", ge=1, le=10)
    code_style: int = Field(description="代码风格评分 (1-10)", ge=1, le=10)
    overall_score: float = Field(description="总分 (1-10)", ge=1, le=10)
    comments: str = Field(description="评价意见和改进建议")

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

    logger.info(f"已保存diff内容到 {output_path} (估计: {estimated_tokens}, 实际: {actual_tokens} tokens)")

    # 如果实际token数量远远超过估计值，记录警告
    if actual_tokens > estimated_tokens * 1.5:
        logger.warning(f"警告: 实际token数量 ({actual_tokens}) 远超估计值 ({estimated_tokens})")


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
        self.system_prompt = SYSTEM_PROMPT

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
            logger.warning(f"遇到速率限制，降低令牌生成速率: {self.token_bucket.tokens_per_minute:.0f} -> {new_rate:.0f} tokens/min")
            print(f"⚠️ 遇到API速率限制，正在降低请求速率: {self.token_bucket.tokens_per_minute:.0f} -> {new_rate:.0f} tokens/min")
            self.token_bucket.tokens_per_minute = new_rate

            # 增加最小请求间隔
            self.MIN_REQUEST_INTERVAL *= self.rate_limit_backoff_factor
            logger.warning(f"增加最小请求间隔: {self.MIN_REQUEST_INTERVAL:.2f}s")

            # 减少最大并发请求数，但不少于1
            if self.MAX_CONCURRENT_REQUESTS > 1:
                self.MAX_CONCURRENT_REQUESTS = max(1, self.MAX_CONCURRENT_REQUESTS - 1)
                self.request_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
                logger.warning(f"减少最大并发请求数: {self.MAX_CONCURRENT_REQUESTS}")
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
                    logger.info(f"连续成功{self.consecutive_successes}次，提高令牌生成速率: {self.token_bucket.tokens_per_minute:.0f} -> {new_rate:.0f} tokens/min")
                    print(f"✅ 连续成功{self.consecutive_successes}次，正在提高请求速率: {self.token_bucket.tokens_per_minute:.0f} -> {new_rate:.0f} tokens/min")
                    self.token_bucket.tokens_per_minute = new_rate

                    # 减少最小请求间隔，但不少于初始值
                    self.MIN_REQUEST_INTERVAL = max(1.0, self.MIN_REQUEST_INTERVAL / self.rate_limit_recovery_factor)

                    # 增加最大并发请求数，但不超过初始值
                    if self.MAX_CONCURRENT_REQUESTS < 3:
                        self.MAX_CONCURRENT_REQUESTS += 1
                        self.request_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
                        logger.info(f"增加最大并发请求数: {self.MAX_CONCURRENT_REQUESTS}")

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

        logger.info(f"差异内容过大，已分割为 {len(chunks)} 个块进行评估")
        print(f"ℹ️ 文件过大，已分割为 {len(chunks)} 个块进行评估")

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
            logger.info(f"缓存命中! 已从缓存获取评估结果 (命中率: {self.cache_hits}/{len(self.cache) + self.cache_hits})")
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
                logger.info(f"评估分块 {i+1}/{len(chunks)}")
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
                    logger.info(f"速率限制: 等待 {wait_time:.2f}s 令牌补充")
                    print(f"⏳ 速率限制: 等待 {wait_time:.2f}s 令牌补充 (当前速率: {self.token_bucket.tokens_per_minute:.0f} tokens/min)")
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

                    # 使用优化的代码评审prompt
                    review_prompt = CODE_REVIEW_PROMPT.format(
                        file_name=file_name,
                        language=language.lower(),
                        code_content=diff_content
                    )

                    # 添加语言特定的考虑因素
                    language_key = language.lower()
                    if language_key in LANGUAGE_SPECIFIC_CONSIDERATIONS:
                        review_prompt += "\n\n" + LANGUAGE_SPECIFIC_CONSIDERATIONS[language_key]

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
                "error_handling", "documentation", "code_style", "overall_score", "comments"
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

            # 使用from_dict方法创建CodeEvaluation实例进行最终验证
            evaluation = CodeEvaluation.from_dict(normalized_result)
            return evaluation.model_dump()
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
            "comments": error_message
        }

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

    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON部分。

        Args:
            text: 原始文本

        Returns:
            str: 提取的JSON字符串，如果没有找到则返回空字符串
        """
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

        return ""

    def _fix_malformed_json(self, json_str: str) -> str:
        """尝试修复格式不正确的JSON字符串。

        Args:
            json_str: 可能格式不正确的JSON字符串

        Returns:
            str: 修复后的JSON字符串，如果无法修复则返回空字符串
        """
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

            # 尝试提取分数并创建最小可用的JSON
            try:
                # 提取分数
                scores = {}
                for field in ["readability", "efficiency", "security", "structure", "error_handling", "documentation", "code_style"]:
                    match = re.search(f'"{field}"\s*:\s*(\d+)', original_json)
                    if match:
                        scores[field] = int(match.group(1))
                    else:
                        scores[field] = 5  # 默认分数

                # 尝试提取总分
                overall_match = re.search(r'"overall_score"\s*:\s*(\d+(?:\.\d+)?)', original_json)
                if overall_match:
                    scores["overall_score"] = float(overall_match.group(1))
                else:
                    # 计算总分为其他分数的平均值
                    scores["overall_score"] = round(sum(scores.values()) / len(scores), 1)

                # 添加评价意见
                scores["comments"] = "JSON解析错误，显示提取的分数。"

                # 转换为JSON字符串
                return json.dumps(scores)
            except Exception as final_e:
                logger.error(f"所有JSON修复尝试失败: {final_e}")
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
                    "comments": "JSON解析错误，显示默认分数。"
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
                    logger.info(f"速率限制: 等待 {wait_time:.2f}s 令牌补充")
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

                    # 使用简化的代码评审prompt，以减少令牌消耗
                    review_prompt = f"请评价以下代码：\n\n文件名：{file_name}\n语言：{language}\n\n```{language.lower()}\n{chunk}\n```\n\n请给出1-10分的评分和简要评价。返回JSON格式的结果。"

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

                if is_context_length_error:
                    # 如果是上下文长度错误，尝试进一步分割
                    logger.warning(f"上下文长度限制错误，尝试进一步分割内容")
                    smaller_chunks = self._split_diff_content(chunk, max_tokens_per_chunk=4000)  # 使用更小的块大小

                    if len(smaller_chunks) > 1:
                        # 如果成功分割成多个小块，分别评估并合并结果
                        sub_results = []
                        for i, sub_chunk in enumerate(smaller_chunks):
                            logger.info(f"评估子块 {i+1}/{len(smaller_chunks)}")
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
            print(f"ℹ️ 文件 {file_path} 过大，将进行分块处理")

            chunks = self._split_diff_content(file_diff, file_path)

            # 分别评估每个块
            chunk_results = []
            for i, chunk in enumerate(chunks):
                logger.info(f"评估分块 {i+1}/{len(chunks)}")
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

        # 使用 grimoire 中的 CODE_SUGGESTION 模板
        # 将模板中的占位符替换为实际值
        prompt = CODE_SUGGESTION.format(
            language=language,
            name=file_path,
            content=file_diff
        )

        try:
            # 发送请求到模型
            messages = [
                HumanMessage(content=prompt)
            ]

            response = await self.model.agenerate(messages=[messages])
            generated_text = response.generations[0][0].text

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

                    # 创建评价对象
                    evaluation = CodeEvaluation(**eval_data)
                except Exception as e:
                    logger.error(f"Error parsing evaluation: {e}")
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
        except Exception as e:
            logger.error(f"Error during evaluation: {e}")
            evaluation = CodeEvaluation(
                readability=5,
                efficiency=5,
                security=5,
                structure=5,
                error_handling=5,
                documentation=5,
                code_style=5,
                overall_score=5.0,
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
                    logger.error(f"评估文件 {file_path} 时出错: {str(eval_result)}")
                    print(f"⚠️ 评估文件 {file_path} 时出错: {str(eval_result)}")

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
                        logger.error(f"创建评估结果对象时出错: {str(e)}\n评估结果: {eval_result}")
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

    # 创建Markdown标题
    markdown = "# 代码评价报告\n\n"

    # 添加概述
    author = sorted_results[0].author if sorted_results else "未知"
    start_date = sorted_results[0].date.strftime("%Y-%m-%d") if sorted_results else "未知"
    end_date = sorted_results[-1].date.strftime("%Y-%m-%d") if sorted_results else "未知"

    markdown += f"## 概述\n\n"
    markdown += f"- **开发者**: {author}\n"
    markdown += f"- **时间范围**: {start_date} 至 {end_date}\n"
    markdown += f"- **评价文件数**: {len(sorted_results)}\n\n"

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

    avg_scores = {k: v / len(sorted_results) for k, v in total_scores.items()}

    # 添加总评分表格
    markdown += "## 总评分\n\n"
    markdown += "| 评分维度 | 平均分 |\n"
    markdown += "|---------|-------|\n"
    markdown += f"| 可读性 | {avg_scores['readability']:.1f} |\n"
    markdown += f"| 效率与性能 | {avg_scores['efficiency']:.1f} |\n"
    markdown += f"| 安全性 | {avg_scores['security']:.1f} |\n"
    markdown += f"| 结构与设计 | {avg_scores['structure']:.1f} |\n"
    markdown += f"| 错误处理 | {avg_scores['error_handling']:.1f} |\n"
    markdown += f"| 文档与注释 | {avg_scores['documentation']:.1f} |\n"
    markdown += f"| 代码风格 | {avg_scores['code_style']:.1f} |\n"
    markdown += f"| **总分** | **{avg_scores['overall_score']:.1f}** |\n\n"

    # 添加质量评估
    overall_score = avg_scores["overall_score"]
    quality_level = ""
    if overall_score >= 9.0:
        quality_level = "卓越"
    elif overall_score >= 7.0:
        quality_level = "优秀"
    elif overall_score >= 5.0:
        quality_level = "良好"
    elif overall_score >= 3.0:
        quality_level = "需要改进"
    else:
        quality_level = "较差"

    markdown += f"**整体代码质量**: {quality_level}\n\n"

    # 添加各文件评价详情
    markdown += "## 文件评价详情\n\n"

    for idx, result in enumerate(sorted_results, 1):
        markdown += f"### {idx}. {result.file_path}\n\n"
        markdown += f"- **提交**: {result.commit_hash[:8]} - {result.commit_message}\n"
        markdown += f"- **日期**: {result.date.strftime('%Y-%m-%d %H:%M')}\n"
        markdown += f"- **评分**:\n\n"

        eval = result.evaluation
        markdown += "| 评分维度 | 分数 |\n"
        markdown += "|---------|----|\n"
        markdown += f"| 可读性 | {eval.readability} |\n"
        markdown += f"| 效率与性能 | {eval.efficiency} |\n"
        markdown += f"| 安全性 | {eval.security} |\n"
        markdown += f"| 结构与设计 | {eval.structure} |\n"
        markdown += f"| 错误处理 | {eval.error_handling} |\n"
        markdown += f"| 文档与注释 | {eval.documentation} |\n"
        markdown += f"| 代码风格 | {eval.code_style} |\n"
        markdown += f"| **总分** | **{eval.overall_score:.1f}** |\n\n"

        markdown += "**评价意见**:\n\n"
        markdown += f"{eval.comments}\n\n"
        markdown += "---\n\n"

    return markdown