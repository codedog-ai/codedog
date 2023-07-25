from typing import Any

from pydantic import BaseModel, Field, validator
from pydantic.fields import ModelField


class Issue(BaseModel):
    issue_id: int = Field()
    """Issue id."""

    title: str = Field(default="")
    """Issue title."""
    description: str = Field(default="")
    """Issue description."""
    url: str = Field(default="")
    """Issue url."""

    _raw: object = Field(default=None, exclude=True)
    """git issue raw object"""

    @validator("*", pre=True)
    def none_to_default(value: Any, field: ModelField):
        if value is not None or field.type_ not in [str, int]:
            return value
        if field.default:
            return field.default
        if field.default_factory:
            return (field.default_factory)()
        raise ValueError(f"Field {field.name} is None.")
