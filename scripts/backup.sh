#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=~/reliability-platform/backups
mkdir -p $BACKUP_DIR

docker compose exec _T postgres pg_dump -U urluser urldb \
  > $BACKUP_DIR/urldb_$TIMESTAMP.sql

ls -t $BACKUP_DIR/*.sql | tail -n +8 | xargs -r rm

echo "Backup complete: $BACKUP_DIR/urldb_$TIMESTAMP.sql"
echo "Size: $(du -h $BACKUP_DIR/urldb_$TIMESTAMP.sql | cut -f1)
