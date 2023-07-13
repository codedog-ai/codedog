import logging

from codedog.adapters.gitlab_adapter import (
    build_merge_request_event,
    handle_gitlab_event,
)
from codedog.utils import init_local_logging

init_local_logging(level=logging.INFO)


repository_id = 1
merge_request_iid = 1

url = ""
token = ""

event = build_merge_request_event(repository_id, merge_request_iid, token, url)

handle_gitlab_event(event, url, token, local=True)
