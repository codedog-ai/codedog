"""
handle github webhook event. load github MR changes.
"""
import asyncio
import logging
import re
import threading
from functools import lru_cache
from os import environ as env

from github import Github
from github.File import File
from github.Issue import Issue
from github.PaginatedList import PaginatedList
from github.PullRequest import PullRequest as GithubPullRequest
from github.Repository import Repository
from pydantic import BaseModel

from codedog.annotations import IGNORE_ANNOTATION
from codedog.model import Change, PullRequest
from codedog.review import Review
from codedog.utils import CodedogError, get_sha256, get_ttl_hash

logger = logging.getLogger(__name__)

# TODO: connection watchdog

github_token = env.get("GITHUB_TOKEN", "")
gh = Github(github_token)


issue_pattern = re.compile(r"#[0-9]+")


class GithubEvent(BaseModel):
    action: str
    number: int
    pull_request: dict
    repository: dict


def handle_github_event(event: GithubEvent, local=False, **args) -> str:
    # TODO: parse event related exception
    _event_filter(event)

    repository_id: int = event.repository.get("id", 0)
    pull_request_number: int = event.number

    assert repository_id
    assert pull_request_number

    return handle_pull_request(repository_id, pull_request_number, local, get_ttl_hash(120), **args)  # TODO: config


@lru_cache()
def handle_pull_request(repository_id: int, pull_request_number: int, local=False, ttl_hash=None, **args):
    del ttl_hash
    logger.info(
        "Retrive pull request from Github",
        extra={"github.repo.id": repository_id, "github.pull.number": pull_request_number},
    )

    pr = get_pr(repository_id, pull_request_number)

    changes = pr.changes

    callbacks = []
    if not local:
        callbacks = [_comment_callback(gh.get_repo(repository_id).get_pull(pull_request_number))]

    thread = threading.Thread(target=asyncio.run, args=(_review_wrapper(pr, changes, callbacks, **args),))
    thread.start()

    return "Review Submitted."


def get_pr(repository_id, pull_request_number):
    repository: Repository = gh.get_repo(repository_id)
    pull_request: GithubPullRequest = repository.get_pull(pull_request_number)
    issue: Issue = get_potential_issue(repository, pull_request)
    url = pull_request.html_url
    title = pull_request.title
    description = pull_request.body

    pr: PullRequest = PullRequest(
        pr_id=pull_request_number,
        repository_id=repository.id,
        repository_name=repository.name,
        repository_group=repository.owner.login,
        url=url,
        title=title,
        description=description if description else "",
    )

    if issue:
        logger.info(
            "Found related issue in pull request body.",
            extra={
                "github.issue.number": issue.number,
                "github.repo.id": repository_id,
                "github.pull.number": pull_request_number,
            },
        )
        pr.issue_id = issue.number
        pr.issue_title = issue.title
        pr.issue_description = issue.body

    changes = _get_changes(pull_request, repository)

    pr.changes = changes
    return pr


def _get_changes(pull_request: GithubPullRequest, repository: Repository) -> list[Change]:
    files: PaginatedList[File] = pull_request.get_files()
    changes: list[Change] = []

    # changes is a dictionary that maps a change id to a Change object
    # A change id is the hash of the new path of the change object.
    for file in files:
        change = Change(
            pr_id=pull_request.number,
            repository_id=repository.id,
            content=file.patch if file.patch else "",
            file_name=file.filename,
            url=f"{pull_request.html_url}/files#diff-{get_sha256(file.filename)}",
        )
        changes.append(change)

    return changes


def _comment_callback(pull_request: GithubPullRequest):
    async def callback(review: Review):
        report: str = review.report()
        pull_request.create_issue_comment(body=report)

    return callback


def get_potential_issue(repo: Repository, pull: GithubPullRequest) -> Issue:
    body = pull.body

    if not body:
        return

    matches = re.finditer(issue_pattern, body)
    issue = None
    for match in matches:
        issue_number = match.group(0).lstrip("#")  # 去除 # 符号
        try:
            issue = repo.get_issue(int(issue_number))
            if not issue:
                continue
            else:
                break
        except:  # noqa
            continue

    if not issue:
        return None

    return issue


async def _review_wrapper(pr: PullRequest, changes: list[Change], callbacks: list[callable] = [], **args):
    review = Review(pr=pr, changes=changes, callbacks=callbacks, **args)
    await review.execute()


def _event_filter(event: GithubEvent) -> bool:
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

    if pull_request.get("title", "").rfind(IGNORE_ANNOTATION) != -1:
        raise CodedogError("Pull request title contains ignore annotation.", 1)


def build_pull_request_event(repository_name_or_id: int | str, pull_request_number: int):
    repository: Repository = gh.get_repo(repository_name_or_id)
    pull_request: GithubPullRequest = repository.get_pull(pull_request_number)

    event = {
        "number": pull_request_number,
        "action": "opened",
        "repository": {"id": repository.id},
        "pull_request": {
            "html_url": pull_request.html_url,
            "title": pull_request.title,
            "body": pull_request.body,
            "state": "open",
            "draft": False,
        },
    }

    return GithubEvent(**event)
