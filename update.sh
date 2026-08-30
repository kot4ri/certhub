#!/usr/bin/env bash
set -Eeuo pipefail

PLUGIN_DIR='/www/server/panel/plugin/certhub'
UPDATE_ROOT='/www/server/certhub/updates'
UPDATE_LOG='/www/server/certhub/update.log'

install -d -m 0700 "$UPDATE_ROOT"
touch "$UPDATE_LOG"
chmod 0600 "$UPDATE_LOG"
exec >>"$UPDATE_LOG" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] updater started: ${1:-update}"

if [[ "${1:-}" != 'apply' ]]; then
    exec "$PLUGIN_DIR/install.sh" update
fi

STAGE="${2:-}"
[[ "$STAGE" =~ ^/www/server/certhub/updates/certhub-[A-Za-z0-9._-]+$ ]] || { echo 'ERROR: 更新暂存目录无效。' >&2; exit 1; }
SOURCE="$STAGE/extracted/certhub"
[[ -f "$SOURCE/info.json" && -f "$SOURCE/install.sh" ]] || { echo 'ERROR: 更新包内容不完整。' >&2; exit 1; }
cleanup() { find "$STAGE" -depth -delete 2>/dev/null || true; }
trap cleanup EXIT
chmod 0755 "$SOURCE/install.sh"

sleep 2
cp -a "$SOURCE/." "$PLUGIN_DIR/"
CERTHUB_SKIP_RESTART=0 "$PLUGIN_DIR/install.sh" update
echo "[$(date '+%Y-%m-%d %H:%M:%S')] update completed"
