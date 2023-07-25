from pydantic import BaseModel, Field


class ChangeSummary(BaseModel):
    full_name: str = Field()
    """File full name."""

    summary: str = Field()
    """File change summarization."""
