"""
utility functions for codedog
"""
import hashlib
import logging
import time
from logging.config import dictConfig

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
