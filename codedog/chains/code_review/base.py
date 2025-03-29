from __future__ import annotations

from itertools import zip_longest
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseLanguageModel
from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains import LLMChain
from langchain.chains.base import Chain
from langchain_core.prompts import BasePromptTemplate
from pydantic import Field

from codedog.chains.code_review.prompts import CODE_REVIEW_PROMPT
from codedog.models import ChangeFile, CodeReview, PullRequest
from codedog.processors import PullRequestProcessor
from codedog.processors.pull_request_processor import SUFFIX_LANGUAGE_MAPPING


class CodeReviewChain(Chain):
    chain: LLMChain = Field(exclude=True)
    """Chain to use to review code change."""
    processor: PullRequestProcessor = Field(
        exclude=True, default_factory=PullRequestProcessor.build
    )
    """PR data process."""
    _input_keys: List[str] = ["pull_request"]
    _output_keys: List[str] = ["code_reviews"]

    @property
    def _chain_type(self) -> str:
        return "pull_request_code_review_chain"

    @property
    def input_keys(self) -> List[str]:
        """Will be whatever keys the prompt expects.

        :meta private:
        """
        return self._input_keys

    @property
    def output_keys(self) -> List[str]:
        """Will always return text key.

        :meta private:
        """
        return self._output_keys

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        _run_manager.on_text(inputs["pull_request"].json() + "\n")

        pr: PullRequest = inputs["pull_request"]
        code_files: List[ChangeFile] = self.processor.get_diff_code_files(pr)

        code_review_inputs = self._process_code_review_inputs(code_files)
        code_review_outputs = (
            self.chain.apply(
                code_review_inputs, callbacks=_run_manager.get_child(tag="CodeReview")
            )
            if code_review_inputs
            else []
        )

        return self._process_result(code_files, code_review_outputs)

    async def _acall(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        _run_manager = run_manager or AsyncCallbackManagerForChainRun.get_noop_manager()
        await _run_manager.on_text(inputs["pull_request"].json() + "\n")

        pr: PullRequest = inputs["pull_request"]
        code_files: List[ChangeFile] = self.processor.get_diff_code_files(pr)

        code_review_inputs = self._process_code_review_inputs(code_files)
        code_review_outputs = (
            await self.chain.aapply(
                code_review_inputs, callbacks=_run_manager.get_child(tag="CodeReview")
            )
            if code_review_inputs
            else []
        )

        return await self._aprocess_result(code_files, code_review_outputs)

    def _process_code_review_inputs(
        self,
        code_files: List[ChangeFile],
    ) -> List[Dict[str, str]]:
        input_data = []
        for code_file in code_files:
            input_item = {
                "content": code_file.diff_content.content[
                    :4000
                ],  # TODO: handle long diff with summarize chain
                "name": code_file.full_name,
                "language": SUFFIX_LANGUAGE_MAPPING.get(code_file.suffix, ""),
            }
            input_data.append(input_item)

        return input_data

    def _process_result(self, code_files: List[ChangeFile], code_review_outputs: List):
        code_reviews = []
        for i, o in zip_longest(code_files, code_review_outputs):
            code_reviews.append(CodeReview(file=i, review=o["text"]))
        return {"code_reviews": code_reviews}

    async def _aprocess_result(
        self, code_files: List[ChangeFile], code_review_outputs: List
    ):
        code_reviews = []
        for i, o in zip_longest(code_files, code_review_outputs):
            code_reviews.append(CodeReview(file=i, review=o["text"]))
        return {"code_reviews": code_reviews}

    @classmethod
    def from_llm(
        cls,
        *,
        llm: BaseLanguageModel,
        prompt: BasePromptTemplate = CODE_REVIEW_PROMPT,
        **kwargs,
    ) -> CodeReviewChain:
        return cls(
            chain=LLMChain(llm=llm, prompt=prompt, **kwargs),
            processor=PullRequestProcessor(),
        )
