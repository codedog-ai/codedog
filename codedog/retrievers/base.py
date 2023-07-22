from abc import ABC, abstractmethod

from codedog.models import Blob, ChangeFile, Commit, PullRequest, Repository


class Retriever(ABC):
    """Base class for git repository pull request retrievers.

    Retrievers are responsible for retrieving pr related commits, branchs, issues and code data from
    Github, Gitlab, Bitbucket etc. It defines the interface codedog uses to retrieve data from
    from repository, wrapped the different client api of platforms.
    """

    @property
    @abstractmethod
    def retriever_type(self) -> str:
        """Return the retriever type."""

    @property
    @abstractmethod
    def pull_request(self) -> PullRequest:
        """Return the pull request object."""

    @property
    @abstractmethod
    def repository(self) -> Repository:
        """Return the pull request target repository object."""

    @property
    @abstractmethod
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
