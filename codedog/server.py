"""
api server
"""

import logging
import os
import traceback
from logging.config import dictConfig

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from codedog.adapters.github_adapter import GithubEvent, handle_github_event
from codedog.adapters.gitlab_adapter import GitlabEvent, handle_gitlab_event
from codedog.utils import CodedogError, get_logging_config

logger = logging.getLogger(__name__)

app = FastAPI()

host = os.environ.get("CODEDOG_SERVER", "0.0.0.0")
port = int(os.environ.get("CODEDOG_PORT", 32167))
worker_num = os.environ.get("CODEDOG_WORKER_NUM", 1)


class Response(BaseModel):
    message: str
    code: int = 0


@app.post("/v1/webhook/gitlab", response_model=Response)
async def gitlab(event: GitlabEvent, url: str, token: str, source: str = "") -> Response:
    """Gitlab webhook.

    Args:
        event (GitlabEvent): Gitlab event.
        url (str): Gitlab site url.
        token (str): Gitlab access token.
        source (str, optional): review source tag. Defaults to "".

    Returns:
        Response: message.
    """
    assert token

    try:
        message = handle_gitlab_event(event, url, token, source)
    except CodedogError as e:
        return Response(message=e.message, code=e.code)
    except Exception:
        logger.fatal("Internal Service Error:\n%s", traceback.format_exc())
        return Response(message="Internal Service Error", code=-2)
    return Response(message=message, code=0)


@app.post("/v1/webhook/github", response_model=Response)
async def github(
    event: GithubEvent,
) -> Response:
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


def start():
    log_config = get_logging_config(level=logging.INFO)
    dictConfig(log_config)

    uvicorn.run("codedog.server:app", host=host, port=port, workers=worker_num, log_config=log_config)


if __name__ == "__main__":
    start()