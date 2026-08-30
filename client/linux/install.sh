#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
API_ENDPOINT='@@API_ENDPOINT@@'
ENROLLMENT_TOKEN='@@ENROLLMENT_TOKEN@@'
INSTALL_BIN=/usr/local/sbin/certhub-agent
CONFIG_DIR=/etc/certhub-agent
STATE_DIR=/var/lib/certhub-agent

[[ $EUID -eq 0 ]] || { echo '请使用 root 执行安装器。' >&2; exit 1; }

install_python3() {
  command -v python3 >/dev/null && return 0
  echo '未检测到 python3，正在安装运行依赖。' >&2
  if command -v dnf >/dev/null; then
    dnf install -y python3
  elif command -v yum >/dev/null; then
    yum install -y python3
  elif command -v apt-get >/dev/null; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3
  else
    echo '未找到受支持的包管理器（dnf、yum 或 apt-get）。' >&2
    return 1
  fi
  command -v python3 >/dev/null || { echo 'python3 安装完成后仍不可用。' >&2; return 1; }
}

install_python3
for command_name in curl openssl flock; do command -v "$command_name" >/dev/null || { echo "缺少 $command_name。" >&2; exit 1; }; done
[[ $API_ENDPOINT == https://* ]] || { echo '面板地址必须使用 HTTPS。' >&2; exit 1; }
install -d -m 0700 "$CONFIG_DIR" "$STATE_DIR" "$STATE_DIR/certificates"

curl_with_ipv4_fallback() {
  curl "$@" || {
    echo 'IPv6/默认网络请求失败，正在回落到 IPv4 重试。' >&2
    curl -4 "$@"
  }
}

system_file=$(mktemp "$CONFIG_DIR/.system.XXXXXX")
python3 - "$system_file" <<'PY'
import json,os,platform,sys
info={'hostname':platform.node(),'os_name':platform.system(),'os_version':platform.platform(),'architecture':platform.machine(),'agent_version':'0.3.13'}
try:
 for line in open('/etc/os-release'):
  if line.startswith('PRETTY_NAME='): info['os_version']=line.split('=',1)[1].strip().strip('"'); break
except OSError: pass
json.dump(info,open(sys.argv[1],'w'),separators=(',',':'))
PY
enroll_file=$(mktemp "$CONFIG_DIR/.enroll.XXXXXX")
python3 - "$system_file" "$ENROLLMENT_TOKEN" > "$CONFIG_DIR/.request.json" <<'PY'
import json,sys
print(json.dumps({'token':sys.argv[2],'system':json.load(open(sys.argv[1]))},separators=(',',':')))
PY
curl_with_ipv4_fallback --fail --silent --show-error --proto '=https' --tlsv1.2 -H 'Content-Type: application/json' --data-binary "@$CONFIG_DIR/.request.json" "$API_ENDPOINT?action=enroll" -o "$enroll_file"
python3 - "$enroll_file" "$CONFIG_DIR/config.json" <<'PY'
import json,os,sys
r=json.load(open(sys.argv[1])); d=r.get('data') or {}
if not r.get('status') or not d.get('client_id') or not d.get('auth_token'): raise SystemExit(r.get('error','注册失败'))
json.dump({'api_endpoint':d['api_endpoint'],'client_id':d['client_id'],'auth_token':d['auth_token']},open(sys.argv[2],'w'),separators=(',',':'))
os.chmod(sys.argv[2],0o600)
PY
agent_file=$(mktemp "$STATE_DIR/.agent.XXXXXX")
service_file=$(mktemp "$STATE_DIR/.service.XXXXXX")
curl_with_ipv4_fallback --fail --silent --show-error --proto '=https' --tlsv1.2 "$API_ENDPOINT?action=client_linux" -o "$agent_file"
curl_with_ipv4_fallback --fail --silent --show-error --proto '=https' --tlsv1.2 "$API_ENDPOINT?action=client_linux_service" -o "$service_file"
install -m 0755 "$agent_file" "$INSTALL_BIN"
find "$CONFIG_DIR" -maxdepth 1 -type f -name '.*' -delete
unset ENROLLMENT_TOKEN
if command -v systemctl >/dev/null; then
  systemctl stop certhub-agent.service 2>/dev/null || true
  install -m 0644 "$service_file" /etc/systemd/system/certhub-agent.service
  systemctl disable --now certhub-agent.timer 2>/dev/null || true
  rm -f /etc/systemd/system/certhub-agent.timer /etc/cron.d/certhub-agent
  systemctl daemon-reload
  systemctl enable --now certhub-agent.service
  if [[ -d /opt/certhub-agent ]]; then
    legacy="$STATE_DIR/legacy-opt-install"
    [[ -e $legacy ]] || mv /opt/certhub-agent "$legacy"
  fi
else
  echo '系统不支持 systemd，无法运行 CertHub 常驻同步服务。' >&2
  exit 1
fi
rm -f "$agent_file" "$service_file"
echo 'CertHub Agent 0.3.13 安装完成。'
