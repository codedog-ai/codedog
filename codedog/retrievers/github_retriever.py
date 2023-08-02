from __future__ import annotations

import itertools
import re

from github import Github
from github.Commit import Commit as GithubCommit
from github.File import File as GithubFile
from github.GitBlob import GitBlob as GithubBlob
from github.Issue import Issue as GithubIssue
from github.PullRequest import PullRequest as GHPullRequest
from github.Repository import Repository as GHRepo
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


class GithubRetriever(Retriever):
    """Github retriever."""

    GITHUB_STATUS_MAPPING = {
        "added": "A",
        "copied": "C",
        "removed": "D",
        "modified": "M",
        "renamed": "R",
        "type_change": "T",
    }

    ISSUE_PATTERN = r"#\d+"

    def __init__(
        self,
        client: Github,
        repository_name_or_id: str | int,
        pull_request_number: int,
    ):
        """Connect to github remote server and retrieve pull request data.

        Args:
            client (github.Github): github client from pyGithub
            repository_name_or_id (str | int): repository name or id
            pull_request_number (int): pull request number (not global id)
        """

        # --- github model ---
        self._git_repository: GHRepo = client.get_repo(repository_name_or_id)
        self._git_pull_request: GHPullRequest = self._git_repository.get_pull(pull_request_number)

        # --- codedog model ---
        self._repository: Repository = self._build_repository(self._git_repository)
        self._source_repository: Repository = self._build_repository(self._git_pull_request.base.repo)
        self._pull_request: PullRequest = self._build_pull_request(self._git_pull_request)

    @property
    def retriever_type(self) -> str:
        return "Github Retriever"

    @property
    def repository(self) -> GHRepo:
        return self._repository

    @property
    def pull_request(self) -> PullRequest:
        return self._pull_request

    @property
    def source_repository(self) -> GHRepo:
        return self._source_repository

    @property
    def changed_files(self) -> list[ChangeFile]:
        return self._pull_request.change_files

    def get_blob(self, blob_id: str) -> Blob:
        git_blob = self._git_repository.get_git_blob(blob_id)
        return self._build_blob(git_blob)

    def get_commit(self, commit_sha: str) -> Commit:
        git_commit = self._git_repository.get_commit(commit_sha)
        return self._build_commit(git_commit)

    def _build_repository(self, git_repo: GHRepo) -> Repository:
        return Repository(
            repository_id=git_repo.id,
            repository_name=git_repo.name,
            repository_full_name=git_repo.full_name,
            repository_url=git_repo.html_url,
            _raw=git_repo,
        )

    def _build_pull_request(self, git_pr: GHPullRequest) -> PullRequest:
        related_issues = self._parse_and_build_related_issues(git_pr)
        change_files = self._build_change_file_list(git_pr)

        return PullRequest(
            pull_request_id=git_pr.id,
            repository_id=git_pr.head.repo.id,
            pull_request_number=git_pr.number,
            title=git_pr.title,
            description=git_pr.body if git_pr is not None else "",
            url=git_pr.html_url,
            repository_name=git_pr.head.repo.full_name,
            related_issues=related_issues,
            change_files=change_files,
            repository=self.repository,
            source_repository=self.source_repository,
            _raw=git_pr,
        )

    def _parse_and_build_related_issues(self, git_pr: GHPullRequest) -> list[Issue]:
        title = git_pr.title
        body = git_pr.body

        issue_numbers = self._parse_issue_numbers(title, body)
        return [self._get_and_build_issue(issue_number) for issue_number in issue_numbers]

    def _parse_issue_numbers(self, title, body) -> list[int]:
        body_matches = re.finditer(GithubRetriever.ISSUE_PATTERN, body) if body else []
        title_matches = re.finditer(GithubRetriever.ISSUE_PATTERN, title) if title else []
        issue_numbers = [int(match.group(0).lstrip("#")) for match in itertools.chain(body_matches, title_matches)]
        return issue_numbers

    def _get_and_build_issue(self, issue_number):
        git_issue = self._git_repository.get_issue(issue_number)
        return self._build_issue(git_issue)

    def _build_issue(self, git_issue: GithubIssue) -> Issue:
        return Issue(
            issue_id=git_issue.number,
            title=git_issue.title,
            description=git_issue.body,
            url=git_issue.html_url,
            _raw=git_issue,
        )

    def _build_change_file_list(self, git_pr: GHPullRequest) -> list[ChangeFile]:
        change_files = []
        for file in git_pr.get_files():
            change_file = self._build_change_file(file, git_pr)
            change_files.append(change_file)
        return change_files

    def _build_change_file(self, git_file: GithubFile, git_pr: GHPullRequest) -> ChangeFile:
        full_name = git_file.filename
        name = full_name.split("/")[-1]
        suffix = name.split(".")[-1]
        source_full_name = git_file.previous_filename if git_file.previous_filename else full_name

        return ChangeFile(
            blob_id=int(git_file.sha, 16),
            sha=git_file.sha,
            full_name=full_name,
            source_full_name=source_full_name,
            name=name,
            suffix=suffix,
            status=self._convert_status(git_file.status),
            pull_request_id=git_pr.id,
            start_commit_id=int(git_pr.base.sha, 16),
            end_commit_id=int(git_pr.head.sha, 16),
            diff_url=self._build_change_file_diff_url(git_file, git_pr),
            blob_url=git_file.blob_url,
            diff_content=self._parse_and_build_diff_content(git_file),
            _raw=git_file,
        )

    def _convert_status(self, git_status: str) -> ChangeFile:
        return GithubRetriever.GITHUB_STATUS_MAPPING.get(git_status, ChangeStatus.unknown)

    def _build_change_file_diff_url(self, git_file: GithubFile, git_pr: GHPullRequest) -> str:
        return f"{git_pr.html_url}/files#diff-{git_file.sha}"

    def _parse_and_build_diff_content(self, git_file: GithubFile) -> DiffContent:
        patched_file: PatchedFile = self._build_patched_file(git_file)
        patched_segs: list[DiffSegment] = self._build_patched_file_segs(patched_file)

        # TODO: retrive long content from blob.
        return DiffContent(
            add_count=patched_file.added,
            remove_count=patched_file.removed,
            content=git_file.patch if git_file.patch else "",
            diff_segments=patched_segs,
            _raw=git_file,
            _patched_file=patched_file,
        )

    def _build_patched_file(self, git_file: GithubFile) -> PatchedFile:
        prev_name = git_file.previous_filename if git_file.previous_filename else git_file.filename
        return parse_patch_file(git_file.patch, prev_name, git_file.filename)

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

    def _build_blob(self, git_blob: GithubBlob) -> Blob:
        return Blob(
            blob_id=int(git_blob.sha, 16),
            sha=git_blob.sha,
            content=git_blob.content,
            encoding=git_blob.encoding,
            size=git_blob.size,
            url=git_blob.url,
        )

    def _build_commit(self, git_commit: GithubCommit) -> Commit:
        return Commit(
            commit_id=int(git_commit.sha, 16),
            sha=git_commit.sha,
            url=git_commit.url,
            message=git_commit.commit.message,
        )
