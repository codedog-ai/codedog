from __future__ import annotations

from itertools import zip_longest
from typing import List

from langchain_core.language_models import BaseLanguageModel
from langchain.chains import LLMChain
from langchain_core.prompts import BasePromptTemplate
from pydantic import Field

from codedog.chains.code_review.base import CodeReviewChain
from codedog.chains.code_review.prompts import CODE_REVIEW_PROMPT
from codedog.chains.prompts import TRANSLATE_PROMPT
from codedog.models import ChangeFile, CodeReview
from codedog.processors.pull_request_processor import PullRequestProcessor


class TranslateCodeReviewChain(CodeReviewChain):
    # TODO: use multiple parent classes to avoid code duplication. Not sure how to do this with pydantic.

    language: str = Field()
    """The language you want to translate into.

    Note that default review result is usually in English. If language is set to english it will also call llm
    """
    translate_chain: LLMChain = Field(exclude=True)
    """Chain to use to translate code review result."""

    @classmethod
    def from_llm(
        cls,
        *,
        language: str,
        llm: BaseLanguageModel,
        translate_llm: BaseLanguageModel,
        prompt: BasePromptTemplate = CODE_REVIEW_PROMPT,
        translate_prompt: BasePromptTemplate = TRANSLATE_PROMPT,
        **kwargs,
    ) -> CodeReviewChain:
        return cls(
            language=language,
            chain=LLMChain(llm=llm, prompt=prompt, **kwargs),
            translate_chain=LLMChain(
                llm=translate_llm, prompt=translate_prompt, **kwargs
            ),
            processor=PullRequestProcessor(),
        )

    def _process_result(self, code_files: List[ChangeFile], code_review_outputs: List):
        code_reviews = []
        for i, o in zip_longest(code_files, code_review_outputs):
            code_reviews.append(CodeReview(file=i, review=o["text"]))

        code_reviews = self._translate(code_reviews)
        return {"code_reviews": code_reviews}

    async def _aprocess_result(
        self, code_files: List[ChangeFile], code_review_outputs: List
    ):
        code_reviews = []
        for i, o in zip_longest(code_files, code_review_outputs):
            code_reviews.append(CodeReview(file=i, review=o["text"]))

        code_reviews = await self._atranslate(code_reviews)
        return {"code_reviews": code_reviews}

    def _translate(self, code_reviews: List[CodeReview]) -> List[CodeReview]:
        data = [
            {
                "language": self.language,
                "description": "Suggestion for a changed file",
                "content": cr.review,
            }
            for cr in code_reviews
            if cr.review != ""
        ]
        response = self.translate_chain.apply(data) if data else []

        for cr, r in zip_longest(code_reviews, response):
            if not cr or not r:
                break

            cr.review = r["text"]
        return code_reviews

    async def _atranslate(self, code_reviews: List[CodeReview]) -> List[CodeReview]:
        data = [
            {
                "language": self.language,
                "description": "Suggestion for a changed file",
                "content": cr.review,
            }
            for cr in code_reviews
            if cr.review != ""
        ]
        response = await self.translate_chain.aapply(data) if data else []

        for cr, r in zip_longest(code_reviews, response):
            if not cr or not r:
                break

            cr.review = r["text"]
        return code_reviews
