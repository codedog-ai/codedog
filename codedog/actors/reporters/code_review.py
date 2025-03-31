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
                "correctness": 0,
                "readability": 0,
                "maintainability": 0,
                "standards_compliance": 0,
                "performance": 0,
                "security": 0,
                "overall": 0
            }
        }
        
        try:
            # Look for the scores section
            scores_section = re.search(r'#{1,3}\s*SCORES:\s*([\s\S]*?)(?=#{1,3}|$)', review_text)
            if not scores_section:
                print(f"No scores section found for {file_name}")
                return default_scores
                
            scores_text = scores_section.group(1)
            
            # Extract individual scores
            correctness = self._extract_score(scores_text, "Correctness")
            readability = self._extract_score(scores_text, "Readability")
            maintainability = self._extract_score(scores_text, "Maintainability")
            standards = self._extract_score(scores_text, "Standards Compliance")
            performance = self._extract_score(scores_text, "Performance")
            security = self._extract_score(scores_text, "Security")
            overall = self._extract_score(scores_text, "Overall")
            
            # Update scores if found
            if any([correctness, readability, maintainability, standards, performance, security, overall]):
                return {
                    "file": file_name,
                    "scores": {
                        "correctness": correctness or 0,
                        "readability": readability or 0,
                        "maintainability": maintainability or 0,
                        "standards_compliance": standards or 0,
                        "performance": performance or 0,
                        "security": security or 0,
                        "overall": overall or 0
                    }
                }
                
        except Exception as e:
            print(f"Error extracting scores from review for {file_name}: {e}")
        
        return default_scores

    def _extract_score(self, text: str, dimension: str) -> float:
        """Extract a score for a specific dimension from text."""
        try:
            # Find patterns like "Correctness: 4.5 /5" or "- Readability: 3.8/5"
            pattern = rf'[-\s]*{dimension}:\s*(\d+(?:\.\d+)?)\s*\/?5'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        except Exception as e:
            print(f"Error extracting {dimension} score: {e}")
        return 0

    def _calculate_average_scores(self) -> Dict:
        """Calculate the average scores across all files."""
        if not self._scores:
            return {
                "avg_correctness": 0,
                "avg_readability": 0,
                "avg_maintainability": 0,
                "avg_standards": 0,
                "avg_performance": 0,
                "avg_security": 0,
                "avg_overall": 0
            }
        
        total_files = len(self._scores)
        avg_scores = {
            "avg_correctness": sum(s["scores"]["correctness"] for s in self._scores) / total_files,
            "avg_readability": sum(s["scores"]["readability"] for s in self._scores) / total_files,
            "avg_maintainability": sum(s["scores"]["maintainability"] for s in self._scores) / total_files,
            "avg_standards": sum(s["scores"]["standards_compliance"] for s in self._scores) / total_files,
            "avg_performance": sum(s["scores"]["performance"] for s in self._scores) / total_files,
            "avg_security": sum(s["scores"]["security"] for s in self._scores) / total_files,
            "avg_overall": sum(s["scores"]["overall"] for s in self._scores) / total_files
        }
        
        return avg_scores

    def _get_quality_assessment(self, avg_overall: float) -> str:
        """Generate a quality assessment based on the average overall score."""
        if avg_overall >= 4.5:
            return "Excellent code quality. The PR demonstrates outstanding adherence to best practices and coding standards."
        elif avg_overall >= 4.0:
            return "Very good code quality. The PR shows strong adherence to standards with only minor improvement opportunities."
        elif avg_overall >= 3.5:
            return "Good code quality. The PR meets most standards but has some areas for improvement."
        elif avg_overall >= 3.0:
            return "Satisfactory code quality. The PR is acceptable but has several areas that could be improved."
        elif avg_overall >= 2.0:
            return "Needs improvement. The PR has significant issues that should be addressed before merging."
        else:
            return "Poor code quality. The PR has major issues that must be fixed before it can be accepted."

    def _generate_summary_table(self) -> str:
        """Generate a summary table of all file scores."""
        if not self._scores:
            return ""
        
        file_score_rows = []
        for score in self._scores:
            file_name = score["file"]
            s = score["scores"]
            file_score_rows.append(
                f"| {file_name} | {s['correctness']:.2f} | {s['readability']:.2f} | {s['maintainability']:.2f} | "
                f"{s['standards_compliance']:.2f} | {s['performance']:.2f} | {s['security']:.2f} | {s['overall']:.2f} |"
            )
        
        avg_scores = self._calculate_average_scores()
        quality_assessment = self._get_quality_assessment(avg_scores["avg_overall"])
        
        return self.template.PR_REVIEW_SUMMARY_TABLE.format(
            file_scores="\n".join(file_score_rows),
            avg_correctness=avg_scores["avg_correctness"],
            avg_readability=avg_scores["avg_readability"],
            avg_maintainability=avg_scores["avg_maintainability"],
            avg_standards=avg_scores["avg_standards"],
            avg_performance=avg_scores["avg_performance"],
            avg_security=avg_scores["avg_security"],
            avg_overall=avg_scores["avg_overall"],
            quality_assessment=quality_assessment
        )

    def _generate_report(self):
        code_review_segs = []
        
        for code_review in self._code_reviews:
            # Extract scores if the review is not empty
            if hasattr(code_review, 'review') and code_review.review.strip():
                file_name = code_review.file.full_name if hasattr(code_review, 'file') and hasattr(code_review.file, 'full_name') else "Unknown"
                score_data = self._extract_scores(code_review.review, file_name)
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
