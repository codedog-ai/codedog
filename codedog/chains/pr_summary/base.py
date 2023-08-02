from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain import BasePromptTemplate, LLMChain
from langchain.base_language import BaseLanguageModel
from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain.schema import BaseOutputParser
from pydantic import Extra, Field

from codedog.chains.pr_summary.prompts import CODE_SUMMARY_PROMPT, PR_SUMMARY_PROMPT
from codedog.models import ChangeSummary, PRSummary, PullRequest
from codedog.processors.pull_request_processor import (
    SUFFIX_LANGUAGE_MAPPING,
    PullRequestProcessor,
)


class PRSummaryChain(Chain):
    """Summarize a pull request.

    Inputs are:
    - pull_request(PullRequest): a pull request object

    Outputs are:
    - pr_summary(PRSummary): summary of pull request.
    - code_summaries(Dict[str, str]): changed code file summarizations, key is file path.
    """

    # TODO: localization
    # TODO: input keys validation

    code_summary_chain: LLMChain = Field(exclude=True)
    """Chain to use to summarize code change."""
    pr_summary_chain: LLMChain = Field(exclude=True)
    """Chain to use to summarize PR."""
    parser: BaseOutputParser = Field(exclude=True)
    """Parse pr summarized result to PRSummary object."""
    processor: PullRequestProcessor = Field(exclude=True, default_factory=PullRequestProcessor.build)
    """PR data process."""
    _input_keys: List[str] = ["pull_request"]
    _output_keys: List[str] = ["pr_summary", "code_summaries"]

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def _chain_type(self) -> str:
        return "pull_request_summary_chain"

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

    def _call(self, inputs: Dict[str, Any], run_manager: Optional[CallbackManagerForChainRun] = None) -> Dict[str, Any]:
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        _run_manager.on_text(inputs["pull_request"].json() + "\n")

        pr: PullRequest = inputs["pull_request"]

        code_summary_inputs = self._process_code_summary_inputs(pr, _run_manager)
        code_summary_outputs = (
            self.code_summary_chain.apply(code_summary_inputs, callbacks=_run_manager.get_child(tag="CodeSummary"))
            if code_summary_inputs
            else []
        )

        code_summaries = self.processor.build_change_summaries(code_summary_inputs, code_summary_outputs)

        pr_summary_input = self._process_pr_summary_input(pr, code_summaries)
        pr_summary_output: PRSummary = self.pr_summary_chain(
            pr_summary_input, callbacks=_run_manager.get_child(tag="PRSummary")
        )

        return self._process_result(pr_summary_output, code_summaries)

    async def _acall(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        _run_manager.on_text(inputs["pull_request"].json() + "\n")

        pr: PullRequest = inputs["pull_request"]

        code_summary_inputs = self._process_code_summary_inputs(pr, _run_manager)
        code_summary_outputs = (
            await self.code_summary_chain.aapply(code_summary_inputs, callbacks=_run_manager.get_child())
            if code_summary_inputs
            else []
        )

        code_summaries = self.processor.build_code_summaries(code_summary_inputs, code_summary_outputs)

        pr_summary_input = self._process_pr_summary_input(pr, code_summaries)
        pr_summary_output: PRSummary = await self.pr_summary_chain(pr_summary_input, callbacks=_run_manager.get_child())

        return self._process_result(pr_summary_output, code_summaries)

    def _process_code_summary_inputs(
        self, pr: PullRequest, run_manager: CallbackManagerForChainRun
    ) -> List[Dict[str, str]]:
        input_data = []
        code_files = self.processor.get_diff_code_files(pr)
        for code_file in code_files:
            input_item = {
                "content": code_file.diff_content.content[:2000],  # TODO: handle long diff
                "name": code_file.full_name,
                "language": SUFFIX_LANGUAGE_MAPPING.get(code_file.suffix, ""),
            }
            input_data.append(input_item)

        run_manager.on_text(f"Prepare code diff content for {len(input_data)} files.\n")
        return input_data

    def _process_pr_summary_input(self, pr: PullRequest, code_summaries: List[ChangeSummary]) -> Dict[str, str]:
        change_files_material: str = self.processor.gen_material_change_files(pr.change_files)
        code_summaries_material = self.processor.gen_material_code_summaries(code_summaries)
        pr_metadata_material = self.processor.gen_material_pr_metadata(pr)
        return {
            "change_files": change_files_material,
            "code_summaries": code_summaries_material,
            "metadata": pr_metadata_material,
        }

    def _process_result(self, pr_summary_output: Dict[str, Any], code_summaries: List[ChangeSummary]):
        return {
            "pr_summary": pr_summary_output["text"],
            "code_summaries": code_summaries,
        }

    @classmethod
    def from_llm(
        cls,
        code_summary_llm: BaseLanguageModel,
        pr_summary_llm: BaseLanguageModel,
        code_summary_prompt: BasePromptTemplate = CODE_SUMMARY_PROMPT,
        pr_summary_prompt: BasePromptTemplate = PR_SUMMARY_PROMPT,
        **kwargs: Any,
    ) -> PRSummaryChain:
        parser = OutputFixingParser.from_llm(llm=pr_summary_llm, parser=PydanticOutputParser(pydantic_object=PRSummary))
        code_summary_chain = LLMChain(llm=code_summary_llm, prompt=code_summary_prompt)
        pr_summary_chain = LLMChain(llm=pr_summary_llm, prompt=pr_summary_prompt, output_parser=parser)
        return cls(code_summary_chain=code_summary_chain, pr_summary_chain=pr_summary_chain, parser=parser, **kwargs)
