#!/usr/bin/env bash
set -Eeuo pipefail
PATH=/www/server/panel/pyenv/bin:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
export PATH

PLUGIN_DIR=${CERTHUB_PLUGIN_DIR:-/www/server/panel/plugin/certhub}
DATA_DIR=${CERTHUB_DATA_DIR:-/www/server/certhub}
HOOK_FILE=${CERTHUB_HOOK_FILE:-/www/server/panel/hooks/certhub_route.py}
PANEL_ICON=${CERTHUB_PANEL_ICON:-/www/server/panel/BTPanel/static/images/soft_ico/ico-certhub.png}
PANEL_ICON_LEGACY=${CERTHUB_PANEL_ICON_LEGACY:-/www/server/panel/BTPanel/static/img/soft_ico/ico-certhub.png}
BT_PYTHON=${CERTHUB_PYTHON:-/www/server/panel/pyenv/bin/python3}

install_certhub() {
    [[ -x "$BT_PYTHON" ]] || { echo 'ERROR: 找不到宝塔 Python 运行环境。' >&2; exit 1; }
    command -v openssl >/dev/null || { echo 'ERROR: 缺少 OpenSSL。' >&2; exit 1; }
    find "$PLUGIN_DIR" -type d -exec chmod 0755 {} +
    find "$PLUGIN_DIR" -type f -exec chmod 0644 {} +
    chmod 0755 "$PLUGIN_DIR/install.sh" "$PLUGIN_DIR/update.sh" "$PLUGIN_DIR/uninstall.sh" "$PLUGIN_DIR/bin/build-package.sh" "$PLUGIN_DIR/client/linux/install.sh" "$PLUGIN_DIR/client/linux/agent"
    install -d -m 0700 -o root -g root "$DATA_DIR"
    CERTHUB_DATA_DIR="$DATA_DIR" PYTHONPATH="$PLUGIN_DIR" "$BT_PYTHON" -c 'from core import initialize; initialize()'
    install -d -m 0700 -o root -g root "$(dirname "$HOOK_FILE")"
    install -m 0600 -o root -g root "$PLUGIN_DIR/route_hook.py" "$HOOK_FILE"
    install -d -m 0755 -o root -g root "$(dirname "$PANEL_ICON")"
    install -m 0755 -o root -g root "$PLUGIN_DIR/icon-panel.png" "$PANEL_ICON"
    install -d -m 0755 -o root -g root "$(dirname "$PANEL_ICON_LEGACY")"
    install -m 0755 -o root -g root "$PLUGIN_DIR/icon-panel.png" "$PANEL_ICON_LEGACY"
    chmod 0600 "$DATA_DIR/certhub.db"
    if [[ "${CERTHUB_SKIP_RESTART:-0}" != "1" ]]; then
        nohup bash -c 'sleep 3; /etc/init.d/bt restart' >/dev/null 2>&1 &
    fi
    echo 'CertHub 1.0.0 安装完成。面板将在数秒后重启并注册 /certhub-api。'
}

uninstall_certhub() {
    if [[ -f "$HOOK_FILE" ]] && cmp -s "$HOOK_FILE" "$PLUGIN_DIR/route_hook.py"; then
        gio trash "$HOOK_FILE" 2>/dev/null || mv "$HOOK_FILE" "$DATA_DIR/certhub_route.py.removed"
    fi
    if [[ "${CERTHUB_PURGE_DATA:-0}" == "1" ]]; then
        gio trash "$DATA_DIR" 2>/dev/null || true
    fi
    if [[ "${CERTHUB_SKIP_RESTART:-0}" != "1" ]]; then
        nohup bash -c 'sleep 3; /etc/init.d/bt restart' >/dev/null 2>&1 &
    fi
    echo "CertHub 已卸载，SQLite 数据默认保留在 $DATA_DIR。"
}

case "${1:-install}" in
    install|update) install_certhub ;;
    uninstall) uninstall_certhub ;;
    *) echo "Usage: $0 {install|update|uninstall}" >&2; exit 2 ;;
esac
