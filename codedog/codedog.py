import time

from github import Github
from langchain.callbacks import get_openai_callback

from codedog.chains import CodeReviewChain, PRSummaryChain
from codedog.retrievers import GithubRetriever
from codedog.utils.github_utils import load_github_client
from codedog.utils.langchain_utils import load_gpt4_llm, load_gpt_llm


def summarize_github_pr(
    *,
    pull_request_number: int,
    repository_full_name: str,
    client: Github = None,
    use_gpt4: bool = True,
    verbose: bool = False,
    include_run_info: bool = False,
):
    t = time.time()
    llm_gpt_secondary = load_gpt_llm()
    llm_gpt = load_gpt4_llm() if use_gpt4 else load_gpt_llm()
    client: Github = load_github_client() if not client else client
    retriever = GithubRetriever(client, repository_full_name, pull_request_number)
    chain = PRSummaryChain.from_llm(code_summary_llm=llm_gpt_secondary, pr_summary_llm=llm_gpt, verbose=verbose)

    with get_openai_callback() as cb:
        result = chain({"pull_request": retriever.pull_request}, include_run_info=include_run_info)
        if include_run_info:
            status = {"time_usage": time.time() - t, "tokens": cb.total_tokens, "cost": cb.total_cost}
            result["status"] = status
    return result


def review_code_github_pr(
    *,
    pull_request_number: int,
    repository_full_name: str,
    client: Github = None,
    use_gpt4: bool = True,
    verbose: bool = False,
    include_run_info: bool = False,
):
    t = time.time()
    llm_gpt = load_gpt4_llm() if use_gpt4 else load_gpt_llm()
    client: Github = load_github_client() if not client else client
    retriever = GithubRetriever(client, repository_full_name, pull_request_number)
    chain = CodeReviewChain.from_llm(llm=llm_gpt, verbose=verbose)

    with get_openai_callback() as cb:
        result = chain({"pull_request": retriever.pull_request}, include_run_info=include_run_info)
        if include_run_info:
            status = {"time_usage": time.time() - t, "tokens": cb.total_tokens, "cost": cb.total_cost}
            result["status"] = status

    return result
