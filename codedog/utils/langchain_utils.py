from functools import lru_cache
from os import environ as env

from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain.chat_models.base import BaseChatModel


@lru_cache(maxsize=1)
def load_gpt_llm() -> BaseChatModel:
    """Load GPT 3.5 Model"""
    if env.get("AZURE_OPENAI"):
        llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_key=env.get("AZURE_OPENAI_API_KEY", ""),
            openai_api_base=env.get("AZURE_OPENAI_API_BASE", ""),
            openai_api_version="2024-05-01-preview",
            deployment_name=env.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-35-turbo"),
            model="gpt-3.5-turbo",
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            openai_api_key=env.get("OPENAI_API_KEY"),
            model="gpt-3.5-turbo",
        )
    return llm


@lru_cache(maxsize=1)
def load_gpt4_llm():
    """Load GPT 4 Model. Make sure your key have access to GPT 4 API. call this function won't check it."""
    if env.get("AZURE_OPENAI"):
        llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_key=env.get("AZURE_OPENAI_API_KEY", ""),
            openai_api_base=env.get("AZURE_OPENAI_API_BASE", ""),
            openai_api_version="2024-05-01-preview",
            deployment_name=env.get("AZURE_OPENAI_GPT4_DEPLOYMENT_ID", "gpt-4"),
            model="gpt-4",
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            openai_api_key=env.get("OPENAI_API_KEY"),
            model="gpt-4",
        )
    return llm
