from pydantic import BaseModel, Field


class Blob(BaseModel):
    """Git blob object."""

    blob_id: int = Field()
    """Blob id. Converted from sha."""
    sha: str = Field()
    """Blob sha."""
    content: str = Field()
    """Blob content."""
    encoding: str = Field()
    """Blob content encoding."""
    size: int = Field()
    """Blob content size."""
    url: str = Field()
    """Blob url."""
