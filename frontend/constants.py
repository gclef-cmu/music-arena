"""
Global constants for Music Arena application.
"""

from enum import IntEnum
import os

# Basic backend connection settings
BACKEND_URL = os.getenv("BACKEND_URL", "http://treble.cs.cmu.edu:12000")

# Survey link for feedback
SURVEY_LINK = "Have feedback? Fill out our [survey](https://forms.gle/BRJmeHuxTgPcqoAr8)."

# Error messages
SERVER_ERROR_MSG = "The server is currently experiencing high traffic. Please try again later."
MODERATION_MSG = "Your message contains content that violates our content policy. Please revise your message and try again."
CONVERSATION_LIMIT_MSG = "You have reached the conversation message limit. Please restart the conversation."
RATE_LIMIT_MSG = "You have reached the rate limit. Please try again later."

# Configuration limits
INPUT_CHAR_LEN_LIMIT = int(os.getenv("FASTCHAT_INPUT_CHAR_LEN_LIMIT", 12000))
CONVERSATION_TURN_LIMIT = 30
SESSION_EXPIRATION_TIME = 3600  # seconds

# The output dir of log files
LOGDIR = os.getenv("LOGDIR", ".")

# API timeouts
WORKER_API_TIMEOUT = int(os.getenv("FASTCHAT_WORKER_API_TIMEOUT", 100))


class ErrorCode(IntEnum):
    """
    Simple error codes for API responses
    """
    INVALID_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    RATE_LIMIT_EXCEEDED = 429
    INTERNAL_SERVER_ERROR = 500
