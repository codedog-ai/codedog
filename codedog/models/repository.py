from typing import Any

from pydantic import BaseModel, Field, validator
from pydantic.fields import ModelField


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

    @validator("*", pre=True)
    def none_to_default(value: Any, field: ModelField):
        if value is not None or field.type_ not in [str, int, float, bool, list, dict]:
            return value
        if field.default:
            return field.default
        if field.default_factory:
            return (field.default_factory)()
        raise ValueError(f"Field {field.name} is None.")
