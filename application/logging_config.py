import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler


class UnicodeFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        return msg.encode("unicode_escape").decode("utf-8")


def setup_logging(default_level=logging.INFO):
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": "DEBUG",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "default",
                "level": "INFO",
                "filename": "logs/application.log",
                "encoding": "utf-8",
                "maxBytes": 10485760,  # 10 MB
                "backupCount": 5,
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": default_level,
        },
    }

    # Ensure the logs directory exists
    os.makedirs("logs", exist_ok=True)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(UnicodeFormatter())
    # Configure logging
    logging.config.dictConfig(log_config)
