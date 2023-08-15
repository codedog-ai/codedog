import asyncio
import time
from os import environ as env

import openai
from github import Github
from langchain.callbacks import get_openai_callback
from langchain_visualizer import visualize

from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.chains import CodeReviewChain, PRSummaryChain
from codedog.retrievers import GithubRetriever
from codedog.utils.langchain_utils import load_gpt4_llm, load_gpt_llm

github_token = env.get("GITHUB_TOKEN", "")
gh = Github(github_token)
retriever = GithubRetriever(gh, "codedog-ai/codedog", 2)
# retriever = GithubRetriever(gh, "langchain-ai/langchain", 8171)
# retriever = GithubRetriever(gh, "ClickHouse/ClickHouse", 49113)

openai_proxy = env.get("OPENAI_PROXY", "")
if openai_proxy:
    openai.proxy = openai_proxy

summary_chain = PRSummaryChain.from_llm(
    code_summary_llm=load_gpt_llm(), pr_summary_llm=load_gpt4_llm(), verbose=True
)
review_chain = CodeReviewChain.from_llm(llm=load_gpt_llm(), verbose=True)


async def pr_summary():
    result = await summary_chain.acall(
        {"pull_request": retriever.pull_request}, include_run_info=True
    )
    return result


async def code_review():
    result = await review_chain.acall(
        {"pull_request": retriever.pull_request}, include_run_info=True
    )
    return result


def report():
    t = time.time()
    with get_openai_callback() as cb:
        p = asyncio.run(pr_summary())
        p_cost = cb.total_cost
        print(f"Summary cost is: ${p_cost:.4f}")

        c = asyncio.run(code_review())
        c_cost = cb.total_cost - p_cost

        print(f"Review cost is: ${c_cost:.4f}")
        reporter = PullRequestReporter(
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

time.sleep(60)
