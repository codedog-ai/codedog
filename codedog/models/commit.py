from pydantic import BaseModel, Field


class Commit(BaseModel):
    commit_id: int = Field()
    """Commit id. Generated by sha1 or sha256 based on platform."""

    url: str = Field(default="")
    """Url to commit."""
    message: str = Field(default="")
    """Commit message."""
