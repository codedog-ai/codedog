from langchain import PromptTemplate
from langchain.output_parsers import PydanticOutputParser

from codedog.models import PRSummary
from codedog.templates import grimoire_en

parser = PydanticOutputParser(pydantic_object=PRSummary)

PR_SUMMARY_PROMPT = PromptTemplate(
    template=grimoire_en.PR_SUMMARY,
    input_variables=["metadata", "change_files", "code_summaries"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)
CODE_SUMMARY_PROMPT = PromptTemplate(template=grimoire_en.CODE_SUMMARY, input_variables=["name", "language", "content"])
