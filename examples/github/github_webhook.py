"""This example is based on github.com"""
import logging

import requests

from codedog.adapters.github_adapter import build_pull_request_event
from codedog.utils import init_local_logging

init_local_logging(level=logging.INFO)

repository_name_or_id = "ClickHouse/ClickHouse"
pull_request_number = 49113

server = "http://127.0.0.1:32167/api/v1/webhook/github"
event = build_pull_request_event(repository_name_or_id=repository_name_or_id, pull_request_number=pull_request_number)

# example: https://github.com/Arcadia822/codedog/pull/3
requests.post(url=server, data=event.json(), headers={"Content-Type": "application/json"})
