from github import Github


def load_github_client(*, token: str, **kwargs):
    client = Github(token, **kwargs)
    return client
