from functools import lru_cache
from os import environ as env
from typing import Dict, Any, List, Optional
import inspect
import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, ConfigDict
import requests
import aiohttp
import json
from langchain.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
import logging
import traceback
import asyncio

logger = logging.getLogger(__name__)


def log_error(e: Exception, message: str, response_text: str = None):
    """Log error with file name and line number"""
    frame = inspect.currentframe()
    # Get the caller's frame (1 level up)
    caller = frame.f_back
    if caller:
        file_name = os.path.basename(caller.f_code.co_filename)
        line_no = caller.f_lineno
        error_msg = f"{file_name}:{line_no} - {message}: {str(e)}"
        if response_text:
            error_msg += f"\nResponse: {response_text}"
        error_msg += f"\n{traceback.format_exc()}"
        logger.error(error_msg)
    else:
        error_msg = f"{message}: {str(e)}"
        if response_text:
            error_msg += f"\nResponse: {response_text}"
        error_msg += f"\n{traceback.format_exc()}"
        logger.error(error_msg)


# Define a custom class for DeepSeek model since it's not available in langchain directly
class DeepSeekChatModel(BaseChatModel):
    """DeepSeek Chat Model"""

    api_key: str
    model_name: str
    api_base: str
    temperature: float
    max_tokens: int
    top_p: float
    timeout: int = 600  # 增加默认超时时间到600秒
    max_retries: int = 3  # 最大重试次数
    retry_delay: int = 5  # 重试间隔（秒）
    total_tokens: int = 0
    total_cost: float = 0.0
    failed_requests: int = 0  # 失败请求计数

    def _calculate_cost(self, total_tokens: int) -> float:
        """Calculate cost based on token usage."""
        # DeepSeek pricing (as of 2024)
        return total_tokens * 0.0001  # $0.0001 per token

    @property
    def _llm_type(self) -> str:
        return "deepseek"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response from the DeepSeek API."""
        try:
            # Convert LangChain messages to DeepSeek format
            deepseek_messages = []
            for message in messages:
                role = "user" if isinstance(message, HumanMessage) else "system" if isinstance(message, SystemMessage) else "assistant"
                deepseek_messages.append({"role": role, "content": message.content})

            # Prepare API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model_name,
                "messages": deepseek_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
            }
            if stop:
                payload["stop"] = stop

            # Log request details for debugging
            logger.debug(f"DeepSeek API request to {self.api_base}")
            logger.debug(f"Model: {self.model_name}")
            logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)}")

            # Ensure API base URL is properly formatted and construct endpoint
            api_base = self.api_base.rstrip('/')
            endpoint = f"{api_base}/v1/chat/completions"

            # Make API request with timeout
            try:
                response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
                response_text = response.text
            except requests.exceptions.Timeout as e:
                log_error(e, f"DeepSeek API request timed out after {self.timeout} seconds")
                raise

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                log_error(e, f"DeepSeek API HTTP error (status {response.status_code})", response_text)
                raise

            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                log_error(e, "Failed to decode JSON response", response_text)
                raise

            # Extract response content
            if not response_data.get("choices"):
                error_msg = "No choices in response"
                log_error(ValueError(error_msg), "DeepSeek API response error", json.dumps(response_data, ensure_ascii=False))
                raise ValueError(error_msg)

            message = response_data["choices"][0]["message"]["content"]

            # Update token usage and cost
            if "usage" in response_data:
                tokens = response_data["usage"].get("total_tokens", 0)
                self.total_tokens += tokens
                self.total_cost += self._calculate_cost(tokens)

            # Create and return ChatResult
            generation = ChatGeneration(message=AIMessage(content=message))
            return ChatResult(generations=[generation])

        except Exception as e:
            log_error(e, "DeepSeek API error")
            # Return a default message indicating the error
            message = f"Error calling DeepSeek API: {str(e)}"
            generation = ChatGeneration(message=AIMessage(content=message))
            return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Asynchronously generate a response from the DeepSeek API."""
        try:
            # Convert LangChain messages to DeepSeek format
            deepseek_messages = []
            for message in messages:
                role = "user" if isinstance(message, HumanMessage) else "system" if isinstance(message, SystemMessage) else "assistant"
                deepseek_messages.append({"role": role, "content": message.content})

            # Prepare API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model_name,
                "messages": deepseek_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
            }
            if stop:
                payload["stop"] = stop

            # Log request details for debugging
            logger.debug(f"DeepSeek API request to {self.api_base}")
            logger.debug(f"Model: {self.model_name}")
            logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)}")

            # Ensure API base URL is properly formatted and construct endpoint
            api_base = self.api_base.rstrip('/')
            endpoint = f"{api_base}/v1/chat/completions"

            # 实现重试机制
            retries = 0
            last_error = None

            while retries < self.max_retries:
                try:
                    # 使用指数退避策略计算当前超时时间
                    current_timeout = self.timeout * (1 + 0.5 * retries)  # 每次重试增加 50% 的超时时间
                    logger.info(f"DeepSeek API request attempt {retries+1}/{self.max_retries} with timeout {current_timeout}s")

                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            endpoint,
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=current_timeout)
                        ) as response:
                            response_text = await response.text()

                            # 检查响应状态
                            if response.status != 200:
                                error_msg = f"DeepSeek API HTTP error (status {response.status}): {response_text}"
                                logger.warning(error_msg)
                                last_error = aiohttp.ClientResponseError(
                                    request_info=response.request_info,
                                    history=response.history,
                                    status=response.status,
                                    message=error_msg,
                                    headers=response.headers
                                )
                                # 如果是服务器错误，重试
                                if response.status >= 500:
                                    retries += 1
                                    if retries < self.max_retries:
                                        wait_time = self.retry_delay * (2 ** retries)  # 指数退避
                                        logger.info(f"Server error, retrying in {wait_time}s...")
                                        await asyncio.sleep(wait_time)
                                        continue
                                # 如果是客户端错误，不重试
                                raise last_error

                            # 解析 JSON 响应
                            try:
                                response_data = json.loads(response_text)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to decode JSON response: {e}\nResponse: {response_text}")
                                last_error = e
                                retries += 1
                                if retries < self.max_retries:
                                    wait_time = self.retry_delay * (2 ** retries)
                                    logger.info(f"JSON decode error, retrying in {wait_time}s...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    raise last_error

                            # 提取响应内容
                            if not response_data.get("choices"):
                                error_msg = f"No choices in response: {json.dumps(response_data, ensure_ascii=False)}"
                                logger.warning(error_msg)
                                last_error = ValueError(error_msg)
                                retries += 1
                                if retries < self.max_retries:
                                    wait_time = self.retry_delay * (2 ** retries)
                                    logger.info(f"Invalid response format, retrying in {wait_time}s...")
                                    await asyncio.sleep(wait_time)
                                    continue
                                else:
                                    raise last_error

                            # 提取消息内容
                            message = response_data["choices"][0]["message"]["content"]

                            # 更新令牌使用和成本
                            if "usage" in response_data:
                                tokens = response_data["usage"].get("total_tokens", 0)
                                self.total_tokens += tokens
                                self.total_cost += self._calculate_cost(tokens)

                            # 创建并返回 ChatResult
                            generation = ChatGeneration(message=AIMessage(content=message))
                            return ChatResult(generations=[generation])

                except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                    # 网络错误或超时错误，进行重试
                    last_error = e
                    logger.warning(f"Network error during DeepSeek API request: {str(e)}")
                    retries += 1
                    self.failed_requests += 1

                    if retries < self.max_retries:
                        wait_time = self.retry_delay * (2 ** retries)  # 指数退避
                        logger.info(f"Network error, retrying in {wait_time}s... (attempt {retries}/{self.max_retries})")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Failed after {self.max_retries} attempts: {str(last_error)}")
                        # 返回一个错误消息
                        error_message = f"Error calling DeepSeek API after {self.max_retries} attempts: {str(last_error)}"
                        generation = ChatGeneration(message=AIMessage(content=error_message))
                        return ChatResult(generations=[generation])

        except Exception as e:
            log_error(e, "DeepSeek API error")
            # Return a default message indicating the error
            message = f"Error calling DeepSeek API: {str(e)}"
            generation = ChatGeneration(message=AIMessage(content=message))
            return ChatResult(generations=[generation])


# Define a custom class for DeepSeek R1 model
class DeepSeekR1Model(DeepSeekChatModel):
    """DeepSeek R1 model wrapper for langchain"""

    @property
    def _llm_type(self) -> str:
        """Return type of LLM."""
        return "deepseek-reasoner"


@lru_cache(maxsize=1)
def load_gpt_llm() -> BaseChatModel:
    """Load GPT 3.5 Model"""
    # Get the specific GPT-3.5 model name from environment variable or use default
    gpt35_model = env.get("GPT35_MODEL", "gpt-3.5-turbo")

    if env.get("AZURE_OPENAI"):
        # For Azure, use the deployment ID from environment
        deployment_id = env.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-35-turbo")

        llm = AzureChatOpenAI(
            openai_api_type="azure",
            api_key=env.get("AZURE_OPENAI_API_KEY", ""),
            azure_endpoint=env.get("AZURE_OPENAI_API_BASE", ""),
            api_version="2024-05-01-preview",
            azure_deployment=deployment_id,
            model=gpt35_model,
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            api_key=env.get("OPENAI_API_KEY"),
            model=gpt35_model,
            temperature=0,
        )
    return llm


@lru_cache(maxsize=1)
def load_gpt4_llm():
    """Load GPT 4 Model. Make sure your key have access to GPT 4 API. call this function won't check it."""
    # Get the specific GPT-4 model name from environment variable or use default
    gpt4_model = env.get("GPT4_MODEL", "gpt-4")

    if env.get("AZURE_OPENAI"):
        # For Azure, use the GPT-4 deployment ID if available
        deployment_id = env.get("AZURE_OPENAI_GPT4_DEPLOYMENT_ID", env.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-4"))

        llm = AzureChatOpenAI(
            openai_api_type="azure",
            api_key=env.get("AZURE_OPENAI_API_KEY", ""),
            azure_endpoint=env.get("AZURE_OPENAI_API_BASE", ""),
            api_version="2024-05-01-preview",
            azure_deployment=deployment_id,
            model=gpt4_model,
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            api_key=env.get("OPENAI_API_KEY"),
            model=gpt4_model,
            temperature=0,
        )
    return llm


@lru_cache(maxsize=1)
def load_gpt4o_llm():
    """Load GPT-4o Model. Make sure your key have access to GPT-4o API."""
    # Get the specific GPT-4o model name from environment variable or use default
    gpt4o_model = env.get("GPT4O_MODEL", "gpt-4o")

    if env.get("AZURE_OPENAI"):
        # For Azure, use the GPT-4o deployment ID if available
        deployment_id = env.get("AZURE_OPENAI_GPT4O_DEPLOYMENT_ID", env.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-4o"))

        llm = AzureChatOpenAI(
            openai_api_type="azure",
            api_key=env.get("AZURE_OPENAI_API_KEY", ""),
            azure_endpoint=env.get("AZURE_OPENAI_API_BASE", ""),
            api_version="2024-05-01-preview",
            azure_deployment=deployment_id,
            model=gpt4o_model,
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            api_key=env.get("OPENAI_API_KEY"),
            model=gpt4o_model,
            temperature=0,
        )
    return llm


@lru_cache(maxsize=1)
def load_deepseek_llm():
    """Load DeepSeek model"""
    llm = DeepSeekChatModel(
        api_key=env.get("DEEPSEEK_API_KEY"),
        model_name=env.get("DEEPSEEK_MODEL"),
        api_base=env.get("DEEPSEEK_API_BASE"),
        temperature=float(env.get("DEEPSEEK_TEMPERATURE", "0")),
        max_tokens=int(env.get("DEEPSEEK_MAX_TOKENS", "4096")),
        top_p=float(env.get("DEEPSEEK_TOP_P", "0.95")),
        timeout=int(env.get("DEEPSEEK_TIMEOUT", "600")),  # 默认超时时间增加到10分钟
        max_retries=int(env.get("DEEPSEEK_MAX_RETRIES", "3")),  # 最大重试次数
        retry_delay=int(env.get("DEEPSEEK_RETRY_DELAY", "5")),  # 重试间隔（秒）
    )
    return llm


@lru_cache(maxsize=1)
def load_deepseek_r1_llm():
    """Load DeepSeek R1 model"""
    llm = DeepSeekR1Model(
        api_key=env.get("DEEPSEEK_API_KEY"),
        model_name=env.get("DEEPSEEK_R1_MODEL"),
        api_base=env.get("DEEPSEEK_R1_API_BASE", env.get("DEEPSEEK_API_BASE")),
        temperature=float(env.get("DEEPSEEK_TEMPERATURE", "0")),
        max_tokens=int(env.get("DEEPSEEK_MAX_TOKENS", "4096")),
        top_p=float(env.get("DEEPSEEK_TOP_P", "0.95")),
        timeout=int(env.get("DEEPSEEK_TIMEOUT", "600")),  # 默认超时时间增加到10分钟
        max_retries=int(env.get("DEEPSEEK_MAX_RETRIES", "3")),  # 最大重试次数
        retry_delay=int(env.get("DEEPSEEK_RETRY_DELAY", "5")),  # 重试间隔（秒）
    )
    return llm


def load_model_by_name(model_name: str) -> BaseChatModel:
    """Load a model by name

    Args:
        model_name: The name of the model to load. Can be:
            - "gpt-3.5" or any string starting with "gpt-3" for GPT-3.5 models
            - "gpt-4" or any string starting with "gpt-4" (except gpt-4o) for GPT-4 models
            - "gpt-4o" or "4o" for GPT-4o models
            - "deepseek" for DeepSeek models
            - "deepseek-r1" for DeepSeek R1 models
            - Any full OpenAI model name (e.g., "gpt-3.5-turbo-16k", "gpt-4-turbo", etc.)

    Returns:
        BaseChatModel: The loaded model

    Raises:
        ValueError: If the model name is not recognized
    """
    # Define standard model loaders
    model_loaders = {
        "gpt-3.5": load_gpt_llm,
        "gpt-4": load_gpt4_llm,
        "gpt-4o": load_gpt4o_llm,
        "4o": load_gpt4o_llm,
        "deepseek": load_deepseek_llm,
        "deepseek-r1": load_deepseek_r1_llm,
    }

    # Check for exact matches first
    if model_name in model_loaders:
        return model_loaders[model_name]()

    # Handle OpenAI model names with pattern matching
    if model_name.startswith("gpt-"):
        # Handle GPT-4o models
        if "4o" in model_name.lower():
            return load_gpt4o_llm()
        # Handle GPT-4 models
        elif model_name.startswith("gpt-4"):
            return load_gpt4_llm()
        # Handle GPT-3 models
        elif model_name.startswith("gpt-3"):
            return load_gpt_llm()
        # For any other GPT models, default to GPT-3.5
        else:
            logger.warning(f"Unrecognized GPT model name: {model_name}, defaulting to GPT-3.5")
            return load_gpt_llm()

    # If we get here, the model name is not recognized
    raise ValueError(f"Unknown model name: {model_name}. Available models: {list(model_loaders.keys())} or any OpenAI model name starting with 'gpt-'.")
