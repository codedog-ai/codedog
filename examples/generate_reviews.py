import asyncio
import logging
import os
import traceback

from codedog.adapters.github_adapter import get_pr
from codedog.model import PullRequest
from codedog.review import Review
from codedog.utils import init_local_logging

init_local_logging(level=logging.INFO)

logger = logging.getLogger(__name__)


def load_pulls(file_path: str):
    pulls = []
    with open(file_path) as f:
        for line in f:
            repo, pull_number = line.rstrip().split(",")
            pulls.append((repo, int(pull_number)))
    return pulls


async def review_and_report(repository_id, pull_request_number, retry=0) -> str:
    if retry > 0:
        logger.warn("Fail to review, retry %s...", retry)

    if retry >= 3:
        raise RuntimeError(f"Fail to review {repository_id} {pull_request_number}")

    try:
        pr: PullRequest = get_pr(repository_id, pull_request_number)
        review = Review(pr, pr.changes)

        await review.execute()
    except:  # noqa
        traceback.print_exc()
        return await review_and_report(repository_id, pull_request_number, retry=retry + 1)

    return review.report()


async def generate_reviews(input_path: str = "examples/pulls.csv", output_path: str = "tmp/report"):
    pulls = load_pulls(input_path)
    logger.info("Get %s pulls", len(pulls))
    for repo_id, pull_no in pulls:
        logger.info("Start review: %s %s", repo_id, pull_no)
        result = await review_and_report(repository_id=repo_id, pull_request_number=pull_no)
        with open(f"{output_path}/{repo_id.lower().replace('/','_')}_{pull_no}.md", "w", encoding="utf-8") as f:
            f.write(result)


if __name__ == "__main__":
    os.makedirs("tmp/report", exist_ok=True)
    asyncio.run(generate_reviews())
