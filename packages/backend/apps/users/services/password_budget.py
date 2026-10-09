"""Account-wide password failure budget (E05 in EMAIL_PASSWORD_SECURITY_REVIEW.md).

The existing login rate limit is IP-based only (`@ratelimit(key="ip", rate="30/min")`), so a
distributed attacker spreading guesses across many source addresses never runs out of attempts
against one account. This adds a per-account counter, independent of IP, that locks the account
- rejecting even its correct password - after too many consecutive failures, with a progressive
cooldown. Keyed by a hash of the attempted email (not a User row), so an unregistered email is
locked out identically to a real one and nothing here discloses account existence.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.users.exceptions import PasswordBudgetExceeded
from apps.users.models import PasswordFailureBudget
from .security import email_identifier

MAX_FAILURES = 10
# Progressive cooldown in minutes, one step per budget exhaustion; the last value repeats for
# any further exhaustion rather than growing unbounded.
COOLDOWN_MINUTES = (1, 5, 15, 60)


def _cooldown_minutes(level: int) -> int:
    return COOLDOWN_MINUTES[min(level, len(COOLDOWN_MINUTES) - 1)]


def check_password(email: str, check):
    """Run `check` (a zero-argument callable performing the actual password verification,
    returning a truthy result on success or a falsy one on failure). Returns whatever `check()`
    returned on success, or None on failure. Raises PasswordBudgetExceeded without calling
    `check()` at all while locked - the correct password must also be rejected during the
    cooldown, otherwise this is not a real budget.

    The lock check and the failure-counter update are each their own short-lived transaction,
    deliberately NOT wrapped around the `check()` call itself: `check()` runs whatever
    transactional context the caller is already in (e.g. a GraphQL mutation that must still roll
    back a successful password check together with something that fails right after it, such as
    session creation). Only the failure counter must survive regardless of what the caller's
    transaction does later - otherwise a mutation that rolls back for an unrelated reason would
    silently erase the failed attempt it just counted, making the budget uncountable.
    """
    key = email_identifier(email)
    with transaction.atomic():
        PasswordFailureBudget.objects.get_or_create(pk=key)
        budget = PasswordFailureBudget.objects.select_for_update().get(pk=key)
        now = timezone.now()
        if budget.locked_until and budget.locked_until > now:
            raise PasswordBudgetExceeded("Too many attempts. Try again later.")

    result = check()

    if result:
        if budget.failures or budget.level or budget.locked_until:
            with transaction.atomic():
                PasswordFailureBudget.objects.filter(pk=key).delete()
        return result

    with transaction.atomic():
        budget = PasswordFailureBudget.objects.select_for_update().get(pk=key)
        now = timezone.now()
        budget.failures += 1
        budget.last_failure_at = now
        if budget.failures >= MAX_FAILURES:
            budget.locked_until = now + timedelta(minutes=_cooldown_minutes(budget.level))
            budget.level += 1
            budget.failures = 0
        budget.save(update_fields=["failures", "level", "locked_until", "last_failure_at"])
    return None


def clear(email: str):
    """Called after a successful password reset/change confirmation - completing one is itself
    proof of mailbox/account ownership, so any outstanding lockout from guessing the old
    password no longer serves a purpose and would otherwise strand the real owner."""
    PasswordFailureBudget.objects.filter(pk=email_identifier(email)).delete()
