from pydantic import BaseModel, Field


class Repository(BaseModel):
    repository_id: int = Field()
    """Repository id."""

    repository_name: str = Field(default="")
    """Repository name this pull request belongs to."""
    repository_full_name: str = Field(default="")
    """Repository full name this pull request belongs to."""
