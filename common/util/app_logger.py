# common/util/logging.py
import logging
import sys

class AppLogger:
    """
    Static-style logger factory.
    Usage:
        logger = AppLogger.get_logger(__name__)
        logger.info("msg", extra={"key": "value"})
    """

    _configured = False

    @staticmethod
    def _configure_root():
        if AppLogger._configured:
            return
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)

        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.handlers.clear()
        root.addHandler(handler)

        AppLogger._configured = True

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        AppLogger._configure_root()
        logger = logging.getLogger(name)
        # Optional: ensure `extra` dicts don’t crash formatting
        # by pre-wrapping into a single string if needed.
        return logger

    # Convenience static helpers, if you like calling directly:
    @staticmethod
    def info(msg: str, **kwargs):
        AppLogger.get_logger("app").info(msg, extra=kwargs or None)

    @staticmethod
    def error(msg: str, **kwargs):
        AppLogger.get_logger("app").error(msg, extra=kwargs or None)

    @staticmethod
    def debug(msg: str, **kwargs):
        AppLogger.get_logger("app").debug(msg, extra=kwargs or None)
