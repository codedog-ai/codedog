import base64
import itertools
import re
from typing import Any, Dict

from gitlab import Gitlab
from gitlab.v4.objects import Project, ProjectCommit, ProjectIssue, ProjectMergeRequest
from unidiff import Hunk, PatchedFile

from codedog.models import (
    Blob,
    ChangeFile,
    ChangeStatus,
    Commit,
    DiffContent,
    Issue,
    PullRequest,
    Repository,
)
from codedog.models.diff import DiffSegment
from codedog.retrievers.base import Retriever
from codedog.utils.diff_utils import parse_patch_file


class GitlabRetriever(Retriever):
    ISSUE_PATTERN = r"#\d+"
    # NOTE Currently, all DIFFs are obtained through one call. Here, the maximum number of file DIFFs is set to 200
    LIST_DIFF_LIMIT = 200

    def __init__(self, client: Gitlab, project_name_or_id: str | int, merge_request_iid: int) -> None:
        """
        Connect to gitlab remote server and retrieve merge request data.

        Args:
            client (gitlab.Gitlab): gitlab client from python-gitlab
            project_name_or_id (str | int): project name (with full namespace) or id
            merge_request_iid (int): merge request iid (not global id)
        """

        # --- gitlab model ---
        self._git_repository: Project = client.projects.get(project_name_or_id)
        self._git_merge_request: ProjectMergeRequest = self._git_repository.mergerequests.get(merge_request_iid)

        source_project: Project = client.projects.get(self._git_merge_request.source_project_id)

        # --- codedog model ---
        self._repository: Repository = self._build_repository(self._git_repository)
        self._source_repository: Repository = self._build_repository(source_project)

        self._merge_request: PullRequest = self._build_merge_request(self._git_merge_request)

    @property
    def retriever_type(self) -> str:
        return "Gitlab Retriever"

    @property
    def repository(self) -> Repository:
        return self._repository

    @property
    def pull_request(self) -> PullRequest:
        return self._merge_request

    @property
    def source_repository(self) -> Repository:
        return self._source_repository

    @property
    def changed_files(self) -> list[ChangeFile]:
        return self._merge_request.change_files

    @property
    def get_blob(self, blob_sha: str or id) -> Blob:
        git_blob = self._git_repository.repository_blob(blob_sha)
        return self._build_blob(git_blob)

    @property
    def get_commit(self, commit_sha: str or id) -> Commit:
        git_commit = self._git_repository.commits.get(commit_sha)
        return self._buid_commit(git_commit)

    def _build_repository(self, git_repo: Project) -> Repository:
        return Repository(
            repository_id=git_repo.id,
            repository_name=git_repo.name,
            repository_full_name=git_repo.path_with_namespace,
            repository_url=git_repo.web_url,
            _raw=git_repo,
        )

    def _build_blob(self, git_blob: Dict[str, Any]) -> Blob:
        return Blob(
            blob_id=int(git_blob["sha"], 16),
            sha=git_blob["sha"],
            content=base64.b64decode(git_blob["content"]),
            encoding=git_blob["encoding"],
            size=git_blob["size"],
            url=git_blob.get("url", ""),  # TODO fix url
        )

    def _build_commit(self, git_commit: ProjectCommit) -> Commit:
        return Commit(
            commit_id=int(git_commit.short_id, 16),
            sha=git_commit.short_id,
            url=git_commit.web_url,
            message=git_commit.message,
        )

    def _build_merge_request(self, git_pr: ProjectMergeRequest) -> PullRequest:
        related_issues = self._parse_and_build_related_issues(git_pr)
        change_files = self._build_change_file_list(git_pr)
        description = git_pr.description if git_pr is not None else ""
        pull_request = PullRequest(
            pull_request_id=git_pr.id,
            repository_id=git_pr.target_project_id,
            pull_request_number=git_pr.get_id(),
            title=git_pr.title,
            body=description,
            url=git_pr.web_url,
            repository_name=self._repository.repository_full_name,
            related_issues=related_issues,
            change_files=change_files,
            repository=self.repository,
            source_repository=self.source_repository,
            _raw=git_pr,
        )
        return pull_request

    def _parse_and_build_related_issues(self, git_mr: ProjectMergeRequest) -> list[Issue]:
        title = git_mr.title
        body = git_mr.description
        issue_numbers = self._parse_issue_numbers(title, body)
        return [self._get_and_build_issue(issue_number) for issue_number in issue_numbers]

    def _parse_issue_numbers(self, title, body) -> list[int]:
        # match pattern like https://gitlab.com/gitlab-org/gitlab/-/issues/405433
        body_matches = re.finditer(GitlabRetriever.ISSUE_PATTERN, body) if body else []
        title_matches = re.finditer(GitlabRetriever.ISSUE_PATTERN, title) if title else []
        issue_numbers = [int(match.group(0).lstrip("#")) for match in itertools.chain(body_matches, title_matches)]
        return issue_numbers

    def _build_change_file_list(self, git_mr: ProjectMergeRequest) -> list[ChangeFile]:
        change_files = []

        # list all diffs
        diffs_list = git_mr.diffs.list(per_page=self.LIST_DIFF_LIMIT)

        for diff_response in diffs_list:
            full_diff = git_mr.diffs.get(diff_response.id)
            for diff in full_diff.attributes.get("diffs", []):
                change_file = self._build_change_file(diff, git_mr)
                change_files.append(change_file)
        return change_files

    def _build_change_file(self, diff: dict, git_mr: ProjectMergeRequest) -> ChangeFile:
        full_name = diff["new_path"]
        name = full_name.split("/")[-1]
        suffix = name.split(".")[-1]
        source_full_name = diff.get("old_path", full_name)
        start_sha = git_mr.diff_refs["start_sha"]
        end_sha = git_mr.diff_refs["head_sha"]
        mr_id = git_mr.get_id()
        blob_url = f"{self._repository.repository_url}/-/blob/{end_sha}/{full_name}"
        change_file = ChangeFile(
            blob_id=int(end_sha, 16),
            sha=end_sha,
            full_name=full_name,
            source_full_name=source_full_name,
            name=name,
            suffix=suffix,
            status=self._convert_status(diff),
            pull_request_id=mr_id,
            start_commit_id=int(start_sha, 16),
            end_commit_id=int(end_sha, 16),
            diff_url=blob_url,  # TODO
            blob_url=blob_url,
            diff_content=self._parse_and_build_diff_content(diff),
            _raw=diff,
        )
        return change_file

    def _convert_status(self, git_pr: dict) -> ChangeFile:
        if git_pr.get("new_file", False):
            return ChangeStatus.addition
        if git_pr.get("deleted_file", False):
            return ChangeStatus.deletion
        if git_pr.get("renamed_file", False):
            return ChangeStatus.renaming
        return ChangeStatus.modified

    # TODO implement
    def _build_change_file_diff_url(self) -> str:
        return ""

    def _parse_and_build_diff_content(self, diff: dict) -> DiffContent:
        patch = diff.get("diff", "")
        old_path = diff.get("old_path", "")
        new_path = diff.get("new_path", "")

        patched_file: PatchedFile = self._build_patched_file(old_path, new_path, patch)
        patched_segs: list[DiffSegment] = self._build_patched_file_segs(patched_file)

        return DiffContent(
            add_count=patched_file.added,
            remove_count=patched_file.removed,
            content=patch,
            diff_segments=patched_segs,
            _raw=diff,
            _patched_file=patched_file,
        )

    def _build_patched_file(self, old_path, new_path, patch) -> PatchedFile:
        return parse_patch_file(patch, old_path, new_path)

    def _build_patched_file_segs(self, patched_file: PatchedFile) -> list[DiffSegment]:
        patched_segs = []
        for patched_hunk in patched_file:
            patched_segs.append(self._build_patch_segment(patched_hunk))
        return patched_segs

    def _build_patch_segment(self, patched_hunk: Hunk) -> DiffSegment:
        return DiffSegment(
            add_count=patched_hunk.added,
            remove_count=patched_hunk.removed,
            content=str(patched_hunk),
            source_start_line_number=patched_hunk.source_start,
            source_length=patched_hunk.source_length,
            target_start_line_number=patched_hunk.target_start,
            target_length=patched_hunk.target_length,
            _raw=patched_hunk,
        )

    def _get_and_build_issue(self, issue_number):
        git_issue = self._git_repository.issues.get(issue_number)
        return self._build_issue(git_issue)

    def _build_issue(self, git_issue: ProjectIssue) -> Issue:
        return Issue(
            issue_id=git_issue.get_id(),
            title=git_issue.title,
            description=git_issue.description,
            url=git_issue.web_url,
            _raw=git_issue,
        )
