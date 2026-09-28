#!/bin/bash
set -e

TRACE_DISABLE="TRACING_BACKEND=none AWS_XRAY_SDK_ENABLED=false"
if [ -n "${CHAMBER_SERVICE_NAME:-}" ]; then
  RUN_CMD="/bin/chamber exec $CHAMBER_SERVICE_NAME -- env $TRACE_DISABLE ./manage.py"
else
  RUN_CMD="env $TRACE_DISABLE uv run python manage.py"
fi

echo "Running database migrations..."
$RUN_CMD migrate --noinput

echo "Initializing subscriptions..."
$RUN_CMD init_subscriptions || echo "init_subscriptions skipped (may require Stripe configuration)"

echo "Initializing customer plans..."
$RUN_CMD init_customers_plans || echo "init_customers_plans skipped (may require Stripe configuration)"

echo "Initializing locales..."
$RUN_CMD init_locales || echo "init_locales skipped"

TRANSLATIONS_MASTER_FILE="/app/translations/master.json"
if [ -f "$TRANSLATIONS_MASTER_FILE" ]; then
  echo "Syncing translation keys from $TRANSLATIONS_MASTER_FILE..."
  $RUN_CMD sync_translations "$TRANSLATIONS_MASTER_FILE" || echo "sync_translations skipped"
else
  echo "Translations master file not found at $TRANSLATIONS_MASTER_FILE, skipping sync"
fi

TRANSLATIONS_EXPORT_FILE="/app/translations/translations_export.json"
if [ -f "$TRANSLATIONS_EXPORT_FILE" ]; then
  echo "Importing translations from $TRANSLATIONS_EXPORT_FILE..."
  $RUN_CMD import_translations "$TRANSLATIONS_EXPORT_FILE" || echo "import_translations skipped"

  # Import only updates the DB (Translation rows) - the served bundle (S3/CDN, or
  # this same container's own endpoint) is a separate artifact that publish writes
  # out, so without this step every deploy would need a manual publish_translations
  # run afterward or newly-imported strings just wouldn't be visible yet.
  echo "Publishing translations..."
  $RUN_CMD publish_translations --all || echo "publish_translations skipped"
else
  echo "Translations export file not found at $TRANSLATIONS_EXPORT_FILE, skipping import"
fi

echo "Migrations complete."
