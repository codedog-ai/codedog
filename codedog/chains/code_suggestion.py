from langchain import LLMChain, PromptTemplate
from langchain.base_language import BaseLanguageModel

from codedog.templates import grimoire_en

# TODO: Localization
CODE_SUGGESTION_PROMPT = PromptTemplate(
    template=grimoire_en.CODE_SUGGESTION, input_variables=["name", "language", "content"]
)


def build_code_suggestion(llm: BaseLanguageModel) -> LLMChain:
    return LLMChain(llm=llm, prompt=CODE_SUGGESTION_PROMPT)
