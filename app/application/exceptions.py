class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class ProviderUnavailable(Exception):
    def __init__(self, message: str = "Price provider is temporarily unavailable", retry_after=30):
        super().__init__(message)
        self.retry_after = retry_after


class GameNotFound(Exception):
    pass
