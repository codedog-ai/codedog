from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from codedog.models.diff import DiffContent


class ChangeStatus(str, Enum):
    """Git file change mode. https://git-scm.com/docs/diff-format"""

    addition = "A"
    """Addition of a file"""
    copy = "C"
    """Copy of a file into a new one"""
    deletion = "D"
    """Deletion of a file"""
    modified = "M"
    """Modification of the contents or mode of a file"""
    renaming = "R"
    """Renaming of a file"""
    type_change = "T"
    """Change in the type of the file (regular file, symbolic link or submodule)"""
    unmerged = "U"
    """File is unmerged (you must complete the merge before it can be committed)"""
    unknown = "X"
    """Unknown change type (most probably a bug, please report it)"""


class ChangeFile(BaseModel):
    """A changed file between two commit."""

    blob_id: str = Field()
    """Blob id. Converted from sha."""
    sha: str = Field()
    """Blob sha."""
    full_name: str = Field()
    """File name and path."""
    status: ChangeStatus = Field()
    """Change status. see more information in ChangeStatus."""
    pull_request_id: int = Field()
    """Id of pull request this change belongs to."""
    repository_id: int = Field()
    """Id of pull request target repository this change file belongs to."""
    source_repository_id: int = Field()
    """Id of pull request source repository this change file belongs to."""
    start_commit_id: str = Field()
    """Start commit id"""
    end_commit_id: str = Field()
    """End commit id"""

    name: str = Field(default="")
    """File name without path."""
    diff_url: str = Field(default="")
    """Url of this change file in pull request."""
    blob_url: str = Field(default="")
    """Url of this change file blob in end commit. If change file type is deleted, this will be none."""
    diff_content: DiffContent = Field(default="", exclude=True)
    """The diff content of this file."""

    _raw: Optional[object] = Field(default=None, exclude=True)
    """Raw object generated by client api of this change file."""
