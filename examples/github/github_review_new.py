import os
import time

import openai
from github import Github
from langchain.callbacks import get_openai_callback
from langchain_visualizer import visualize

from codedog.actors.reporters.pull_request_review import (
    PullRequestReviewMarkdownReporter,
)
from codedog.chains import CodeReviewChain, PRSummaryChain
from codedog.retrievers import GithubRetriever
from codedog.utils.langchain_utils import load_gpt4_llm, load_gpt_llm

github_token = os.environ.get("GITHUB_TOKEN", "")
gh = Github(github_token)
# retriever = GithubRetriever(gh, "codedog-ai/codedog", 2)
# retriever = GithubRetriever(gh, "ClickHouse/ClickHouse", 49113)
retriever = GithubRetriever(gh, "langchain-ai/langchain", 8171)

openai_proxy = os.environ.get("OPENAI_PROXY", "")
if openai_proxy:
    openai.proxy = openai_proxy

summary_chain = PRSummaryChain.from_llm(code_summary_llm=load_gpt_llm(), pr_summary_llm=load_gpt4_llm(), verbose=True)
review_chain = CodeReviewChain.from_llm(llm=load_gpt_llm(), verbose=True)


def pr_summary():
    result = summary_chain({"pull_request": retriever.pull_request}, include_run_info=True)
    return result


def code_review():
    result = review_chain({"pull_request": retriever.pull_request}, include_run_info=True)
    return result


def report():
    t = time.time()
    with get_openai_callback() as cb:
        p = pr_summary()
        p_cost = cb.total_cost
        print(f"Summary cost is: ${p_cost:.4f}")

        c = code_review()
        c_cost = cb.total_cost - p_cost

        print(f"Review cost is: ${c_cost:.4f}")
        reporter = PullRequestReviewMarkdownReporter(
            pr_summary=p["pr_summary"],
            code_summaries=p["code_summaries"],
            pull_request=retriever.pull_request,
            code_reviews=c["code_reviews"],
            telemetry={
                "start_time": t,
                "time_usage": time.time() - t,
                "cost": cb.total_cost,
                "tokens": cb.total_tokens,
            },
        )
    return reporter.report()


async def run():
    result = report()
    print(result)


visualize(run)

time.sleep(30)
