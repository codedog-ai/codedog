from codedog.actors.reporters.base import Reporter
from codedog.localization import Localization
from codedog.models import ChangeSummary, PRSummary, PullRequest
from codedog.processors import PullRequestProcessor
from codedog.templates import template_en


class PRSummaryMarkdownReporter(Reporter, Localization):
    pr_processor = PullRequestProcessor()

    def __init__(
        self, pr_summary: PRSummary, code_summaries: list[ChangeSummary], pull_request: PullRequest, language="en"
    ):
        self._pr_summary: PRSummary = pr_summary
        self._code_summaries: dict[str, ChangeSummary] = {summary.full_name: summary for summary in code_summaries}
        self._pull_request: PullRequest = pull_request
        self._markdown: str = ""

        super().__init__(language=language)

    def report(self) -> str:
        if not self._markdown:
            self._markdown = self._generate_markdown()

        return self._markdown

    def _generate_markdown(self) -> str:
        results = self.template.REPORT_PR_SUMMARY.format(
            overview=self._generate_pr_overview(),
            change_overview=self._generate_change_overivew(),
            file_changes=self._generate_file_changes(),
        )
        return results

    def _generate_pr_overview(self) -> str:
        return template_en.REPORT_PR_SUMMARY_OVERVIEW.format(
            type_desc=self.template.REPORT_PR_TYPE_DESC_MAPPING[self._pr_summary.pr_type],
            overview=self._pr_summary.overview,
        )

    def _generate_change_overivew(self) -> str:
        return self.pr_processor.gen_material_change_files(self._pull_request.change_files)

    def _generate_file_changes(self) -> str:
        major_changes_report = []
        changes_report = []

        major_files = set(self._pr_summary.major_files)
        self._pull_request.change_files
        for change_file in self._pull_request.change_files:
            if change_file.full_name not in self._code_summaries:
                continue

            curr_report = self.template.REPORT_CHANGE_OVERVIEW.format(
                name=change_file.name,
                url=change_file.diff_url,
                full_name=change_file.full_name,
                content=self._code_summaries[change_file.full_name].summary,
            )

            major_changes_report.append(curr_report) if change_file.full_name in major_files else changes_report.append(
                curr_report
            )

        report_major = self.template.REPORT_FILE_CHANGES_MAJOR.format(
            major_changes="\n".join(major_changes_report) if major_changes_report else "",
        )
        report = self.template.REPORT_FILE_CHANGES.format(changes="\n".join(changes_report) if changes_report else "")

        return f"{report_major}\n{report}\n"
