from github import Github
from github.PullRequest import GithubPullRequest
from github.Repository import Repository as GithubRepository

from codedog.retrievers.base import Retriever

DEFAULT_GITHUB_BASE_URL = "https://www.github.com"


class GithubRetriever(Retriever):
    def __init__(
        self,
        client: Github,
        repository_name_or_id: str or int,
        pull_request_id: int,
    ):
        """_summary_

        Args:
            client (Github): _description_
            repository_name_or_id (strorint): _description_
            pull_request_id (int): _description_
            base_url (str, optional): _description_. Defaults to None.
        """
        self._git_repository: GithubRepository = client.get_repo(repository_name_or_id)
        self._git_pull_request: GithubPullRequest = self.repository.get_pull(pull_request_id)

    def repository(self):
