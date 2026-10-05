"""
Pytest configuration for SSO tests.

All fixtures are now registered via pytest_factoryboy in fixtures.py
and included via the main conftest.py pytest_plugins list.
"""

import pytest

# Fixtures are auto-discovered from fixtures.py via pytest_plugins in main conftest


@pytest.fixture(autouse=True)
def sso_switched_on_for_tests(settings):
    """SSO is switched off by default (apps/sso/availability.py). The SSO tests exercise it, so they switch it on.
    tests/test_sso_switch.py switches it off again for the cases that check the switch itself."""
    settings.SSO_CONFIGURATION_ENABLED = True
