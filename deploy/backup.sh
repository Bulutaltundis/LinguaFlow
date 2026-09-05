#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/var/www/linguaflow"
BACKUP_DIR="/var/backups/linguaflow"
mkdir -p "$BACKUP_DIR"
sqlite3 "$APP_DIR/linguaflow.db" ".backup '$BACKUP_DIR/linguaflow-$(date +%Y-%m-%d).db'"
find "$BACKUP_DIR" -type f -name 'linguaflow-*.db' -mtime +14 -delete
