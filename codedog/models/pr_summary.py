from enum import Enum

from pydantic import BaseModel, Field


class PRType(str, Enum):
    """Pull request type: feature, fix, refactor, perf, test, doc, ci, style, chore."""

    feature = "feature"
    fix = "fix"
    refactor = "refactor"
    perf = "perf"
    test = "test"
    doc = "doc"
    ci = "ci"
    style = "style"
    chore = "chore"
    unknown = "unknown"


class PRSummary(BaseModel):
    overview: str = ""
    """Pull request summarization."""

    pr_type: PRType = PRType.unknown
    """Pull request type."""

    major_files: list[str] = Field(default_factory=list)
    """Pull request file with major logical changes. If pr_type is not feature, this will be empty."""
