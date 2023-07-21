from pydantic import BaseModel, Field


class Issue(BaseModel):
    issue: int = Field()
    """Issue id."""
    repository_id: int = Field()
    """Repository id this pull request belongs to."""

    repository_full_name: str = Field(default="")
    """Repository full name this issue belongs to."""
    repository_name: str = Field(default="")
    """Repository name this pull request belongs to."""
    title: str = Field(default="")
    """Issue title."""
    description: str = Field(default="")
    """Issue description."""
    url: str = Field(default="")
    """Issue url."""
