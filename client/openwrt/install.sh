#!/bin/sh
# Bootstrap with BusyBox ash: bash is installed before running the agent.
set -eu
umask 077
API_ENDPOINT='@@API_ENDPOINT@@'
ENROLLMENT_TOKEN='@@ENROLLMENT_TOKEN@@'
export API_ENDPOINT ENROLLMENT_TOKEN
[ "$(id -u)" -eq 0 ] || { echo '请使用 root 执行安装器。' >&2; exit 1; }
[ -f /etc/openwrt_release ] && [ -f /etc/rc.common ] || { echo '需要 OpenWrt/procd 环境。' >&2; exit 1; }
case "$API_ENDPOINT" in https://*\?*|*\#*) exit 1;; https://*) ;; *) echo '面板地址必须使用 HTTPS。' >&2; exit 1;; esac
if command -v opkg >/dev/null 2>&1; then
  opkg update
  opkg install bash curl ca-bundle flock python3-light python3-openssl openssl-util
elif command -v apk >/dev/null 2>&1; then
  apk update
  apk add bash curl ca-bundle flock python3-light python3-openssl openssl-util
else
  echo '需要 opkg 或 apk 包管理器。' >&2; exit 1
fi
for name in bash curl flock openssl python3; do
  command -v "$name" >/dev/null 2>&1 || { echo "缺少依赖：$name" >&2; exit 1; }
done
python3 -c 'import json,platform,hashlib,datetime,ssl,subprocess,shutil; assert hasattr(ssl._ssl,"_test_decode_cert")'
mkdir -p /usr/local/sbin /etc/certhub-agent/state /var/lock
chmod 700 /etc/certhub-agent /etc/certhub-agent/state
work=$(mktemp -d /tmp/certhub-install.XXXXXX)
trap 'rm -rf "$work"; unset ENROLLMENT_TOKEN' EXIT
fetch() {
  curl --connect-timeout 10 --max-time 120 --fail --silent --show-error --proto '=https' --tlsv1.2 "$@" ||
  curl -4 --connect-timeout 10 --max-time 120 --fail --silent --show-error --proto '=https' --tlsv1.2 "$@"
}
# Download and check all artifacts before changing the installed service.
fetch "$API_ENDPOINT?action=client_openwrt" -o "$work/agent"
fetch "$API_ENDPOINT?action=client_openwrt_service" -o "$work/service"
bash -n "$work/agent"
sh -n "$work/service"
if [ ! -s /etc/certhub-agent/config.json ]; then
  python3 - "$work/request.json" <<'PY'
import json,os,platform,sys
info={'hostname':platform.node(),'os_name':'OpenWrt','os_version':platform.platform(),'architecture':platform.machine(),'agent_version':'0.3.20'}
try:
 for line in open('/etc/os-release'):
  if line.startswith('PRETTY_NAME='):info['os_version']=line.split('=',1)[1].strip().strip('"');break
except OSError:pass
with open(sys.argv[1],'w') as f:json.dump({'token':os.environ['ENROLLMENT_TOKEN'],'system':info},f)
PY
  fetch -H 'Content-Type: application/json' --data-binary "@$work/request.json" "$API_ENDPOINT?action=enroll" -o "$work/enroll.json"
  python3 - "$work/enroll.json" /etc/certhub-agent/config.json <<'PY'
import json,os,sys
r=json.load(open(sys.argv[1]));d=r.get('data') or {}
if not r.get('status') or not all(d.get(k) for k in ('api_endpoint','client_id','auth_token')):raise SystemExit(r.get('error','注册失败'))
if d.get('platform')!='openwrt':raise SystemExit('安装凭据的平台不是 OpenWRT')
p=sys.argv[2]+'.new'
with open(p,'w') as f:json.dump({k:d[k] for k in ('api_endpoint','client_id','auth_token')},f,separators=(',',':'))
os.chmod(p,0o600);os.replace(p,sys.argv[2])
PY
else
  # Reinstallation keeps the existing identity; never consume another token.
  python3 - <<'PY'
import json,os
c=json.load(open('/etc/certhub-agent/config.json'))
if c.get('api_endpoint')!=os.environ['API_ENDPOINT'] or not all(c.get(k) for k in ('client_id','auth_token')):
 raise SystemExit('已有注册配置与面板地址不一致或配置损坏，请先检查 /etc/certhub-agent/config.json')
PY
fi
unset ENROLLMENT_TOKEN
if [ -f /etc/init.d/certhub-agent ]; then /etc/init.d/certhub-agent stop; fi
if [ -f /usr/local/sbin/certhub-agent ]; then cp -p /usr/local/sbin/certhub-agent /usr/local/sbin/certhub-agent.previous; fi
cp "$work/agent" /usr/local/sbin/.certhub-agent.new
chmod 755 /usr/local/sbin/.certhub-agent.new
mv /usr/local/sbin/.certhub-agent.new /usr/local/sbin/certhub-agent
cp "$work/service" /etc/init.d/certhub-agent
chmod 755 /etc/init.d/certhub-agent
/etc/init.d/certhub-agent enable
# Leave the daemon enabled even if initial synchronization needs a network retry.
if ! /usr/local/sbin/certhub-agent sync; then echo '首次同步失败，后台服务将继续重试。' >&2; fi
/etc/init.d/certhub-agent start
/etc/init.d/certhub-agent status
echo 'CertHub OpenWRT Agent 0.3.20 安装完成。'
echo '持久化证书：/etc/certhub-agent/state/certificates/<id>/current/'
