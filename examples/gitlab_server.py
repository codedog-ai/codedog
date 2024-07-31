"""
demo gitlab api server
"""

import asyncio
import logging
import threading
import time
import traceback
from typing import Callable

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from gitlab import Gitlab
from gitlab.v4.objects import ProjectMergeRequest
from langchain_community.callbacks.manager import get_openai_callback
from pydantic import BaseModel

from codedog.actors.reporters.pull_request import PullRequestReporter
from codedog.chains.code_review.base import CodeReviewChain
from codedog.chains.pr_summary.base import PRSummaryChain
from codedog.retrievers.gitlab_retriever import GitlabRetriever
from codedog.utils.langchain_utils import load_gpt4_llm, load_gpt_llm
from codedog.version import VERSION

# config
host = "127.0.0.1"
port = 32167
worker_num = 1
gitlab_token = "your gitlab token here"
gitlab_base_url = "your gitlab base url here"

# fastapi
app = FastAPI()


class GitlabEvent(BaseModel):
    object_kind: str
    project: dict
    object_attributes: dict


@app.post("/gitlab_event", response_class=PlainTextResponse)
async def gitlab_event(event: GitlabEvent) -> str:
    """Gitlab webhook."""
    t = time.time()
    status = "failed"

    try:
        message = handle_gitlab_event(event)
        status = "success"
    except Exception:
        logging.warn(
            "Fail to handle gitlab event: %s",
            traceback.format_exc().replace("\n", "\\n"),
        )
        message = "failed"
    finally:
        logging.info(
            "Submit github pull request review: %s:#%d-%s Start: %f Status: %s",
            event.project.get("name"),
            event.object_attributes.get("iid"),
            event.object_attributes.get("title"),
            t,
            time.time() - t,
            status,
        )

    return message


def handle_gitlab_event(event: GitlabEvent) -> str:
    """Trigger merge request review based on gitlab event."""
    if not _validate_event(event):
        raise ValueError("Invalid Event.")

    project_id: int = event.project.get("id", 0)
    merge_request_iid: int = event.object_attributes.get("iid", 0)
    client = Gitlab(url=gitlab_base_url, private_token=gitlab_token)
    retriever = GitlabRetriever(
        client=client,
        project_name_or_id=project_id,
        merge_request_iid=merge_request_iid,
    )
    callback = _comment_callback(retriever._git_merge_request)

    thread = threading.Thread(
        target=asyncio.run, args=(handle_event(retriever, callback=callback),)
    )
    thread.start()
    return "Review Request Submitted."


def _validate_event(event: GitlabEvent) -> bool:
    """Merge request open/reopen event with no draft mark will return True, otherwise False."""
    object_attributes = event.object_attributes

    if event.object_kind != "merge_request":
        return False

    if object_attributes.get("action") not in ("open", "reopen"):
        return False

    if object_attributes.get("state", "") != "opened":
        return False

    if object_attributes.get("work_in_progress", False):
        return False

    return True


def _comment_callback(merge_request: ProjectMergeRequest):
    """Build callback function for merge request comment."""

    def callback(report: str):
        merge_request.notes.create(
            {
                "body": report,
                "project_id": merge_request.project_id,
                "merge_request_iid": merge_request.iid,
            }
        )

    return callback


async def handle_event(retriever: GitlabRetriever, callback: Callable):
    t = time.time()
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
        )
        report = reporter.report()
        callback(report)


def start():
    uvicorn.run("examples.gitlab_server:app", host=host, port=port, workers=worker_num)
    logging.info(f"Codedog v{VERSION}: server start.")


if __name__ == "__main__":
    start()
