import logging
from logging.config import dictConfig


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
