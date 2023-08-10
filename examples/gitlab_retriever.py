from gitlab import Gitlab
from gitlab.v4.objects import Project
from gitlab.v4.objects import ProjectMergeRequest
from typing import Dict, Any
import json

from codedog.models import (
    Blob,
    ChangeFile,
    ChangeStatus,
    Commit,
    DiffContent,
    Issue,
    PullRequest,
    Repository,
)

gitlab = Gitlab("", private_token="")

# print(gitlab.projects.list())

git_repo = gitlab.projects.get("")
# print(git_repo)
print(Repository(
    repository_id=git_repo.id,
    repository_name=git_repo.name,
    repository_full_name=git_repo.path_with_namespace,
    repository_url=git_repo.web_url,
    _raw=git_repo,
))
print("-------")
# print(json.dumps(str(project), indent=2))

# blob = project.repository_blob("02eb735f3042ff1e0be91aaf8260b35ed9e29160")
# print(blob)


items = git_repo.repository_tree(
    path='', ref='develop')

blob = git_repo.repository_blob("dde6ce90f82ff915a0f04f1b45daec7e51e017f8")
print(blob)
print(items)
git_commit = git_repo.commits.get("dde6ce90f82ff915a0f04f1b45daec7e51e017f8")
print(git_commit)

print(Commit(
    commit_id=int(git_commit.short_id, 16),
    sha=git_commit.short_id,
    url=git_commit.web_url,
    message=git_commit.message,
))
