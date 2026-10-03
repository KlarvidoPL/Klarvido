"""
Django app configuration for the KSeF (Krajowy System e-Faktur) integration.
"""

from django.apps import AppConfig


class KsefConfig(AppConfig):
    """App configuration for the KSeF integration."""

    name = 'apps.ksef'
    verbose_name = 'KSeF'
