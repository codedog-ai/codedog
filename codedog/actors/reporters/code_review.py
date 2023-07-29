from codedog.actors.reporters.base import Reporter
from codedog.localization import Localization
from codedog.models.code_review import CodeReview


class CodeReviewMarkdownReporter(Reporter, Localization):
    def __init__(self, code_reviews: list[CodeReview], language="en"):
        self._code_reviews: list[CodeReview] = code_reviews
        self._markdown: str = ""

        super().__init__(language=language)

    def report(self) -> str:
        if not self._markdown:
            self._markdown = self._generate_report()

        return self._markdown

    def _generate_report(self):
        code_review_segs = []
        for code_review in self._code_reviews:
            code_review_segs.append(
                self.template.REPORT_CODE_REVIEW_SEGMENT.format(
                    full_name=code_review.file.full_name,
                    url=code_review.file.diff_url,
                    review=code_review.review,
                )
            )

        return self.template.REPORT_CODE_REVIEW.format(
            feedback="\n".join(code_review_segs),
        )
