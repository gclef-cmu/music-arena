from typing import Optional


class ChatException(Exception):
    pass


class PromptException(Exception):
    pass


class PromptTooLongException(PromptException):
    pass


class PromptContentException(PromptException):
    def __init__(
        self, rationale: Optional[str] = None, error_message: Optional[str] = None
    ):
        self.rationale = rationale
        self.error_message = error_message
        super().__init__(self.rationale)


class SystemException(Exception):
    pass


class SystemTimeoutException(SystemException):
    pass


class RateLimitException(Exception):
    pass
