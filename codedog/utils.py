"""
utility functions for codedog
"""
import hashlib
import logging
import time
from logging.config import dictConfig

import jwt
import requests

# -- Logging ------------------------------------------------------------------


def init_local_logging(level=logging.INFO):
    """setup logging interface for local debugging"""
    dictConfig(get_logging_config(level))


def get_logging_config(level=logging.INFO):
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "plain": {
                "format": "[%(asctime)s][%(levelname)s][%(pathname)s:%(lineno)d][%(name)s]%(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console_handler": {
                "level": "DEBUG",
                "formatter": "plain",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",  # Default is stderr
            },
        },
        "loggers": {
            "": {
                "level": level,
                "handlers": ["console_handler"],
            },
        },
    }


# -- exception ----------------------------------------------------------------


class CodedogError(Exception):
    def __init__(self, message: str = None, code: int = -1):
        self.message = "" if message is None else message
        self.code = code


# -- utility ------------------------------------------------------------------


def get_ttl_hash(seconds=3600):
    """Return the same value withing `seconds` time period"""
    return round(time.time() / seconds)


def get_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def get_sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def get_jwt_token(private_key, app_id):
    # 获取当前时间
    now = int(time.time())

    # 准备 JWT 的 payload
    payload = {
        # 发行人
        "iat": now,
        # JWT 的过期时间，这里设置为1分钟后
        "exp": now + (10 * 60),
        # GitHub App 的 ID
        "iss": app_id,
    }

    # 生成JWT
    jwt_token = jwt.encode(payload, private_key, algorithm="RS256")
    return jwt_token


def get_access_token_by_installation_id(installation_id: int, jwt_token: str):
    if installation_id is None:
        return None
    # 使用installation_id生成访问令牌
    token_url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": "Bearer {}".format(jwt_token),
        "Accept": "application/vnd.github.machine-man-preview+json",
    }
    response = requests.post(token_url, headers=headers)
    response.raise_for_status()
    token_info = response.json()
    return token_info["token"]
