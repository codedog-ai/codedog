from typing import Any

from pydantic import BaseModel, Field


class Issue(BaseModel):
    issue_id: int = Field()
    """Issue id."""

    title: str = Field(default="")
    """Issue title."""
    description: str = Field(default="")
    """Issue description."""
    url: str = Field(default="")
    """Issue url."""

    raw: object = Field(default=None, exclude=True)
    """git issue raw object"""
