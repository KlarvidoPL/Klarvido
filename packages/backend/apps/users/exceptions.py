from common.exceptions import DomainException


class OTPVerificationFailure(DomainException):
    pass


class OTPAttemptLimitExceeded(DomainException):
    pass


class PasswordBudgetExceeded(DomainException):
    """Account-wide password failure budget (E05) exhausted - the account is locked and even
    its correct password is rejected until the cooldown expires. Callers must map this to a
    generic message/code (e.g. "too_many_attempts") rather than ever revealing remaining
    lockout time or distinguishing a locked account from an unknown email."""
