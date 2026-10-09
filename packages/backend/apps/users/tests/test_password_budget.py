"""Account-wide password failure budget (E05 in EMAIL_PASSWORD_SECURITY_REVIEW.md).

Covers the service directly (apps.users.services.password_budget) plus its wiring into login
(tokenAuth), change-password and the passkey-management fresh-auth password proof.
"""

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.exceptions import PasswordBudgetExceeded
from apps.users.models import PasswordFailureBudget
from apps.users.services import password_budget
from common.ratelimiting.config import clear_config_cache

pytestmark = pytest.mark.django_db

API_GRAPHQL_PATH = "/api/graphql/"
LOGIN = "mutation($input: ObtainTokenMutationInput!) { " "tokenAuth(input: $input) { authenticated } }"


@pytest.fixture(autouse=True)
def _clear_rate_limit_state():
    # This file deliberately fires 10+ requests per test against real rate-limited endpoints
    # (tokenAuth, changePassword, the passkey reauth view) to exercise the password budget - the
    # underlying rate-limit counters live in the real cache (Redis), not inside the per-test DB
    # transaction, so without this they would otherwise leak into whichever test runs next in
    # the same session and spuriously rate-limit it.
    yield
    cache.clear()


class TestCheckPasswordService:
    def test_correct_password_without_prior_failures_leaves_no_failure_state(self):
        email = "no-failures@example.com"
        result = password_budget.check_password(email, lambda: "ok")
        assert result == "ok"
        row = PasswordFailureBudget.objects.filter(pk=password_budget.email_identifier(email)).first()
        assert row is None or (row.failures == 0 and row.locked_until is None)

    def test_failures_accumulate_and_lock_after_ten(self):
        email = "lockout@example.com"
        for _ in range(9):
            result = password_budget.check_password(email, lambda: False)
            assert result is None
        # 10th failure crosses the threshold and locks immediately.
        result = password_budget.check_password(email, lambda: False)
        assert result is None

        with pytest.raises(PasswordBudgetExceeded):
            password_budget.check_password(email, lambda: True)  # even a "correct" check

    def test_check_is_not_called_at_all_while_locked(self):
        email = "no-call@example.com"
        calls = []
        for _ in range(10):
            password_budget.check_password(email, lambda: calls.append(1) or False)

        with pytest.raises(PasswordBudgetExceeded):
            password_budget.check_password(email, lambda: calls.append("should not run"))
        assert "should not run" not in calls

    def test_successful_check_clears_failures(self):
        email = "recovers@example.com"
        for _ in range(5):
            password_budget.check_password(email, lambda: False)
        result = password_budget.check_password(email, lambda: "ok")
        assert result == "ok"
        assert not PasswordFailureBudget.objects.filter(pk=password_budget.email_identifier(email)).exists()

    def test_progressive_cooldown_lengthens_on_repeated_exhaustion(self):
        email = "progressive@example.com"
        for _ in range(10):
            password_budget.check_password(email, lambda: False)
        row = PasswordFailureBudget.objects.get(pk=password_budget.email_identifier(email))
        first_cooldown = row.locked_until - row.last_failure_at
        assert abs(first_cooldown.total_seconds() - 60) < 5

        # Jump past the first lock so the next ten failures exhaust the budget again.
        row.locked_until = timezone.now()
        row.save(update_fields=["locked_until"])
        for _ in range(10):
            password_budget.check_password(email, lambda: False)
        row.refresh_from_db()
        second_cooldown = row.locked_until - row.last_failure_at
        assert second_cooldown.total_seconds() > first_cooldown.total_seconds()

    def test_unknown_email_is_locked_identically_to_a_real_one(self):
        """The budget is keyed by an email hash, not a User row - an attacker probing for
        which emails exist must see the exact same lockout behavior either way."""
        unknown_email = "definitely-not-registered@example.com"
        for _ in range(10):
            password_budget.check_password(unknown_email, lambda: False)
        with pytest.raises(PasswordBudgetExceeded):
            password_budget.check_password(unknown_email, lambda: True)

    def test_clear_removes_the_row(self):
        email = "cleared@example.com"
        for _ in range(10):
            password_budget.check_password(email, lambda: False)
        assert PasswordFailureBudget.objects.filter(pk=password_budget.email_identifier(email)).exists()

        password_budget.clear(email)
        assert not PasswordFailureBudget.objects.filter(pk=password_budget.email_identifier(email)).exists()
        # No longer locked - a fresh budget starts from zero.
        result = password_budget.check_password(email, lambda: True)
        assert result is True


