import os
from functools import lru_cache

from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain.chat_models.base import BaseChatModel


@lru_cache(maxsize=1)
def load_gpt_llm() -> BaseChatModel:
    if os.environ.get("AZURE_OPENAI"):
        llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            openai_api_base=os.environ.get("AZURE_OPENAI_API_BASE"),
            openai_api_version="2023-05-15",
            deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-35-turbo"),
            model=os.environ.get("AZURE_OPENAI_MODEL", "gpt-3.5-turbo"),
            temperature=0,
        )
    else:
        llm = ChatOpenAI(
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
        )
    return llm


@lru_cache(maxsize=1)
def load_gpt4_llm():
    return ChatOpenAI(openai_api_key=os.environ.get("OPENAI_API_KEY"), model="gpt-4")
