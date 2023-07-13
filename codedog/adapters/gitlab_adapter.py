"""
gitlab code review implementation.
"""
import asyncio
import logging
import threading

from gitlab import Gitlab
from gitlab.v4.objects import Project, ProjectMergeRequest
from pydantic import BaseModel

from codedog.annotations import IGNORE_ANNOTATION
from codedog.model import Change, PullRequest
from codedog.review import Review
from codedog.utils import CodedogError, get_sha1

logger = logging.getLogger(__name__)


class GitlabEvent(BaseModel):
    object_kind: str
    project: dict
    object_attributes: dict


def handle_gitlab_event(event: GitlabEvent, url: str, token: str, source: str = "", local: bool = False):
    _event_filter(event)

    project_id: int = event.project.get("id", 0)
    merge_request_id: int = event.object_attributes.get("iid", 0)

    return handle_merge_request(project_id, merge_request_id, url, token, source, local)


def handle_merge_request(project_id: int, merge_request_id: int, url: str, token: str, source: str, local: bool):
    try:
        gl: Gitlab = Gitlab(url=url, private_token=token)
        gl.auth()
    except:  # noqa
        logger.warn("Fail connect to %s", url)
        raise CodedogError(f"Fail connect to {url}", 2)

    project: Project = gl.projects.get(project_id)
    merge_request: ProjectMergeRequest = project.mergerequests.get(merge_request_id)

    pr: PullRequest = PullRequest(
        pr_id=merge_request_id,
        repository_id=project_id,
        repository_name=project._attrs.get("name", str(project_id)),
        repository_group=project._attrs.get("namespace", {}).get("name", ""),
        url=merge_request.attributes.get("web_url", ""),
        title=merge_request.attributes.get("title", ""),
        description=merge_request.attributes.get("description", ""),
    )

    changes = _get_changes(merge_request)

    callbacks = []
    if not local:
        callbacks = [_comment_callback(merge_request)]

    thread = threading.Thread(
        target=asyncio.run, args=(_review_wrapper(pr, changes, callbacks, source=source, url=url),)
    )
    thread.start()

    return "submitted"


def _get_changes(merge_request: ProjectMergeRequest) -> list[Change]:
    changes: list = merge_request.changes().get("changes", [])
    change_list: list[Change] = []
    url_prefix = merge_request.attributes.get("web_url", "")

    # changes is a dictionary that maps a change id to a Change object
    # A change id is the hash of the new path of the change
    for change in changes:
        change = Change(
            pr_id=merge_request.iid,
            repository_id=merge_request.project_id,
            content=change.get("diff", ""),
            file_name=change["new_path"],
            url=f"{url_prefix}/diffs#diff-content-{get_sha1(change['new_path'])}",
        )
        change_list.append(change)

    return change_list


def _comment_callback(merge_request: ProjectMergeRequest):
    async def callback(review: Review):
        report: str = review.report()
        merge_request.notes.create(
            {"body": report, "project_id": merge_request.project_id, "merge_request_iid": merge_request.iid}
        )

    return callback


async def _review_wrapper(pr: PullRequest, changes: list[Change], callbacks: list[callable] = [], **kwargs):
    try:
        url = kwargs.get("url", "gitlab")
        review = Review(pr=pr, changes=changes, callbacks=callbacks, platform=url, **kwargs)
        await review.execute()
    except:  # noqa
        logger.warn("review raise an exception.", extra=pr.json(exclude={"content", "description"}))


def _event_filter(event: GitlabEvent) -> bool:
    """filter gitlab event.

    Args:
        event (GitlabEvent): gitlab event.

    Returns:
        bool: True if the event is filtered.
    """
    object_attributes = event.object_attributes

    if event.object_kind != "merge_request":
        raise CodedogError("Not a merge request event.", 1)

    if object_attributes.get("action") not in ("open", "reopen"):
        raise CodedogError("Not a merge request open/reopen event.", 1)

    if object_attributes.get("state", "") != "opened":
        raise CodedogError("Not a merge request status is not opened.", 1)

    if object_attributes.get("work_in_progress", False):
        raise CodedogError("Merge request is a WIP", 1)

    if object_attributes.get("title", "").rfind(IGNORE_ANNOTATION) != -1:
        raise CodedogError("Merge request title contains ignore annotation.", 1)


def build_merge_request_event(project_id: int, merge_request_iid: int):
    event = {
        "project": {"id": project_id},
        "object_attributes": {
            "iid": merge_request_iid,
            "action": "open",
            "state": "opened",
            "work_in_progress": False,
        },
        "object_kind": "merge_request",
    }

    return GitlabEvent(**event)
