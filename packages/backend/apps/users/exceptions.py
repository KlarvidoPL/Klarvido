from common.exceptions import DomainException


class OTPVerificationFailure(DomainException):
    pass


class OTPAttemptLimitExceeded(DomainException):
    pass
