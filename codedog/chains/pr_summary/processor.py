import itertools
from typing import Dict, List

from codedog.models import ChangeFile, ChangeStatus, ChangeSummary, PullRequest
from codedog.templates import template_cn, template_en

CONTENT_CHANGE_STATUS = [ChangeStatus.addition, ChangeStatus.modified]

SUPPORT_CODE_FILE_SUFFIX = set(["py", "java", "go", "js", "ts", "php", "c", "cpp", "h", "cs", "rs"])

SUFFIX_LANGUAGE_MAPPING = {
    "py": "python",
    "java": "java",
    "go": "go",
    "js": "javascript",
    "ts": "typescript",
    "php": "php",
    "c": "c",
    "cpp": "cpp",
    "h": "c",
    "cs": "csharp",
    "rs": "rust",
}

STATUS_HEADER_MAPPING = {
    ChangeStatus.addition: "Added files:",
    ChangeStatus.copy: "Copied files:",
    ChangeStatus.deletion: "Deleted files:",
    ChangeStatus.modified: "Modified files:",
    ChangeStatus.renaming: "Renamed files:",
    ChangeStatus.type_change: "Type changed files:",
    ChangeStatus.unknown: "Other files:",
}


class PRSummaryProcessor:
    # TODO: localization
    def __init__(self, language: str = "en"):
        self._status_template_functions = {
            ChangeStatus.copy: self._build_status_template_copy,
            ChangeStatus.renaming: self._build_status_template_rename,
        }

        self.language = language
        self.template = template_en if language == "en" else template_cn

    def is_code_file(self, change_file: ChangeFile):
        return change_file.suffix in SUPPORT_CODE_FILE_SUFFIX

    def get_diff_code_files(self, pr: PullRequest) -> list[ChangeFile]:
        diff_code_files = []
        for change_file in pr.change_files:
            if change_file.status in CONTENT_CHANGE_STATUS and self.is_code_file(change_file):
                diff_code_files.append(change_file)

        return diff_code_files

    def gen_material_change_files(self, change_files: list[ChangeFile]) -> str:
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

    def gen_material_code_summaries(self, code_summaries: list[ChangeSummary]) -> str:
        return (
            "\n\n".join(
                self.template.MATERIAL_CODE_SUMMARY.format(summary=code_summary.summary, name=code_summary.full_name)
                for code_summary in code_summaries
            )
            + "\n"
        )

    def gen_material_pr_metadata(self, pr: PullRequest) -> str:
        return self.template.MATERIAL_PR_METADATA.format(
            pr_title=pr.title,
            pr_body=pr.body,
            issues="\n".join(f"- {issue.title}" for issue in pr.related_issues),
        )

    def build_change_summaries(
        self, summaries_input: List[Dict[str, str]], summaries_output: List[Dict[str, str]]
    ) -> List[ChangeSummary]:
        result = []
        for i, o in itertools.zip_longest(summaries_input, summaries_output):
            result.append(ChangeSummary(full_name=i["name"], summary=o["text"]))

        return result

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

    pr_preprocess = PRSummaryProcessor()
    print(pr_preprocess.gen_material_change_files(pull_request.change_files))

    code_files = pr_preprocess.get_diff_code_files(pull_request.change_files)
    for code_file in code_files:
        print(code_file.full_name)
