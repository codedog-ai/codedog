from codedog.retrievers.base import Retriever
from gitlab import Gitlab
from gitlab.v4.objects import Project
from gitlab.v4.objects import ProjectMergeRequest
from gitlab.v4.objects import ProjectCommit
from typing import Dict, Any
import base64

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
# TODO: implement Gitlab Retriever


class GitlabRetriever(Retriever):

    def __init__(
        self,
        client: Gitlab,
        repository_name_or_id: str | int,
        merge_request_number: int
    ) -> None:
        """
        Connect to gitlab remote server and retrieve merge request data.

        Args:
            client (gitlab.Gitlab): gitlab client from python-gitlab
            repository_name_or_id (str | int): repository name or id
            merge_request_number (int): merge request number (not global id)
        """

        # --- gitlab model ---
        self._git_repository: Project = client.projects.get(repository_name_or_id)
        self._git_merge_request: ProjectMergeRequest = self._git_repository.mergerequests.get(merge_request_number)

        # --- codedog model ---
        self._repository: Repository = self._build_repository(self._git_repository)

        # self._source_repository: Repository = self._build_repository(self._git_merge_request.base.repo)

        self._merge_request: PullRequest = self._build_merge_request(self._git_merge_request)

    @property
    def retriever_type(self) -> str:
        return "Gitlab Retriever"

    @property
    def repository(self) -> Repository:
        return self._repository

    @property
    def pull_request(self) -> PullRequest:
        return self._git_merge_request

    @property
    def source_repository(self) -> Repository:
        """Return the pull request source repository object."""

    @property
    def changed_files(self) -> list[ChangeFile]:
        return self._merge_request.change_files

    @property
    def get_blob(self, blob_sha: str or id) -> Blob:
        git_blob = self._git_repository.repository_blob_raw(blob_sha)
        return self._build_blob(git_blob)

    @property
    def get_commit(self, commit_sha: str or id) -> Commit:
        git_commit = self._git_repository.commits.get(commit_sha)
        return self._buid_commit(git_commit)

    def _build_repository(self, git_repo: Project) -> Repository:
        return print(Repository(
            repository_id=git_repo.id,
            repository_name=git_repo.name,
            repository_full_name=git_repo.path_with_namespace,
            repository_url=git_repo.web_url,
            _raw=git_repo,
        ))

    def _build_blob(self, git_blob: Dict[str, Any]) -> Blob:
        print(git_blob)
        return Blob(
            blob_id=int(git_blob['sha'], 16),
            sha=git_blob['sha'],
            content=base64.b64decode(git_blob['content']),
            encoding=git_blob['encoding'],
            size=git_blob['size'],
            url=git_blob['url'],
        )

    def _build_commit(self, git_commit: ProjectCommit) -> Commit:
        return Commit(
            commit_id=int(git_commit.short_id, 16),
            sha=git_commit.short_id,
            url=git_commit.web_url,
            message=git_commit.message,
        )

    def _build_pull_request(self, git_pr: ProjectMergeRequest) -> PullRequest:
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
