from abc import ABC, abstractmethod, abstractstaticmethod
from typing import Callable

from pydantic import BaseModel, Field

import codedog
from codedog.models import ChangeFile, Commit, DiffContent, PullRequest, Repository


def _get_verbosity() -> bool:
    return codedog.verbose


class Retriever(BaseModel, ABC):
    """Base class for git repository pull request retrievers.

    Retrievers are responsible for retrieving pr related commits, branchs, issues and code data from
    Github, Gitlab, Bitbucket etc. It defines the interface codedog uses to retrieve data from
    from repository, wrapped the different client api of platforms.

    The main methods exposed by chains are:
    """

    callbacks: Callable = Field(default=None, exclude=True)
    verbose: bool = Field(default_factory=_get_verbosity)

    @property
    def retriever_type(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def repository(self) -> Repository:
        """Return the pull request target repository object."""

    @property
    @abstractmethod
    def pull_request(self) -> PullRequest:
        """Return the pull request object."""

    @abstractmethod
    def get_pull_request_commits(self) -> list[Commit]:
        """Return the commit list in pr."""

    @abstractmethod
    def get_pull_request_changed_files(self) -> list[ChangeFile]:
        """Return the changed file list between end commit and start commit."""

    @abstractmethod
    def get_diff_content(self, file: ChangeFile) -> DiffContent:
        """Return the diff content of the specified file between end commit and start commit."""
