"""
gitlab code review implementation.
"""
import datetime
import json
import logging
import time
import traceback

from langchain.callbacks import get_openai_callback
from langchain.schema import OutputParserException

from codedog.chains import Chains
from codedog.model import Change, ChangeSummary, PullRequest
from codedog.templates import template_cn, template_en
from codedog.version import VERSION

logger = logging.getLogger(__name__)

# TODO: unit test


class Review:
    """Code review execution wrapper"""

    def __init__(
        self,
        pr: PullRequest,
        changes: list[Change],
        callbacks: list | None = None,
        lang: str = "cn",
        **kwargs,
    ):
        assert lang in ("cn", "en")
        self.language = lang
        self._chains = Chains.init_chains(lang=lang)
        self._template = template_cn if lang == "cn" else template_en
        # --- data --------------------
        self._pr = pr
        self._changes: list[Change] = changes
        self._platform: str = kwargs.get("platform", "Github")

        self._pr_summary: str = ""

        self._telemetry: dict = {
            "tokens": 0,
            "cost": 0.0,
            "files": 0,
            "start_time": time.time(),
        }

        # --- data end ----------------
        self._callbacks = callbacks or []

        self._repr_dict = {"platform": self._platform}
        self._repr_dict["start_time"] = self._telemetry["start_time"]
        self._repr_dict["pull_request"] = self._pr.dict(exclude={"changes", "description", "issue_description"})
        self._repr_str = json.dumps(self._repr_dict)

        # --- telemetry ---------------

        self._meter_files(len(self._changes))

    def __str__(self):
        return f"Review({self._platform}-{self._pr.repository_id}-{self._pr.pr_id})"

    def json(self) -> str:
        return self._repr_dict

    def json_str(self) -> str:
        return self._repr_str

    async def execute(self) -> None:
        """Execute code review."""
        logger.debug("Start code review %s", self.json_str())
        try:
            await self._single_file_summarize()
            await self._changelist_summarize()
            await self._feedback()

            self._telemetry["time_usage"] = time.time() - self._telemetry["start_time"]

            await self._execute_callback()

            logger.info("Success code review %s", self.json_str())
        except Exception as ex:
            logger.warn("Fail code review %s %s %s", ex, self.json_str(), traceback.format_exc().replace("\n", "\\n"))

    def print_report(self) -> None:
        print(self.report())

    def report(self) -> str:
        return self._generate_report()

    async def _single_file_summarize(self):
        # TODO: handle openai.error.RateLimitError with langchain

        with get_openai_callback() as cb:
            for change in self._changes:
                text = change.content[:4000]  # TODO: handle long text
                file_name = change.file_name
                args = {"text": text, "name": file_name}

                result = self._chains.review_chain.run(args)

                try:
                    summary = self._chains.review_parser.parse(result)
                except OutputParserException as ex:
                    del ex
                    logger.warn("Fail parse review response for %s %s", file_name, self.json_str())
                    fallback_result = self._chains.review_fallback_chain.run(args)
                    summary = ChangeSummary(summary=fallback_result)

                change.summary = summary.summary
                change.major = not summary.main_change_flag

            self._meter_api_call_tokens(cb.total_tokens, cb.total_cost)

    async def _changelist_summarize(self):
        with get_openai_callback() as cb:
            result = self._chains.summary_chain.run(
                {
                    "pull_request_info": f"{self._pr.title}\n\n{self._pr.description}",
                    "issue_info": f"{self._pr.issue_title}\n\n{self._pr.issue_description}"
                    if self._pr.issue_id
                    else "no data",
                    "summary": "\n\n".join(
                        f"---\n[{change.file_name}]:\n{change.summary}\n---"
                        for change in self._changes
                        if not change.major
                    ),
                }
            )
            self._meter_api_call_tokens(cb.total_tokens, cb.total_cost)

        self._pr_summary = result

    async def _feedback(self):
        with get_openai_callback() as cb:
            for change in self._changes:
                # FIXME: long diff not in content
                if not change.content:
                    continue

                result = self._chains.feedback_chain.run({"text": change.content[:4000]})
                change.feedback = result

            self._meter_api_call_tokens(cb.total_tokens, cb.total_cost)

    def _generate_report(self) -> str:
        header: str = self._template.REPORT_HEADER.format(
            repo_name=self._pr.repository_name, pr_number=self._pr.pr_id, url=self._pr.url, version=VERSION
        )

        telemetry: str = self._template.REPORT_TELEMETRY.format(
            start_time=datetime.datetime.fromtimestamp(self._telemetry["start_time"]).strftime("%Y-%m-%d %H:%M:%S"),
            time_usage=int(self._telemetry["time_usage"]),
            files=self._telemetry["files"],
            tokens=self._telemetry["tokens"],
            cost=self._telemetry.get("cost", 0),
        )

        summary: str = self._template.REPORT_PR_SUMMARY.format(
            pr_summary=self._pr_summary,
            pr_changes_summary=self._generate_change_summary(),
        )
        feedback: str = self._template.REPORT_FEEDBACK.format(feedback=self._generate_feedback())

        report = "\n".join([header, telemetry, summary, feedback])
        return report

    def _generate_change_summary(self) -> str:
        """format change summary

        Args:
            changes (list[Change]): pr changes and reviews
        Returns:
            str: format markdown table string of change summary
        """
        changes = self._changes
        important_changes = []
        housekeeping_changes = []

        important_idx = 1
        housekeeping_idx = 1
        for change in changes:
            file_name = change.file_name or ""
            url = change.url or ""
            summary = change.summary or ""

            text = summary.replace("\n", "<br/>") if summary else ""
            text_template: str = self._template.TABLE_LINE.format(file_name=file_name, url=url, text=text)

            if not change.major:
                text = text_template.format(idx=important_idx)
                important_idx += 1
                important_changes.append(text)
            else:
                text = text_template.format(idx=housekeeping_idx)
                housekeeping_idx += 1
                housekeeping_changes.append(text)

        important_changes = "\n".join(important_changes) if important_changes else self._template.TABLE_LINE_NODATA
        housekeeping_changes = (
            "\n".join(housekeeping_changes) if housekeeping_changes else self._template.TABLE_LINE_NODATA
        )
        text = self._template.CHANGE_SUMMARY.format(
            important_changes=important_changes, housekeeping_changes=housekeeping_changes
        )
        return text

    def _generate_feedback(self) -> str:
        """format feedback

        Args:
            changes (list[Change]): pr changes and reviews
        Returns:
            str: format markdown table string of feedback
        """
        changes = self._changes

        texts = []

        idx = 1
        for change in changes:
            file_name = change.file_name
            url = change.url

            feedback = change.feedback
            if (
                not feedback
                or feedback in ("ok", "OK")
                or (len(feedback) < 30 and "ok" in feedback.lower())  # 移除ok + 其他短语的回复
            ):
                continue

            text = f"{self._template.T3_TITLE_LINE.format(idx=idx, file_name=file_name, url=url)}\n\n{feedback}"

            texts.append(text)
            idx += 1

        concat_feedback_text = "\n\n".join(texts) if texts else self._template.TABLE_LINE_NODATA
        return concat_feedback_text

    async def _execute_callback(self):
        if not self._callbacks:
            self.print_report()

        for callback in self._callbacks:
            await callback(self)

    def _meter_api_call_tokens(self, tokens: int, cost: float = 0.0):
        self._telemetry["tokens"] += tokens
        self._telemetry["cost"] += cost

    def _meter_files(self, files: int):
        self._telemetry["files"] += files

    def _meter_important_files(self, files: int):
        self._telemetry["important_files"] += files
