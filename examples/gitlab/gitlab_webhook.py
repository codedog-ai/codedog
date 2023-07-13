import logging

import requests

from codedog.adapters.gitlab_adapter import build_merge_request_event
from codedog.utils import init_local_logging

init_local_logging(level=logging.DEBUG)

repository_id = 1
merge_request_iid = 1

token = ""
url = ""
server = f"http://127.0.0.1:32167/v1/webhook/gitlab?token={token}&url={url}"

event = build_merge_request_event(repository_id, merge_request_iid)

requests.post(url=server, data=event.json(), headers={"Content-Type": "application/json"})
