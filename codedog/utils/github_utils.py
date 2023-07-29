import os

from github import Github


def load_github_client():
    github_token = os.environ.get("GITHUB_TOKEN", "")
    client = Github(github_token)
    return client
