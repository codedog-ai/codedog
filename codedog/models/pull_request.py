from pydantic import BaseModel, Field

from codedog.models.change_file import ChangeFile
from codedog.models.issue import Issue
from codedog.models.repository import Repository


class PullRequest(BaseModel):
    pull_request_id: int = Field()
    """Pull Request id."""
    repository_id: int = Field()
    """Repository id this pull request belongs to."""

    title: str = Field(default="")
    """Pull Request title."""
    description: str = Field(default="")
    """Pull Request description."""
    url: str = Field(default="")
    """Pull Request url."""
    repository_name: str = Field(default="")
    """Repository name this pull request belongs to."""

    related_issues: list[Issue] = Field(default_factory=list, exclude=True)
    """git PR related issues"""
    change_files: list[ChangeFile] = Field(default_factory=list, exclude=True)
    """git PR changed files"""
    repository: Repository = Field(default=None, exclude=True)
    """git PR target repository"""
    source_repository: Repository = Field(default=None, exclude=True)
    """git PR source repository"""
    _raw: object = Field(default=None, exclude=True)
    """git PR raw object"""
