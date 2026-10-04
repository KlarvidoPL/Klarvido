#!/bin/bash
# Encrypts .env (Django secret key, Postgres password, AWS creds, BACKUP_MASTER_KEY,
# Stripe/OAuth secrets, ...) and uploads it to S3.
#
# .env lives ONLY on the VPS disk and is never committed - if the VPS dies, this file
# dies with it, taking down the ability to decrypt/use the Postgres and per-tenant
# backups this same S3 setup produces. This script is the recovery path for THAT file.
#
# One-time setup on the VPS (run once, by hand):
#   openssl rand -base64 48 > /opt/klarvido/.env-backup-key
#   chmod 600 /opt/klarvido/.env-backup-key
#   Then copy that passphrase into your password manager - it is the ONLY way to
#   decrypt the backup if the VPS itself is lost, so it must live somewhere else too.
#
# Run from the deploy directory, e.g. via VPS crontab (daily, right after the DB backup):
#   0 3 * * * cd /opt/klarvido && ./scripts/backup-postgres-to-s3.sh >> /var/log/klarvido-backup.log 2>&1
#   15 3 * * * cd /opt/klarvido && ./scripts/backup-env-to-s3.sh >> /var/log/klarvido-backup.log 2>&1
#
# Requires in .env: BACKUP_S3_BUCKET, BACKUP_AWS_ACCESS_KEY_ID, BACKUP_AWS_SECRET_ACCESS_KEY,
# AWS_DEFAULT_REGION (the backup IAM user, which can write and read backups but not delete). Requires /opt/klarvido/.env-backup-key (see setup above).
#
# To restore after a VPS loss (on the new VPS, before starting containers):
#   aws s3 cp s3://<bucket>/env-backups/<timestamp>.env.enc ./env-backup.enc
#   openssl enc -d -aes-256-cbc -pbkdf2 -in env-backup.enc -out .env -pass pass:'<passphrase from password manager>'
set -euo pipefail

ENV_FILE=".env"
KEY_FILE=".env-backup-key"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ENC_FILE="/tmp/klarvido-env-backup-${TIMESTAMP}.enc"

set -a
source "$ENV_FILE"
set +a

: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET must be set in $ENV_FILE}"
: "${BACKUP_AWS_ACCESS_KEY_ID:?BACKUP_AWS_ACCESS_KEY_ID must be set in $ENV_FILE}"
: "${BACKUP_AWS_SECRET_ACCESS_KEY:?BACKUP_AWS_SECRET_ACCESS_KEY must be set in $ENV_FILE}"
: "${AWS_DEFAULT_REGION:?AWS_DEFAULT_REGION must be set in $ENV_FILE}"

# Backups use their own scoped AWS key (klarvido-backup: put and get, no delete), never the app key
export AWS_ACCESS_KEY_ID="$BACKUP_AWS_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$BACKUP_AWS_SECRET_ACCESS_KEY"

if [ ! -f "$KEY_FILE" ]; then
  echo "Missing $KEY_FILE - run: openssl rand -base64 48 > $KEY_FILE && chmod 600 $KEY_FILE" >&2
  echo "Then save that passphrase in a password manager - it's the only offsite copy." >&2
  exit 1
fi

cleanup() { rm -f "$ENC_FILE"; }
trap cleanup EXIT

echo "[$(date)] Encrypting $ENV_FILE..."
openssl enc -aes-256-cbc -pbkdf2 -salt -in "$ENV_FILE" -out "$ENC_FILE" -pass "file:$KEY_FILE"

echo "[$(date)] Uploading to s3://${BACKUP_S3_BUCKET}/env-backups/${TIMESTAMP}.env.enc..."
docker run --rm \
  -v "${ENC_FILE}:/backup.enc:ro" \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_DEFAULT_REGION \
  amazon/aws-cli s3 cp /backup.enc "s3://${BACKUP_S3_BUCKET}/env-backups/${TIMESTAMP}.env.enc"

echo "[$(date)] .env backup complete."
