import datetime
from typing import Any, Dict, List

from codedog.actors.reporters.base import Reporter
from codedog.actors.reporters.code_review import CodeReviewMarkdownReporter
from codedog.actors.reporters.pr_summary import PRSummaryMarkdownReporter
from codedog.localization import Localization
from codedog.models import ChangeSummary, CodeReview, PRSummary, PullRequest
from codedog.version import PROJECT, VERSION


class PullRequestReporter(Reporter, Localization):
    def __init__(
        self,
        pr_summary: PRSummary,
        code_summaries: list[ChangeSummary],
        pull_request: PullRequest,
        code_reviews: List[CodeReview],
        telemetry: Dict[str, Any] = None,
        language="en",
    ):
        self._pr_summary = pr_summary
        self._code_summaries = code_summaries
        self._pull_request = pull_request
        self._code_reviews = code_reviews
        self._telemetry = telemetry if telemetry else {}
        super().__init__(language=language)

    def report(self) -> str:
        telemetry = (
            self.template.REPORT_TELEMETRY.format(
                start_time=datetime.datetime.fromtimestamp(self._telemetry["start_time"]).strftime("%Y-%m-%d %H:%M:%S"),
                time_usage=self._telemetry["time_usage"],
                cost=self._telemetry["cost"],
                tokens=self._telemetry["tokens"],
            )
            if self._telemetry
            else ""
        )
        pr_report = PRSummaryMarkdownReporter(
            pr_summary=self._pr_summary,
            code_summaries=self._code_summaries,
            pull_request=self._pull_request,
            language=self.language,
        ).report()
        cr_report = CodeReviewMarkdownReporter(self._code_reviews, self.language).report()

        return self.template.REPORT_PR_REVIEW.format(
            repo_name=self._pull_request.repository_name,
            pr_number=self._pull_request.pull_request_number,
            pr_name=self._pull_request.title,
            url=self._pull_request.url,
            project=PROJECT,
            version=VERSION,
            telemetry=telemetry,
            pr_report=pr_report,
            cr_report=cr_report,
        )
