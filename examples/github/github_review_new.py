import json
import os
import time

import openai
from fastapi.encoders import jsonable_encoder
from github import Github
from langchain.callbacks import get_openai_callback
from langchain_visualizer import visualize

from codedog.chains import CodeReviewChain, PRSummaryChain
from codedog.retrievers import GithubRetriever
from codedog.utils.langchain_utils import load_gpt4_llm, load_gpt_llm

github_token = os.environ.get("GITHUB_TOKEN", "")
gh = Github(github_token)
retriever = GithubRetriever(gh, "codedog-ai/codedog", 2)
# retriever = GithubRetriever(gh, "ClickHouse/ClickHouse", 49113)
# retriever = GithubRetriever(gh, "langchain-ai/langchain", 8171)

openai_proxy = os.environ.get("OPENAI_PROXY", "")
if openai_proxy:
    openai.proxy = openai_proxy

summary_chain = PRSummaryChain.from_llm(code_summary_llm=load_gpt_llm(), pr_summary_llm=load_gpt4_llm(), verbose=True)
review_chain = CodeReviewChain.from_llm(llm=load_gpt_llm(), verbose=True)


def pr_summary():
    with get_openai_callback() as cb:
        result = summary_chain({"pull_request": retriever.pull_request}, include_run_info=True)
        print(json.dumps(jsonable_encoder(result), ensure_ascii=False, indent=4))
        print(f"Summary cost is: ${cb.total_cost:.4f}")


def code_review():
    with get_openai_callback() as cb:
        result = review_chain({"pull_request": retriever.pull_request}, include_run_info=True)
        print(json.dumps(jsonable_encoder(result), ensure_ascii=False, indent=4))
        print(f"Review cost is: ${cb.total_cost:.4f}")


async def run():
    with get_openai_callback() as cb:
        # pr_summary()
        code_review()
        print(f"Total cost is: ${cb.total_cost:.4f}")


visualize(run)

time.sleep(30)
