from langchain.base_language import BaseLanguageModel
from langchain.chains.base import Chain
from pydantic import Extra


class PRSummaryChain(Chain):
    """Summarize a pull request.

    Inputs are:
    - pull_request(PullRequest): a pull request object

    Outputs are:
    - pr_summary(str): pull request summarization
    - classification(str): feature, refactor, fix, doc, ci, test, style, chore etc.
    - major_files(list[str]): for a feature pr, contains fullname of the files with major logic changes.
    - code_summaries(dict[str, str]): changed code file summarizations, key is file path.
    """

    llm: BaseLanguageModel
    """Language model to use."""

    llm_side: BaseLanguageModel
    """Language model to use for secondary tasks. You may want to specify a cost efficient model here.

    Including tasks: none
    """

    input_key: str = ["pull_request"]
    output_key: str = ["pr_summary", "classification", "major_files", "code_summaries"]

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def input_keys(self) -> list[str]:
        """Will be whatever keys the prompt expects."""
        return self.input_key

    @property
    def output_keys(self) -> list[str]:
        """Will always return text key."""
        return [self.output_key]

    @property
    def _chain_type(self) -> str:
        return "pull_request_summary_chain"
