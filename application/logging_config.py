import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler


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

    # Configure logging
    logging.config.dictConfig(log_config)
