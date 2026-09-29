from django.core.management.base import BaseCommand, CommandError

from apps.klarvido.adapters import MockDataAdapter
from apps.klarvido.services import import_from_adapter
from apps.multitenancy.models import Tenant


class Command(BaseCommand):
    help = "Load the versioned Klarvido demonstration dataset for an existing tenant."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-slug", required=True, help="Slug of the tenant that will own the demo data.")

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options["tenant_slug"])
        except Tenant.DoesNotExist as error:
            raise CommandError(f'Tenant "{options["tenant_slug"]}" does not exist.') from error

        summary = import_from_adapter(tenant=tenant, adapter=MockDataAdapter())
        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded Klarvido demo for {tenant.slug}: "
                f"{summary.invoices} invoices, {summary.counterparties} counterparties, "
                f"{summary.source_records} source records."
            )
        )
