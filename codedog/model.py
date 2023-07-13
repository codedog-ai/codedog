from pydantic import BaseModel, Field

from codedog.templates import grimoire_cn

GRIMOIRE = grimoire_cn


class Change(BaseModel):
    pr_id: int = Field(description="git PR id")
    repository_id: int = Field(description="git remote repository id")
    content: str = Field(description="diff content")
    file_name: str = Field(description="the new path of file")
    url: str = Field(description="file url")
    summary: str | None = Field(description="文件diff的概括")
    major: bool | None = Field(description="文件diff是否为housekeeping")
    feedback: str | None = Field(description="文件修改意见")


class PullRequest(BaseModel):
    # TODO: compress pr body and issue body if longer than 4096
    pr_id: int = Field(description="git PR id")
    repository_id: int = Field(description="git remote repository id")
    repository_name: str = Field(description="repository name")
    repository_group: str = Field(description="repository group")
    url: str = Field(description="git PR visit url")
    title: str = Field(description="git PR title")
    description: str = Field(description="git PR description")
    issue_id: int | None = Field(description="git PR related issue id")
    issue_title: str | None = Field(description="git PR related issue title")
    issue_description: str | None = Field(description="git PR related issue description")
    changes: list[Change] | None = Field(description="change list in this pr.")


class ChangeSummary(BaseModel):
    summary: str = Field(description=GRIMOIRE.PR_CHANGE_REVIEW_SUMMARY)
    main_change_flag: bool | None = Field(description=GRIMOIRE.PR_CHANGE_REVIEW_MAIN_CHANGE, default=False)
