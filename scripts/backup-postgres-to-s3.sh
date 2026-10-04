#!/bin/bash
# Dumps the production Postgres database, encrypts it and uploads it to S3.
#
# The dump is encrypted before it leaves the VPS (AES-256-CBC, PBKDF2) with the same passphrase file as the .env
# backup (/opt/klarvido/.env-backup-key). The bucket only ever holds ciphertext, and the plaintext dump never touches
# disk. Without the passphrase the files are useless, which also covers the encrypted KSeF tokens they contain.
#
# Run from the deploy directory (where docker-compose.yml + .env live on the VPS -
# deploy-vps.yml renames docker-compose.prod.yml to docker-compose.yml on upload),
# e.g. via VPS crontab:
#   0 3 * * * cd /opt/klarvido && ./scripts/backup-postgres-to-s3.sh >> /var/log/klarvido-backup.log 2>&1
#
# Requires in .env: POSTGRES_PASSWORD, BACKUP_S3_BUCKET, BACKUP_AWS_ACCESS_KEY_ID,
# BACKUP_AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION (the backup IAM user, which can write and read backups but not delete). Requires /opt/klarvido/.env-backup-key (see
# backup-env-to-s3.sh for how to create it). Retention is handled by an S3 lifecycle
# rule on the bucket, not by this script.
#
# To restore (on a new or repaired database, with the passphrase from your password manager):
#   aws s3 cp s3://<bucket>/postgres/<timestamp>.sql.gz.enc ./dump.sql.gz.enc
#   openssl enc -d -aes-256-cbc -pbkdf2 -in dump.sql.gz.enc -pass file:.env-backup-key | gunzip | \
#     docker compose exec -T db psql -U backend backend
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
KEY_FILE=".env-backup-key"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ENC_FILE="/tmp/klarvido-backup-${TIMESTAMP}.sql.gz.enc"

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
  echo "Missing $KEY_FILE - see backup-env-to-s3.sh for how to create it." >&2
  exit 1
fi

cleanup() { rm -f "$ENC_FILE"; }
trap cleanup EXIT

echo "[$(date)] Dumping and encrypting Postgres database..."
docker compose -f "$COMPOSE_FILE" exec -T db pg_dump -U backend backend \
  | gzip \
  | openssl enc -aes-256-cbc -pbkdf2 -salt -pass "file:$KEY_FILE" -out "$ENC_FILE"

echo "[$(date)] Uploading to s3://${BACKUP_S3_BUCKET}/postgres/${TIMESTAMP}.sql.gz.enc..."
docker run --rm \
  -v "${ENC_FILE}:/backup.sql.gz.enc:ro" \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_DEFAULT_REGION \
  amazon/aws-cli s3 cp /backup.sql.gz.enc "s3://${BACKUP_S3_BUCKET}/postgres/${TIMESTAMP}.sql.gz.enc"

echo "[$(date)] Backup complete."
