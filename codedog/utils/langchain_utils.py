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
    timeout: int = 300  # 增加默认超时时间到300秒
    total_tokens: int = 0
    total_cost: float = 0.0

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

            # Make API request with timeout
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(endpoint, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                        response_text = await response.text()

                        try:
                            response.raise_for_status()
                        except aiohttp.ClientResponseError as e:
                            log_error(e, f"DeepSeek API HTTP error (status {response.status})", response_text)
                            raise

                        try:
                            response_data = await response.json()
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

            except asyncio.TimeoutError as e:
                log_error(e, f"DeepSeek API request timed out after {self.timeout} seconds")
                raise

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
    if env.get("AZURE_OPENAI"):
        llm = AzureChatOpenAI(
            openai_api_type="azure",
            api_key=env.get("AZURE_OPENAI_API_KEY", ""),
            azure_endpoint=env.get("AZURE_OPENAI_API_BASE", ""),
            api_version="2024-05-01-preview",
            azure_deployment=env.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-35-turbo"),
            model="gpt-3.5-turbo",
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            api_key=env.get("OPENAI_API_KEY"),
            model="gpt-3.5-turbo",
        )
    return llm


@lru_cache(maxsize=1)
def load_gpt4_llm():
    """Load GPT 4 Model. Make sure your key have access to GPT 4 API. call this function won't check it."""
    if env.get("AZURE_OPENAI"):
        llm = AzureChatOpenAI(
            openai_api_type="azure",
            api_key=env.get("AZURE_OPENAI_API_KEY", ""),
            azure_endpoint=env.get("AZURE_OPENAI_API_BASE", ""),
            api_version="2024-05-01-preview",
            azure_deployment=env.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-35-turbo"),
            model="gpt-4",
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            api_key=env.get("OPENAI_API_KEY"),
            model="gpt-4",
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
        timeout=int(env.get("DEEPSEEK_TIMEOUT", "60")),
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
        timeout=int(env.get("DEEPSEEK_TIMEOUT", "60")),
    )
    return llm


def load_model_by_name(model_name: str) -> BaseChatModel:
    """Load a model by name"""
    model_loaders = {
        "gpt-3.5": load_gpt_llm,
        "gpt-4": load_gpt4_llm,
        "deepseek": load_deepseek_llm,
        "deepseek-r1": load_deepseek_r1_llm,
    }
    if model_name not in model_loaders:
        raise ValueError(f"Unknown model name: {model_name}. Available models: {list(model_loaders.keys())}")
    
    return model_loaders[model_name]()
