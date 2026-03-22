import logging
import os

class AppLogger:
    """
    Centralized logging utility with toggleable debug mode.
    Complies with CURRENT_STATE.md debugging code system requirements.
    """
    _instance = None
    _debug_mode = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppLogger, cls).__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self):
        self.logger = logging.getLogger("Paleo_01")
        self.logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def set_debug(self, enabled: bool):
        """Toggle debug mode."""
        self._debug_mode = enabled
        if enabled:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

    def is_debug(self) -> bool:
        return self._debug_mode

    def debug(self, msg, *args, **kwargs):
        if self._debug_mode:
            self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

# Global logger instance
logger = AppLogger()
