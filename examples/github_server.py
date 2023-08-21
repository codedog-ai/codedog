"""
demo github api server
"""
import asyncio
import logging
import threading
import time

import uvicorn
from fastapi import FastAPI
from github import Github
from langchain.callbacks import get_openai_callback
from pydantic import BaseModel

from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.chains.code_review.base import CodeReviewChain
from codedog.chains.pr_summary.base import PRSummaryChain
from codedog.retrievers.github_retriever import GithubRetriever
from codedog.utils.langchain_utils import load_gpt4_llm, load_gpt_llm
from codedog.version import VERSION

# config
host = "127.0.0.1"
port = 32167
worker_num = 1
github_token = "your github token here"

# fastapi
app = FastAPI()


class GithubEvent(BaseModel):
    action: str
    number: int
    pull_request: dict
    repository: dict


@app.post("/github")
async def github(event: GithubEvent):
    """Github webhook.

    Args:
        request (GithubEvent): Github event.
    Returns:
        Response: message.
    """
    try:
        message = handle_github_event(event)
    except Exception as e:
        return str(e)
    return message


def handle_github_event(event: GithubEvent, **kwargs) -> str:
    _github_event_filter(event)

    repository_id: int = event.repository.get("id", 0)
    pull_request_number: int = event.number

    logging.info(
        f"Retrive pull request from Github {repository_id} {pull_request_number}"
    )

    thread = threading.Thread(
        target=asyncio.run,
        args=(handle_pull_request(repository_id, pull_request_number, **kwargs),),
    )
    thread.start()

    return "Review Submitted."


async def handle_pull_request(
    repository_id: int,
    pull_request_number: int,
    local=False,
    language="en",
    **kwargs,
):
    t = time.time()
    client = Github(github_token)
    retriever = GithubRetriever(
        client=client,
        repository_name_or_id=repository_id,
        pull_request_number=pull_request_number,
    )
    summary_chain = PRSummaryChain.from_llm(
        code_summary_llm=load_gpt_llm(), pr_summary_llm=load_gpt4_llm()
    )
    review_chain = CodeReviewChain.from_llm(llm=load_gpt_llm())

    with get_openai_callback() as cb:
        summary_result = summary_chain({"pull_request": retriever.pull_request})
        review_result = review_chain({"pull_request": retriever.pull_request})

        reporter = PullRequestReporter(
            pr_summary=summary_result["pr_summary"],
            code_summaries=summary_result["code_summaries"],
            pull_request=retriever.pull_request,
            code_reviews=review_result["code_reviews"],
            telemetry={
                "start_time": t,
                "time_usage": time.time() - t,
                "cost": cb.total_cost,
                "tokens": cb.total_tokens,
            },
            language=language,
        )
        report = reporter.report()
        if local:
            print(report)
        else:
            retriever._git_pull_request.create_issue_comment(report)


def _github_event_filter(event: GithubEvent):
    """filter github event.

    Args:
        event (GithubEvent): github event.

    Returns:
        bool: True if the event is filtered.
    """
    pull_request = event.pull_request

    if not pull_request:
        raise RuntimeError("Not a pull request event.")
    if event.action not in ("opened"):
        raise RuntimeError("Not a pull request open event.")
    if pull_request.get("state", "") != "open":
        raise RuntimeError("Pull request status is not open.")
    if pull_request.get("draft", False):
        raise RuntimeError("Pull request is a draft")


def start():
    uvicorn.run("examples.github_server:app", host=host, port=port, workers=worker_num)
    logging.info(f"Codedog v{VERSION}: server start.")


if __name__ == "__main__":
    start()
