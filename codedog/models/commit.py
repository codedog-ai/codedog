from typing import Any

from pydantic import BaseModel, Field


class Commit(BaseModel):
    commit_id: int = Field()
    """Commit id converted from sha."""
    sha: str = Field()
    """Commit sha."""

    url: str = Field(default="")
    """Commit html url."""
    message: str = Field(default="")
    """Commit message."""

    raw: object = Field(default=None, exclude=True)
    """git commit raw object"""
    """git commit raw object"""
