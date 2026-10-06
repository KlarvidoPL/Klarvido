from common.exceptions import DomainException


class OpenAIClientException(Exception):
    pass


class OpenAIServiceUnavailable(DomainException):
    """Public availability error; never expose upstream exception details."""
