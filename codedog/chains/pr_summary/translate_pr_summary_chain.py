from __future__ import annotations

from itertools import zip_longest
from typing import Any, Dict, List

from langchain_core.language_models import BaseLanguageModel
from langchain.chains import LLMChain
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.prompts import BasePromptTemplate
from pydantic import Field

from codedog.chains.pr_summary.base import PRSummaryChain
from codedog.chains.pr_summary.prompts import CODE_SUMMARY_PROMPT, PR_SUMMARY_PROMPT
from codedog.chains.prompts import TRANSLATE_PROMPT
from codedog.models import ChangeSummary, PRSummary


class TranslatePRSummaryChain(PRSummaryChain):
    language: str = Field()
    """The language you want to translate into.

    Note that default review result is usually in English. If language is set to english it will also call llm
    """

    translate_chain: LLMChain = Field(exclude=True)
    """Chain to use to translate summary result."""

    @classmethod
    def from_llm(
        cls,
        language: str,
        code_summary_llm: BaseLanguageModel,
        pr_summary_llm: BaseLanguageModel,
        translate_llm: BaseLanguageModel,
        code_summary_prompt: BasePromptTemplate = CODE_SUMMARY_PROMPT,
        pr_summary_prompt: BasePromptTemplate = PR_SUMMARY_PROMPT,
        translate_prompt: BasePromptTemplate = TRANSLATE_PROMPT,
        **kwargs,
    ) -> PRSummaryChain:
        parser = OutputFixingParser.from_llm(
            llm=pr_summary_llm, parser=PydanticOutputParser(pydantic_object=PRSummary)
        )
        code_summary_chain = LLMChain(llm=code_summary_llm, prompt=code_summary_prompt)
        pr_summary_chain = LLMChain(
            llm=pr_summary_llm, prompt=pr_summary_prompt, output_parser=parser
        )
        translate_chain = LLMChain(llm=translate_llm, prompt=translate_prompt)

        return cls(
            language=language,
            code_summary_chain=code_summary_chain,
            pr_summary_chain=pr_summary_chain,
            translate_chain=translate_chain,
            parser=parser,
            **kwargs,
        )

    def _process_result(
        self, pr_summary_output: Dict[str, Any], code_summaries: List[ChangeSummary]
    ) -> Dict[str, Any]:
        summary: PRSummary = pr_summary_output["text"]

        if self.language:
            summary = self._translate_summary(summary=summary)
            code_summaries = self._translate_code_summaries(
                code_summaries=code_summaries
            )

        return {
            "pr_summary": summary,
            "code_summaries": code_summaries,
        }

    async def _aprocess_result(
        self, pr_summary_output: Dict[str, Any], code_summaries: List[ChangeSummary]
    ) -> Dict[str, Any]:
        summary: PRSummary = pr_summary_output["text"]

        if self.language:
            summary = await self._atranslate_summary(summary=summary)
            code_summaries = await self._atranslate_code_summaries(
                code_summaries=code_summaries
            )

        return {
            "pr_summary": summary,
            "code_summaries": code_summaries,
        }

    def _translate_summary(self, summary: PRSummary) -> PRSummary:
        response = self.translate_chain(
            {"language": self.language, "description": "", "content": summary.overview}
        )
        summary.overview = response["text"]

        return summary

    def _translate_code_summaries(
        self, code_summaries: List[ChangeSummary]
    ) -> List[ChangeSummary]:
        data = [
            {
                "language": self.language,
                "description": "Changed file brief summary (must in single line!).",
                "content": cs.summary,
            }
            for cs in code_summaries
            if cs.summary != ""
        ]
        response = self.translate_chain.apply(data) if data else []

        for cs, r in zip_longest(code_summaries, response):
            if not cs or not r:
                break

            cs.summary = r["text"]
        return code_summaries

    async def _atranslate_summary(self, summary: PRSummary) -> PRSummary:
        response = await self.translate_chain.ainvoke(
            {
                "language": self.language,
                "description": "Changed file brief summary (must in single line!).",
                "content": summary.overview,
            }
        )

        summary.overview = response["text"]

        return summary

    async def _atranslate_code_summaries(
        self, code_summaries: List[ChangeSummary]
    ) -> List[ChangeSummary]:
        data = [
            {
                "language": self.language,
                "description": "Changed file brief summary.",
                "content": cs.summary,
            }
            for cs in code_summaries
            if cs.summary != ""
        ]
        response = await self.translate_chain.aapply(data) if data else []

        for cs, r in zip_longest(code_summaries, response):
            if not cs or not r:
                break

            cs.summary = r["text"]
        return code_summaries
