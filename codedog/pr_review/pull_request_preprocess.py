import itertools

from codedog.models import ChangeFile, ChangeStatus

CONTENT_CHANGE_STATUS = [ChangeStatus.addition, ChangeStatus.modified]

SUPPORT_CODE_FILE_SUFFIX = set(["py", "java", "go", "js", "ts", "php", "c", "cpp", "h", "cs", "rs"])

STATUS_HEADER_MAPPING = {
    ChangeStatus.addition: "Added files:",
    ChangeStatus.copy: "Copied files:",
    ChangeStatus.deletion: "Deleted files:",
    ChangeStatus.modified: "Modified files:",
    ChangeStatus.renaming: "Renamed files:",
    ChangeStatus.type_change: "Type changed files:",
    ChangeStatus.unknown: "Other files:",
}


class PullRequestPreProcess:
    def __init__(self):
        self._status_template_functions = {
            ChangeStatus.copy: self._build_status_template_copy,
            ChangeStatus.renaming: self._build_status_template_rename,
        }

    def is_code_file(self, change_file: ChangeFile):
        return change_file.name[-10:].split(".")[-1] in SUPPORT_CODE_FILE_SUFFIX

    def get_diff_code_files(self, change_files: list[ChangeFile]) -> list[ChangeFile]:
        diff_code_files = []
        for change_file in change_files:
            if change_file.status in CONTENT_CHANGE_STATUS and self.is_code_file(change_file):
                diff_code_files.append(change_file)

        return diff_code_files

    def generate_change_filename_template(self, change_files: list[ChangeFile]) -> str:
        files_by_status = itertools.groupby(change_files, lambda change_file: change_file.status)
        summary_by_status = []

        for status, files in files_by_status:
            summary_by_status.append(
                f"{STATUS_HEADER_MAPPING.get(status, ChangeStatus.unknown)}\n"
                + "\n".join(
                    self._status_template_functions.get(status, self._build_status_template_default)(file)
                    for file in files
                )
                + "\n"
            )

        return "\n".join(summary_by_status)

    def _build_status_template_default(self, change_file: ChangeFile):
        return f"- {change_file.full_name}"

    def _build_status_template_copy(self, change_file: ChangeFile):
        return f"- {change_file.full_name} (copied from {change_file.source_full_name})"

    def _build_status_template_rename(self, change_file: ChangeFile):
        return f"- {change_file.full_name} (renamed from {change_file.source_full_name})"


if __name__ == "__main__":
    import os

    from github import Github

    from codedog.retrievers import GithubRetriever

    client = Github(os.environ.get("GITHUB_TOKEN"))
    retriever = GithubRetriever(client, "codedog-ai/codedog", 2)
    pull_request = retriever.pull_request

    pr_preprocess = PullRequestPreProcess()
    print(pr_preprocess.generate_change_filename_template(pull_request.change_files))

    code_files = pr_preprocess.get_diff_code_files(pull_request.change_files)
    for code_file in code_files:
        print(code_file.full_name)
