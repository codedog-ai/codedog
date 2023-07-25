from pydantic import BaseModel, Field


class Repository(BaseModel):
    repository_id: int = Field()
    """Repository id."""

    repository_name: str = Field(default="")
    """Repository name this pull request belongs to."""
    repository_full_name: str = Field(default="")
    """Repository full name this pull request belongs to."""
    repository_url: str = Field(default="")
    """Repository url this pull request belongs to."""

    _raw: object = Field(default=None, exclude=True)
    """git repository raw object"""
