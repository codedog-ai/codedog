from pydantic import BaseModel, Field

from codedog.models.change_file import ChangeFile
from codedog.models.issue import Issue


class PullRequest(BaseModel):
    pr_id: int = Field()
    """Pull Request id."""
    repository_id: int = Field()
    """Repository id this pull request belongs to."""

    title: str = Field(default="")
    """Pull Request title."""
    description: str = Field(default="")
    """Pull Request description."""
    url: str = Field(default="")
    """Pull Request url."""
    related_issue_ids: list[int] = Field(default_factory=list)
    """git PR related issue ids"""
    change_file_full_names: list[str] = Field(default_factory=list)
    """git PR changed file full names"""

    related_issues: list[Issue] = Field(default_factory=list, exclude=True)
    """git PR related issues"""
    change_files: list[ChangeFile] = Field(default_factory=list, exclude=True)
    """git PR changed files"""
