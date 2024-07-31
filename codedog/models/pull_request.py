from typing import Any

from pydantic import BaseModel, Field

from codedog.models.change_file import ChangeFile
from codedog.models.issue import Issue
from codedog.models.repository import Repository


class PullRequest(BaseModel):
    pull_request_id: int = Field()
    """Pull Request id (Global id. Not number/iid)"""
    repository_id: int = Field()
    """Repository id this pull request belongs to."""
    pull_request_number: int = Field(default=0)

    title: str = Field(default="")
    """Pull Request title."""
    body: str = Field(default="")
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
    raw: object = Field(default=None, exclude=True)
    """git PR raw object"""
