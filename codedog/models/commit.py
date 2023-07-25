from typing import Any

from pydantic import BaseModel, Field, validator
from pydantic.fields import ModelField


class Commit(BaseModel):
    commit_id: int = Field()
    """Commit id converted from sha."""
    sha: str = Field()
    """Commit sha."""

    url: str = Field(default="")
    """Commit html url."""
    message: str = Field(default="")
    """Commit message."""

    _raw: object = Field(default=None, exclude=True)
    """git commit raw object"""

    @validator("*", pre=True)
    def none_to_default(value: Any, field: ModelField):
        if value is not None:
            return value
        if field.default:
            return field.default
        if field.default_factory:
            return (field.default_factory)()
        raise ValueError(f"Field {field.name} is None.")
