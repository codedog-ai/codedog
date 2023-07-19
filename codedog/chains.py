import os

from langchain import LLMChain, PromptTemplate
from langchain.chat_models import AzureChatOpenAI, ChatOpenAI
from langchain.chat_models.base import BaseChatModel
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser

from codedog.model import ChangeSummary
from codedog.templates import grimoire_cn

GRIMOIRE = grimoire_cn


class Chains:
    def __init__(self, llm: BaseChatModel):
        self._review_fallback_prompt = PromptTemplate.from_template(GRIMOIRE.PR_CHANGE_REVIEW_FALLBACK_TEMPLATE)
        self._summary_prompt = PromptTemplate.from_template(GRIMOIRE.PR_SUMMARIZE_TEMPLATE)
        self._feedback_prompt = PromptTemplate.from_template(GRIMOIRE.PR_SIMPLE_FEEDBACK_TEMPLATE)
        self._raw_review_parser = PydanticOutputParser(pydantic_object=ChangeSummary)
        self._review_parser = OutputFixingParser.from_llm(llm=llm, parser=self._raw_review_parser)
        self._review_prompt = PromptTemplate(
            template=GRIMOIRE.PR_CHANGE_REVIEW_TEMPLATE,
            input_variables=["text", "name"],
            partial_variables={"format_instructions": self._raw_review_parser.get_format_instructions()},
        )
        self._review_chain = LLMChain(llm=llm, prompt=self._review_prompt)
        self._review_fallback_chain = LLMChain(llm=llm, prompt=self._review_fallback_prompt)

        self._summary_chain = LLMChain(llm=llm, prompt=self._summary_prompt)
        self._feedback_chain = LLMChain(llm=llm, prompt=self._feedback_prompt)

    @staticmethod
    def init_chains():
        llm = load_llm()
        return Chains(llm=llm)

    @property
    def llm(self):
        return self._llm

    def set_llm(self, llm: BaseChatModel):
        self._llm = llm
        self._init_with_llm(llm)

    @property
    def review_parser(self):
        return self._review_parser

    @property
    def review_chain(self):
        return self._review_chain

    @property
    def review_fallback_chain(self):
        return self._review_fallback_chain

    @property
    def summary_chain(self):
        return self._summary_chain

    @property
    def feedback_chain(self):
        return self._feedback_chain


def load_llm() -> BaseChatModel:
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