class TestLoginSharesAccountWideBudget:
    def test_distributed_guessing_across_many_ips_still_locks_the_account(self, user_factory, faker):
        """E05: the existing per-IP login limit alone lets an attacker spread guesses across
        many source addresses. The account-wide budget must still lock regardless of IP."""
        password = "Correct-password-42!"
        user = user_factory(password=password)

        for i in range(10):
            client = APIClient()
            client.defaults["REMOTE_ADDR"] = f"203.0.113.{i}"
            response = client.post(
                API_GRAPHQL_PATH,
                {"query": LOGIN, "variables": {"input": {"email": user.email, "password": "wrong"}}},
                format="json",
            )
            assert response.json().get("errors"), response.json()

        # The correct password is now rejected too, from yet another IP.
        client = APIClient()
        client.defaults["REMOTE_ADDR"] = "198.51.100.99"
        response = client.post(
            API_GRAPHQL_PATH,
            {"query": LOGIN, "variables": {"input": {"email": user.email, "password": password}}},
            format="json",
        )
        errors = response.json().get("errors")
        assert errors
        assert errors[0]["extensions"]["non_field_errors"][0]["code"] == "too_many_attempts"

    def test_successful_login_clears_the_budget(self, user_factory):
        password = "Correct-password-42!"
        user = user_factory(password=password)
        for _ in range(5):
            client = APIClient()
            client.post(
                API_GRAPHQL_PATH,
                {"query": LOGIN, "variables": {"input": {"email": user.email, "password": "wrong"}}},
                format="json",
            )
        response = APIClient().post(
            API_GRAPHQL_PATH,
            {"query": LOGIN, "variables": {"input": {"email": user.email, "password": password}}},
            format="json",
        )
        assert "errors" not in response.json()
        assert not PasswordFailureBudget.objects.filter(pk=password_budget.email_identifier(user.email)).exists()

    def test_passkey_login_is_unaffected_by_a_locked_password_budget(self, user_factory, user_passkey_factory, faker):
        """A locked password budget must not block the account's other login methods."""
        password = "Correct-password-42!"
        user = user_factory(password=password)
        for _ in range(10):
            APIClient().post(
                API_GRAPHQL_PATH,
                {"query": LOGIN, "variables": {"input": {"email": user.email, "password": "wrong"}}},
                format="json",
            )
        assert PasswordFailureBudget.objects.filter(pk=password_budget.email_identifier(user.email)).exists()
        # Sanity: the budget is genuinely account-specific, not a global lock - a different
        # account's password login still works normally while this one is locked.
        other = user_factory(password="Other-password-1!")
        response = APIClient().post(
            API_GRAPHQL_PATH,
            {"query": LOGIN, "variables": {"input": {"email": other.email, "password": "Other-password-1!"}}},
            format="json",
        )
        assert "errors" not in response.json()


class TestChangePasswordSharesTheBudget:
    def test_wrong_old_password_guesses_also_lock_the_account(self, user_factory, settings):
        # Raise the independent per-user changePassword operation limit out of the way so
        # this test exercises the password budget (E05) itself.
        settings.RATE_LIMITS = {**settings.RATE_LIMITS, "auth.password_change": {"rate": "100/min"}}
        clear_config_cache()

        password = "Correct-password-42!"
        user = user_factory(password=password)
        client = APIClient()
        client.force_authenticate(user)
        mutation = "mutation($input: ChangePasswordMutationInput!) { changePassword(input: $input) { authenticated } }"
        for _ in range(10):
            client.post(
                API_GRAPHQL_PATH,
                {"query": mutation, "variables": {"input": {"oldPassword": "wrong", "newPassword": "New-pass-1!"}}},
                format="json",
            )
        response = client.post(
            API_GRAPHQL_PATH,
            {"query": mutation, "variables": {"input": {"oldPassword": password, "newPassword": "New-pass-1!"}}},
            format="json",
        )
        errors = response.json().get("errors")
        assert errors
        assert errors[0]["extensions"]["old_password"][0]["code"] == "too_many_attempts"
        user.refresh_from_db()
        assert user.check_password(password)


class TestPasskeyManagementFreshAuthSharesTheBudget:
    def test_wrong_password_proof_guesses_lock_via_the_same_budget(self, user_factory, settings):
        # Raise the independent passkey-endpoint IP throttle out of the way so this test
        # exercises the password budget (E05) itself, not the pre-existing per-IP limit.
        settings.RATE_LIMITS = {**settings.RATE_LIMITS, "auth.passkey": {"rate": "100/min"}}
        clear_config_cache()

        password = "Correct-password-42!"
        user = user_factory(password=password)
        client = APIClient()
        client.force_authenticate(user)
        for _ in range(10):
            response = client.post(
                "/api/sso/passkeys/reauthenticate/verify",
                {"action": "otp_setup", "password": "wrong"},
                format="json",
            )
            assert response.status_code != 200
        response = client.post(
            "/api/sso/passkeys/reauthenticate/verify",
            {"action": "otp_setup", "password": password},
            format="json",
        )
        assert response.status_code != 200
        assert response.data.get("code") == "password_locked"
