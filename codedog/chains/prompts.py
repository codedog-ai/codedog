from langchain import PromptTemplate

from codedog.templates import grimoire_en

TRANSLATE_PROMPT = PromptTemplate(
    template=grimoire_en.TRANSLATE_PR_REVIEW, input_variables=["language", "description", "content"]
)
