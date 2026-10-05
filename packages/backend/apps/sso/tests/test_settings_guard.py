"""
The DNS verification bypass must never be enabled outside DEBUG. Settings load once per process, so each case
runs a fresh interpreter that imports the settings module.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Shared fixtures in this suite touch the database, so the marker applies to every test in the module
pytestmark = pytest.mark.django_db

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _import_settings(**env_overrides):
    env = {**os.environ, "SSO_DOMAIN_VERIFICATION_SKIP_DNS": "true", "DJANGO_DEBUG": "false", **env_overrides}
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        env=env,
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_bypass_refuses_to_load_outside_debug():
    result = _import_settings()

    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert "SSO_DOMAIN_VERIFICATION_SKIP_DNS" in result.stderr


def test_bypass_loads_in_debug():
    result = _import_settings(DJANGO_DEBUG="true")

    assert result.returncode == 0, result.stderr
