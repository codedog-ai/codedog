import json
import re
from typing import Dict, List, Tuple, Any

from codedog.actors.reporters.base import Reporter
from codedog.localization import Localization
from codedog.models.code_review import CodeReview


class CodeReviewMarkdownReporter(Reporter, Localization):
    def __init__(self, code_reviews: list[CodeReview], language="en"):
        self._code_reviews: list[CodeReview] = code_reviews
        self._markdown: str = ""
        self._scores: List[Dict] = []

        super().__init__(language=language)

    def report(self) -> str:
        if not self._markdown:
            self._markdown = self._generate_report()

        return self._markdown

    def _extract_scores(self, review_text: str, file_name: str) -> Dict[str, Any]:
        """Extract scores from the review text using a simple format."""
        # Default empty score data
        default_scores = {
            "file": file_name,
            "scores": {
                "readability": 0,
                "efficiency": 0,
                "security": 0,
                "structure": 0,
                "error_handling": 0,
                "documentation": 0,
                "code_style": 0,
                "overall": 0
            }
        }

        try:
            # Look for the scores section
            scores_section = re.search(r'#{1,3}\s*(?:SCORES|评分):\s*([\s\S]*?)(?=#{1,3}|$)', review_text)
            if not scores_section:
                print(f"No scores section found for {file_name}")
                return default_scores

            scores_text = scores_section.group(1)

            # Extract individual scores
            readability = self._extract_score(scores_text, "Readability|可读性")
            efficiency = self._extract_score(scores_text, "Efficiency & Performance|效率与性能")
            security = self._extract_score(scores_text, "Security|安全性")
            structure = self._extract_score(scores_text, "Structure & Design|结构与设计")
            error_handling = self._extract_score(scores_text, "Error Handling|错误处理")
            documentation = self._extract_score(scores_text, "Documentation & Comments|文档与注释")
            code_style = self._extract_score(scores_text, "Code Style|代码风格")

            # Extract overall score with a more flexible pattern
            overall = self._extract_score(scores_text, "Final Overall Score|最终总分")
            if overall == 0:  # If not found with standard pattern, try alternative patterns
                try:
                    # Try to match patterns like "**Final Overall Score: 8.1** /10"
                    pattern = r'\*\*(?:Final Overall Score|最终总分):\s*(\d+(?:\.\d+)?)\*\*\s*\/10'
                    match = re.search(pattern, scores_text, re.IGNORECASE)
                    if match:
                        overall = float(match.group(1))
                except Exception as e:
                    print(f"Error extracting overall score with alternative pattern: {e}")

            # Update scores if found
            if any([readability, efficiency, security, structure, error_handling, documentation, code_style, overall]):
                scores = {
                    "file": file_name,
                    "scores": {
                        "readability": readability or 0,
                        "efficiency": efficiency or 0,
                        "security": security or 0,
                        "structure": structure or 0,
                        "error_handling": error_handling or 0,
                        "documentation": documentation or 0,
                        "code_style": code_style or 0,
                        "overall": overall or 0
                    }
                }
                print(f"Extracted scores for {file_name}: {scores['scores']}")
                return scores

        except Exception as e:
            print(f"Error extracting scores from review for {file_name}: {e}")

        return default_scores

    def _extract_score(self, text: str, dimension: str) -> float:
        """Extract a score for a specific dimension from text."""
        try:
            # Find patterns like "Readability: 8.5 /10", "- Security: 7.2/10", or "Readability: **8.5** /10"
            pattern = rf'[-\s]*(?:{dimension}):\s*(?:\*\*)?(\d+(?:\.\d+)?)(?:\*\*)?\s*\/?10'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                print(f"Found {dimension} score: {score}")
                return score
            else:
                print(f"No match found for {dimension} using pattern: {pattern}")
                # Print a small excerpt of the text for debugging
                excerpt = text[:200] + "..." if len(text) > 200 else text
                print(f"Text excerpt: {excerpt}")
        except Exception as e:
            print(f"Error extracting {dimension} score: {e}")
        return 0

    def _calculate_average_scores(self) -> Dict:
        """Calculate the average scores across all files."""
        if not self._scores:
            return {
                "avg_readability": 0,
                "avg_efficiency": 0,
                "avg_security": 0,
                "avg_structure": 0,
                "avg_error_handling": 0,
                "avg_documentation": 0,
                "avg_code_style": 0,
                "avg_overall": 0
            }

        total_files = len(self._scores)
        avg_scores = {
            "avg_readability": sum(s["scores"]["readability"] for s in self._scores) / total_files,
            "avg_efficiency": sum(s["scores"]["efficiency"] for s in self._scores) / total_files,
            "avg_security": sum(s["scores"]["security"] for s in self._scores) / total_files,
            "avg_structure": sum(s["scores"]["structure"] for s in self._scores) / total_files,
            "avg_error_handling": sum(s["scores"]["error_handling"] for s in self._scores) / total_files,
            "avg_documentation": sum(s["scores"]["documentation"] for s in self._scores) / total_files,
            "avg_code_style": sum(s["scores"]["code_style"] for s in self._scores) / total_files,
            "avg_overall": sum(s["scores"]["overall"] for s in self._scores) / total_files
        }

        return avg_scores

    def _get_quality_assessment(self, avg_overall: float) -> str:
        """Generate a quality assessment based on the average overall score."""
        if avg_overall >= 9.0:
            return "Excellent code quality. The PR demonstrates outstanding adherence to best practices and coding standards."
        elif avg_overall >= 7.0:
            return "Very good code quality. The PR shows strong adherence to standards with only minor improvement opportunities."
        elif avg_overall >= 5.0:
            return "Good code quality. The PR meets most standards but has some areas for improvement."
        elif avg_overall >= 3.0:
            return "Needs improvement. The PR has significant issues that should be addressed before merging."
        else:
            return "Poor code quality. The PR has major issues that must be fixed before it can be accepted."

    def _generate_summary_table(self) -> str:
        """Generate a summary table of all file scores."""
        if not self._scores:
            return ""

        print(f"Generating summary table with {len(self._scores)} files")
        for i, score in enumerate(self._scores):
            print(f"File {i+1}: {score['file']} - Scores: {score['scores']}")

        file_score_rows = []
        for score in self._scores:
            file_name = score["file"]
            s = score["scores"]
            file_score_rows.append(
                f"| {file_name} | {s['readability']:.1f} | {s['efficiency']:.1f} | {s['security']:.1f} | "
                f"{s['structure']:.1f} | {s['error_handling']:.1f} | {s['documentation']:.1f} | {s['code_style']:.1f} | {s['overall']:.1f} |"
            )

        avg_scores = self._calculate_average_scores()
        quality_assessment = self._get_quality_assessment(avg_scores["avg_overall"])

        return self.template.PR_REVIEW_SUMMARY_TABLE.format(
            file_scores="\n".join(file_score_rows),
            avg_readability=avg_scores["avg_readability"],
            avg_efficiency=avg_scores["avg_efficiency"],
            avg_security=avg_scores["avg_security"],
            avg_structure=avg_scores["avg_structure"],
            avg_error_handling=avg_scores["avg_error_handling"],
            avg_documentation=avg_scores["avg_documentation"],
            avg_code_style=avg_scores["avg_code_style"],
            avg_overall=avg_scores["avg_overall"],
            quality_assessment=quality_assessment
        )

    def _generate_report(self):
        code_review_segs = []
        print(f"Processing {len(self._code_reviews)} code reviews")

        for i, code_review in enumerate(self._code_reviews):
            # Extract scores if the review is not empty
            if hasattr(code_review, 'review') and code_review.review.strip():
                file_name = code_review.file.full_name if hasattr(code_review, 'file') and hasattr(code_review.file, 'full_name') else "Unknown"
                print(f"\nExtracting scores for review {i+1}: {file_name}")
                score_data = self._extract_scores(code_review.review, file_name)
                print(f"Extracted score data: {score_data}")
                self._scores.append(score_data)

            # Add the review text (without modification)
            code_review_segs.append(
                self.template.REPORT_CODE_REVIEW_SEGMENT.format(
                    full_name=code_review.file.full_name if hasattr(code_review, 'file') and hasattr(code_review.file, 'full_name') else "Unknown",
                    url=code_review.file.diff_url if hasattr(code_review, 'file') and hasattr(code_review.file, 'diff_url') else "#",
                    review=code_review.review if hasattr(code_review, 'review') else "",
                )
            )

        # Generate review content
        review_content = self.template.REPORT_CODE_REVIEW.format(
            feedback="\n".join(code_review_segs) if code_review_segs else self.template.REPORT_CODE_REVIEW_NO_FEEDBACK,
        )

        # Add summary table at the end if we have scores
        summary_table = self._generate_summary_table()
        if summary_table:
            review_content += "\n\n" + summary_table

        return review_content
