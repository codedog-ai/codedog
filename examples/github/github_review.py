import logging

from codedog.adapters.github_adapter import (
    build_pull_request_event,
    handle_github_event,
)
from codedog.utils import init_local_logging

init_local_logging(level=logging.DEBUG)

repository_name_or_id = "ClickHouse/ClickHouse"
pull_request_number = 49113

# repository_name_or_id = "gradio-app/gradio"
# pull_request_number = 480

# repository_name_or_id = "qdrant/qdrant"
# pull_request_number = 1245

# repository_name_or_id = "psf/requests"
# pull_request_number = 118

# repository_name_or_id = "apache/superset"
# pull_request_number = 7416


event = build_pull_request_event(repository_name_or_id=repository_name_or_id, pull_request_number=pull_request_number)

# handle_github_event(event, local=False)
handle_github_event(event, local=True)
