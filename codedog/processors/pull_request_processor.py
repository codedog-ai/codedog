from __future__ import annotations

import itertools
from functools import lru_cache
from typing import Callable, Dict, List

from codedog.localization import Localization
from codedog.models import ChangeFile, ChangeStatus, ChangeSummary, PullRequest

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


class PullRequestProcessor(Localization):
    def __init__(self):
        self._status_template_functions = None

        super().__init__()

    def is_code_file(self, change_file: ChangeFile):
        return change_file.suffix in SUPPORT_CODE_FILE_SUFFIX

    def get_diff_code_files(self, pr: PullRequest) -> list[ChangeFile]:
        diff_code_files = []
        for change_file in pr.change_files:
            if change_file.status in CONTENT_CHANGE_STATUS and self.is_code_file(change_file):
                diff_code_files.append(change_file)

        return diff_code_files

    def gen_material_change_files(self, change_files: list[ChangeFile]) -> str:
        files_by_status = itertools.groupby(sorted(change_files, key=lambda x: x.status), lambda x: x.status)
        summary_by_status = []

        for status, files in files_by_status:
            summary_by_status.append(
                f"{self.template.MATERIAL_STATUS_HEADER_MAPPING.get(status, ChangeStatus.unknown)}\n"
                + "\n".join(
                    self.status_template_functions.get(status, self._build_status_template_default)(file)
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

    @property
    def status_template_functions(self) -> dict[ChangeStatus, Callable]:
        if not self._status_template_functions:
            self._status_template_functions = {
                ChangeStatus.copy: self._build_status_template_copy,
                ChangeStatus.renaming: self._build_status_template_rename,
            }
        return self._status_template_functions

    @classmethod
    @lru_cache(maxsize=1)
    def build(cls) -> PullRequestProcessor:
        return cls()
