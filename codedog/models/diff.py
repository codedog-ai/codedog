from typing import Optional

from pydantic import BaseModel, Field
from unidiff import PatchedFile


class DiffSegment(BaseModel):
    add_count: int = Field()
    """Added lines count of this segment."""
    remove_count: int = Field()
    """Removed lines count of this segment."""
    content: str = Field()
    """Diff content of this segment."""
    source_start_line_number: int = Field()
    """Start line number of this segment in source file."""
    source_length: int = Field()
    """Length of this segment in source file."""
    target_start_line_number: int = Field()
    """Start line number of this segment in target file."""
    target_length: int = Field()
    """Length of this segment in target file."""


class DiffContent(BaseModel):
    add_count: int = Field()
    """Added lines count."""
    remove_count: int = Field()
    """Removed lines count."""
    content: str = Field()
    """Diff content."""
    diff_segments: list[DiffSegment] = Field(default_factory=list, exclude=True)
    """Diff segments."""
    patched_file: Optional[PatchedFile] = Field(default=None, exclude=True)
    """Unidiff patched file object."""
