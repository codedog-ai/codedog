from functools import lru_cache
from os import environ as env
from typing import Dict, Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, ConfigDict


# Define a custom class for DeepSeek model since it's not available in langchain directly
class DeepSeekChatModel(BaseChatModel):
    """DeepSeek model wrapper for langchain"""
    
    model_name: str = Field(default="deepseek-chat")
    api_key: str
    api_base: str = Field(default="https://api.deepseek.com")
    temperature: float = Field(default=0)
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
    )
    
    @property
    def _llm_type(self) -> str:
        """Return type of LLM."""
        return "deepseek"
    
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Implementation for DeepSeek API"""
        try:
            import requests
            import json
            
            # Convert LangChain messages to DeepSeek format
            deepseek_messages = []
            for message in messages:
                if isinstance(message, HumanMessage):
                    deepseek_messages.append({"role": "user", "content": message.content})
                elif isinstance(message, SystemMessage):
                    deepseek_messages.append({"role": "system", "content": message.content})
                else:  # AIMessage or other
                    deepseek_messages.append({"role": "assistant", "content": message.content})
            
            # Prepare the API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model_name,
                "messages": deepseek_messages,
                "temperature": self.temperature,
                **self.model_kwargs
            }
            
            if stop:
                payload["stop"] = stop
            
            # Make the API call
            response = requests.post(
                f"{self.api_base}/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            if response.status_code != 200:
                raise Exception(f"DeepSeek API error: {response.status_code}, {response.text}")
            
            response_data = response.json()
            
            # Convert the response to LangChain format
            message = AIMessage(content=response_data["choices"][0]["message"]["content"])
            generation = ChatGeneration(message=message)
            
            return ChatResult(generations=[generation])
        except Exception as e:
            import traceback
            print(f"DeepSeek API error: {str(e)}")
            print(traceback.format_exc())
            # 如果 API 调用失败，返回一个默认消息
            message = AIMessage(content="I'm sorry, but I couldn't process your request.")
            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])
    
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        """Async implementation for DeepSeek API"""
        try:
            import aiohttp
            import json
            
            # Convert LangChain messages to DeepSeek format
            deepseek_messages = []
            for message in messages:
                if isinstance(message, HumanMessage):
                    deepseek_messages.append({"role": "user", "content": message.content})
                elif isinstance(message, SystemMessage):
                    deepseek_messages.append({"role": "system", "content": message.content})
                else:  # AIMessage or other
                    deepseek_messages.append({"role": "assistant", "content": message.content})
            
            # Prepare the API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model_name,
                "messages": deepseek_messages,
                "temperature": self.temperature,
                **self.model_kwargs
            }
            
            if stop:
                payload["stop"] = stop
            
            # Make the API call
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(payload)
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        raise Exception(f"DeepSeek API error: {response.status}, {response_text}")
                    
                    response_data = await response.json()
            
            # Convert the response to LangChain format
            message = AIMessage(content=response_data["choices"][0]["message"]["content"])
            generation = ChatGeneration(message=message)
            
            return ChatResult(generations=[generation])
        except Exception as e:
            import traceback
            print(f"DeepSeek API error: {str(e)}")
            print(traceback.format_exc())
            # 如果 API 调用失败，返回一个默认消息
            message = AIMessage(content="I'm sorry, but I couldn't process your request.")
            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])


# Define a custom class for DeepSeek R1 model
class DeepSeekR1Model(DeepSeekChatModel):
    """DeepSeek R1 model wrapper for langchain"""
    
    model_name: str = Field(default="deepseek-reasoner")
    api_base: str = Field(default="https://api.deepseek.com")
    
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
        model_name=env.get("DEEPSEEK_MODEL", "deepseek-chat"),
        api_base=env.get("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
        temperature=0,
    )
    return llm


@lru_cache(maxsize=1)
def load_deepseek_r1_llm():
    """Load DeepSeek R1 model"""
    llm = DeepSeekR1Model(
        api_key=env.get("DEEPSEEK_API_KEY"),
        api_base=env.get("DEEPSEEK_R1_API_BASE", env.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")),
        temperature=0,
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
