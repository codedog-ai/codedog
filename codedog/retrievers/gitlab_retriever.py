from codedog.retrievers.base import Retriever
from gitlab import Gitlab
from gitlab import Project
from gitlab import ProjectMergeRequest

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
        self._git_pull_request: ProjectMergeRequest = self._git_repository.mergerequests.get(merge_request_number)

        # --- codedog model ---
        self._repository: Repository = self._build_repository(self._git_repository)
        self._source_repository: Repository = self._build_repository(self._git_pull_request.base.repo)
        self._pull_request: PullRequest = self._build_pull_request(self._git_pull_request)

        # Get a project by name with namespace
        # project_name_with_namespace = "namespace/project_name"
        # project = gl.projects.get(project_name_with_namespace)

    @property
    def retriever_type(self) -> str:
        return "Gitlab Retriever"

    @property
    def repository(self) -> Repository:
        """Return the pull request target repository object."""

    @property
    def pull_request(self) -> PullRequest:
        """Return the pull request object."""

    @property
    def source_repository(self) -> Repository:
        """Return the pull request source repository object."""

    @property
    @abstractmethod
    def changed_files(self) -> list[ChangeFile]:
        """Return the changed file list between end commit and start commit."""

    @abstractmethod
    def get_blob(self, blob_sha: str or id) -> Blob:
        """Get blob by id."""

    @abstractmethod
    def get_commit(self, commit_sha: str or id) -> Commit:
        """Get commit by id."""
