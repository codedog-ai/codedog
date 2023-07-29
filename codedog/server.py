"""
demo api server
"""
import asyncio
import logging
import threading
import time
import traceback
from os import environ as env

import openai
import uvicorn
from fastapi import FastAPI
from langchain.callbacks import get_openai_callback
from pydantic import BaseModel

from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.chains.code_review.base import CodeReviewChain
from codedog.chains.pr_summary.base import PRSummaryChain
from codedog.retrievers.github_retriever import GithubRetriever
from codedog.utils import init_local_logging
from codedog.utils.github_utils import load_github_client
from codedog.utils.langchain_utils import load_gpt4_llm, load_gpt_llm
from codedog.version import VERSION

# logging
init_local_logging()
logger = logging.getLogger(__name__)

# config
host = env.get("CODEDOG_SERVER", "0.0.0.0")
port = int(env.get("CODEDOG_PORT", 32167))
worker_num = int(env.get("CODEDOG_WORKER_NUM", 1))
openai_proxy = env.get("OPENAI_PROXY", "")
if openai_proxy:
    openai.proxy = openai_proxy
github_token = env.get("GITHUB_TOKEN", "")

# fastapi
app = FastAPI()


class GithubEvent(BaseModel):
    action: str
    number: int
    pull_request: dict
    repository: dict


class Response(BaseModel):
    message: str
    code: int = 0


class CodedogError(Exception):
    def __init__(self, message: str = None, code: int = -1):
        self.message = "" if message is None else message
        self.code = code


@app.post("/github", response_model=Response)
async def github(event: GithubEvent) -> Response:
    """Github webhook.

    Args:
        request (GithubEvent): Github event.
    Returns:
        Response: message.
    """
    try:
        message = handle_github_event(event)
    except CodedogError as e:
        return Response(message=e.message, code=e.code)
    except Exception:
        logger.fatal("Internal Service Error:\n%s", traceback.format_exc())
        return Response(message="Internal Service Error", code=-2)
    return Response(message=message, code=0)


def handle_github_event(event: GithubEvent, **kwargs) -> str:
    _github_event_filter(event)

    repository_id: int = event.repository.get("id", 0)
    pull_request_number: int = event.number

    logger.info(
        "Retrive pull request from Github",
        extra={
            "github.repo.id": repository_id,
            "github.pull.number": pull_request_number,
        },
    )

    thread = threading.Thread(
        target=asyncio.run, args=(handle_pull_request(repository_id, pull_request_number, **kwargs),)
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
    client = load_github_client(token=github_token)
    retriever = GithubRetriever(
        client=client,
        repository_name_or_id=repository_id,
        pull_request_number=pull_request_number,
    )
    summary_chain = PRSummaryChain.from_llm(code_summary_llm=load_gpt_llm(), pr_summary_llm=load_gpt4_llm())
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


def _github_event_filter(event: GithubEvent) -> bool:
    """filter github event.

    Args:
        event (GithubEvent): github event.

    Returns:
        bool: True if the event is filtered.
    """
    pull_request = event.pull_request

    if not pull_request:
        raise CodedogError("Not a pull request event.", 1)
    if event.action not in ("opened"):
        raise CodedogError("Not a pull request open event.", 1)
    if pull_request.get("state", "") != "open":
        raise CodedogError("Pull request status is not open.", 1)
    if pull_request.get("draft", False):
        raise CodedogError("Pull request is a draft", 1)


def start():
    uvicorn.run("codedog.server:app", host=host, port=port, workers=worker_num)
    logger.info(f"Codedog v{VERSION}: server start.")


if __name__ == "__main__":
    start()
