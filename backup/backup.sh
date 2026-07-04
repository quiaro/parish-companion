#!/bin/sh
set -eu

WEEKDAY=$(date +%A | tr 'A-Z' 'a-z')
DUMP_PATH="/tmp/backup-$WEEKDAY.sql"
PLAIN_DATABASE_URL=$(echo "$DATABASE_URL" | sed 's#postgresql+psycopg://#postgresql://#')

echo "[backup] starting dump for $WEEKDAY"
pg_dump "$PLAIN_DATABASE_URL" > "$DUMP_PATH"

echo "[backup] uploading to s3://$BACKUP_S3_BUCKET/backup-$WEEKDAY.sql"
aws s3 cp "$DUMP_PATH" "s3://$BACKUP_S3_BUCKET/backup-$WEEKDAY.sql"

rm -f "$DUMP_PATH"
echo "[backup] done"
