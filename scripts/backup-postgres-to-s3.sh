#!/bin/bash
# Dumps the production Postgres database and uploads it to S3.
#
# Run from the deploy directory (where docker-compose.yml + .env live on the VPS -
# deploy-vps.yml renames docker-compose.prod.yml to docker-compose.yml on upload),
# e.g. via VPS crontab:
#   0 3 * * * cd /opt/klarvido && ./scripts/backup-postgres-to-s3.sh >> /var/log/klarvido-backup.log 2>&1
#
# Requires in .env: POSTGRES_PASSWORD, BACKUP_S3_BUCKET, AWS_ACCESS_KEY_ID,
# AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION. Retention is handled by an S3 lifecycle
# rule on the bucket, not by this script.
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="/tmp/klarvido-backup-${TIMESTAMP}.sql.gz"

set -a
source "$ENV_FILE"
set +a

: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET must be set in $ENV_FILE}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID must be set in $ENV_FILE}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY must be set in $ENV_FILE}"
: "${AWS_DEFAULT_REGION:?AWS_DEFAULT_REGION must be set in $ENV_FILE}"

cleanup() { rm -f "$DUMP_FILE"; }
trap cleanup EXIT

echo "[$(date)] Dumping Postgres database..."
docker compose -f "$COMPOSE_FILE" exec -T db pg_dump -U backend backend | gzip > "$DUMP_FILE"

echo "[$(date)] Uploading to s3://${BACKUP_S3_BUCKET}/postgres/${TIMESTAMP}.sql.gz..."
docker run --rm \
  -v "${DUMP_FILE}:/backup.sql.gz:ro" \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_DEFAULT_REGION \
  amazon/aws-cli s3 cp /backup.sql.gz "s3://${BACKUP_S3_BUCKET}/postgres/${TIMESTAMP}.sql.gz"

echo "[$(date)] Backup complete."
