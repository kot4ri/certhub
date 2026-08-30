# coding: utf-8
from __future__ import absolute_import

import json
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.parse
import zipfile

PANEL_DIR = '/www/server/panel'
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if PANEL_DIR + '/class' not in sys.path:
    sys.path.insert(0, PANEL_DIR + '/class')
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

import public
from core import CertificateScanner, CertHubError, ClientService, connect, initialize, save_setting, setting, utcnow, audit, validate_cron


class certhub_main(object):
    RELEASE_API = 'https://api.github.com/repos/kot4ri/certhub/releases/latest'
    UPDATE_ROOT = '/www/server/certhub/updates'
    def __init__(self):
        initialize()

    @staticmethod
    def ok(data=None, msg='操作成功'):
        return {'status': True, 'msg': msg, 'data': data}

    @staticmethod
    def value(get, name, default=None):
        value = getattr(get, name, default)
        return default if value is None else value

    @staticmethod
    def validate_panel_url(value):
        url = str(value or '').strip().rstrip('/')
        try:
            parsed = urllib.parse.urlsplit(url)
            valid = (parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and
                     not parsed.password and not parsed.query and not parsed.fragment)
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                valid = False
        except (TypeError, ValueError):
            valid = False
        if not valid or len(url) > 512 or any(char in url for char in "'\"\\\r\n\t"):
            raise CertHubError('宝塔面板公开地址必须是安全的 HTTPS 地址')
        return url

    def guard(self, callback):
        try:
            return callback()
        except Exception as exc:
            return {'status': False, 'msg': str(exc)}

    def dashboard(self, get):
        def run():
            with connect() as db:
                data = {
                    'certificates': db.execute('SELECT COUNT(*) FROM certificates').fetchone()[0],
                    'clients': db.execute("SELECT COUNT(*) FROM clients WHERE status!='revoked'").fetchone()[0],
                    'online_24h': db.execute("SELECT COUNT(*) FROM clients WHERE last_seen_at>=?", (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 86400)),)).fetchone()[0],
                    'pulls_24h': db.execute("SELECT COUNT(*) FROM pull_events WHERE created_at>=?", (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 86400)),)).fetchone()[0],
                    'panel_base_url': setting('panel_base_url'),
                    'pull_retention_days': int(setting('pull_retention_days', '30') or 30),
                    'default_sync_schedule': setting('default_sync_schedule', '0 * * * *') or '0 * * * *',
                    'onboarding_completed': setting('onboarding_completed', '0') == '1',
                    'api_path': '/certhub-api',
                    'database_path': os.path.join(os.environ.get('CERTHUB_DATA_DIR', '/www/server/certhub'), 'certhub.db')
                }
            return self.ok(data)
        return self.guard(run)

    def discover_local(self, get):
        return self.guard(lambda: self.ok(CertificateScanner().discover()))

    def complete_onboarding(self, get):
        def run():
            certificates = CertificateScanner().discover()
            if not any(not item.get('error') for item in certificates):
                raise CertHubError('未检测到宝塔面板中已签发的有效证书')
            with connect() as db:
                if db.execute('SELECT COUNT(*) FROM certificates').fetchone()[0] < 1:
                    raise CertHubError('请先纳管至少一张证书')
                if db.execute('SELECT COUNT(*) FROM clients').fetchone()[0] < 1:
                    raise CertHubError('请先添加至少一个下发服务')
            save_setting('onboarding_completed', '1')
            audit('onboarding.complete', 'setting', 'onboarding_completed')
            return self.ok(None, '初始化检查已完成')
        return self.guard(run)

    def skip_onboarding(self, get):
        def run():
            save_setting('onboarding_completed', '1')
            audit('onboarding.skip', 'setting', 'onboarding_completed')
            return self.ok(None, '已跳过首次使用引导')
        return self.guard(run)

    def import_local(self, get):
        return self.guard(lambda: self.ok(CertificateScanner().import_local(self.value(get, 'path', ''), self.value(get, 'name', '')), '证书已纳管'))

    def sync_now(self, get):
        def run():
            result = {'checked': 0, 'failed': 0}
            with connect() as db:
                ids = [row[0] for row in db.execute('SELECT id FROM certificates WHERE auto_sync=1')]
            scanner = CertificateScanner()
            for certificate_id in ids:
                try:
                    scanner.refresh(certificate_id); result['checked'] += 1
                except Exception:
                    result['failed'] += 1
            return self.ok(result, '检查完成')
        return self.guard(run)

    def certificates(self, get):
        def run():
            with connect() as db:
                rows = [dict(row) for row in db.execute('SELECT * FROM certificates ORDER BY name')]
            scanner = CertificateScanner()
            for row in rows:
                row['sans'] = json.loads(row.pop('sans_json'))
                try:
                    files = scanner.locate(scanner.assert_allowed(row['source_path']))
                    info = scanner.inspect(files[0], files[1]) if files else {}
                    row['issuer_brand'] = info.get('issuer_brand', '未知')
                    row['validation_type'] = info.get('validation_type', '未知')
                except Exception:
                    row['issuer_brand'] = '未知'
                    row['validation_type'] = '未知'
            return self.ok(rows)
        return self.guard(run)

    def remove_certificate(self, get):
        def run():
            certificate_id = int(self.value(get, 'id', 0))
            with connect() as db:
                db.execute('DELETE FROM certificates WHERE id=?', (certificate_id,))
            audit('certificate.remove', 'certificate', certificate_id)
            return self.ok(None, '已取消纳管；源证书未被删除')
        return self.guard(run)

    def clients(self, get):
        def run():
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'info.json'), 'r', encoding='utf-8') as handle:
                version_info = json.load(handle)
            base_url = setting('panel_base_url').rstrip('/') + '/certhub-api'
            packages = {}
            for platform_name, relative, action in (
                    ('windows', 'client/windows/certhub-agent.exe', 'client_windows_binary'),
                    ('linux', 'client/linux/agent', 'client_linux')):
                path = os.path.join(PLUGIN_DIR, *relative.split('/'))
                with open(path, 'rb') as package:
                    digest = hashlib.sha256(package.read()).hexdigest()
                url = base_url + '?action=' + action
                if platform_name == 'windows':
                    command = "$u='%s';$p=\"$env:TEMP\\certhub-agent-update.exe\";$d=\"$env:ProgramData\\CertHub\\certhub-agent.exe\";try{Invoke-WebRequest -UseBasicParsing $u -OutFile $p}catch{& curl.exe -4 -fSL $u -o $p;if($LASTEXITCODE -ne 0){throw}};if((Get-FileHash $p -Algorithm SHA256).Hash -ne '%s'){throw \"文件校验失败\"};schtasks.exe /End /TN \"CertHub Certificate Sync\" 2>$null;Get-Process certhub-agent -ErrorAction SilentlyContinue|Stop-Process -Force;Start-Sleep -Seconds 2;Copy-Item $p $d -Force;Start-Process $d -ArgumentList \"--scheduled\" -Wait;schtasks.exe /Run /TN \"CertHub Certificate Sync\"" % (url.replace("'", "''"), digest.upper())
                else:
                    command = "curl -fsS '%s' -o /tmp/certhub-agent.update && echo '%s  /tmp/certhub-agent.update' | sha256sum -c - && sudo systemctl stop certhub-agent.service && sudo install -m 0755 /tmp/certhub-agent.update /usr/local/sbin/certhub-agent && sudo systemctl start certhub-agent.service" % (url.replace("'", "'\\''"), digest)
                packages[platform_name] = command
            with connect() as db:
                rows = [dict(row) for row in db.execute('''SELECT id,client_uuid,name,platform,status,hostname,os_name,os_version,architecture,agent_version,last_ip,last_seen_at,created_at,
                                                           allowed_ip,deploy_mode,download_path,auto_deploy_sites,sync_interval_seconds,sync_schedule,config_updated_at,
                                                           force_sync_token,force_sync_requested_at,force_sync_completed_at
                                                           ,update_token,update_requested_at,update_completed_at,update_completed_version
                                                           ,cleanup_token,cleanup_requested_at,cleanup_completed_at,revoke_after_cleanup
                                                           FROM clients ORDER BY id DESC''')]
                for row in rows:
                    row['certificate_ids'] = [item[0] for item in db.execute("SELECT certificate_id FROM grants WHERE client_id=? AND effect='allow' ORDER BY certificate_id", (row['id'],))]
                    row['latest_agent_version'] = str(version_info.get(row['platform'] + '_agent_version') or '')
                    row['manual_update_command'] = packages.get(row['platform'], '')
            return self.ok(rows)
        return self.guard(run)

    def create_client(self, get):
        def run():
            ids = json.loads(self.value(get, 'certificate_ids', '[]'))
            if not isinstance(ids, list):
                raise CertHubError('证书权限参数无效')
            if not setting('panel_base_url').strip():
                panel_url = self.validate_panel_url(self.value(get, 'panel_base_url', ''))
                save_setting('panel_base_url', panel_url)
            options = {key: self.value(get, key, '') for key in ('allowed_ip', 'deploy_mode', 'download_path', 'auto_deploy_sites', 'sync_schedule')}
            if not str(options.get('sync_schedule') or '').strip():
                options['sync_schedule'] = setting('default_sync_schedule', '0 * * * *') or '0 * * * *'
            result = ClientService().create(self.value(get, 'name', ''), self.value(get, 'platform', ''), ids, options)
            return self.ok(result, '唯一安装信息已生成')
        return self.guard(run)

    def update_client(self, get):
        def run():
            ids = json.loads(self.value(get, 'certificate_ids', '[]'))
            if not isinstance(ids, list):
                raise CertHubError('证书权限参数无效')
            options = {key: self.value(get, key, '') for key in ('allowed_ip', 'deploy_mode', 'download_path', 'auto_deploy_sites', 'sync_schedule')}
            ClientService().update(int(self.value(get, 'id', 0)), self.value(get, 'name', ''), ids, options)
            return self.ok(None, '客户端配置已更新')
        return self.guard(run)

    def revoke_client(self, get):
        def run():
            client_id = int(self.value(get, 'id', 0))
            cleanup = str(self.value(get, 'cleanup_certificates', '0')).lower() in ('1', 'true', 'yes')
            with connect() as db:
                row = db.execute('SELECT status FROM clients WHERE id=?', (client_id,)).fetchone()
                if not row:
                    raise CertHubError('客户端不存在')
                if cleanup and row['status'] == 'active':
                    db.execute('UPDATE clients SET cleanup_token=?,cleanup_requested_at=?,cleanup_completed_at=NULL,revoke_after_cleanup=1 WHERE id=?', (os.urandom(24).hex(), utcnow(), client_id))
                else:
                    db.execute("UPDATE clients SET status='revoked',auth_token_hash=NULL,cleanup_token=NULL,revoke_after_cleanup=0,revoked_at=? WHERE id=?", (utcnow(), client_id))
            audit('client.revoke', 'client', client_id)
            return self.ok(None, '清理指令已下发，客户端完成后将自动撤销' if cleanup and row['status'] == 'active' else '客户端已撤销')
        return self.guard(run)

    def delete_client(self, get):
        def run():
            client_id = int(self.value(get, 'id', 0))
            with connect() as db:
                row = db.execute('SELECT id,name FROM clients WHERE id=?', (client_id,)).fetchone()
                if not row:
                    raise CertHubError('客户端不存在')
                db.execute('DELETE FROM clients WHERE id=?', (client_id,))
            audit('client.delete', 'client', client_id, {'name': row['name']})
            return self.ok(None, '客户端及关联数据已彻底删除')
        return self.guard(run)

    def restore_client(self, get):
        def run():
            client_id = int(self.value(get, 'id', 0))
            with connect() as db:
                row = db.execute('SELECT status FROM clients WHERE id=?', (client_id,)).fetchone()
                if not row:
                    raise CertHubError('客户端不存在')
                if row['status'] != 'revoked':
                    raise CertHubError('只能恢复已撤销的客户端')
                db.execute("""UPDATE clients SET status='pending',revoked_at=NULL,auth_token_hash=NULL,
                             cleanup_token=NULL,revoke_after_cleanup=0,force_sync_token=NULL,update_token=NULL
                             WHERE id=?""", (client_id,))
            result = ClientService().reissue_enrollment(client_id)
            audit('client.restore', 'client', client_id)
            return self.ok(result, '恢复凭据已生成，请在原客户端重新安装')
        return self.guard(run)

    def reissue_enrollment(self, get):
        return self.guard(lambda: self.ok(ClientService().reissue_enrollment(int(self.value(get, 'id', 0))), '安装命令已重新生成'))

    def force_sync_clients(self, get):
        def run():
            ids = json.loads(self.value(get, 'client_ids', '[]'))
            if not isinstance(ids, list) or not ids:
                raise CertHubError('请选择需要立即拉取的客户端')
            ids = sorted(set(int(item) for item in ids if int(item) > 0))
            if not ids:
                raise CertHubError('请选择需要立即拉取的客户端')
            placeholders = ','.join('?' for _ in ids)
            token = os.urandom(24).hex(); now = utcnow()
            with connect() as db:
                cursor = db.execute("UPDATE clients SET force_sync_token=?,force_sync_requested_at=?,force_sync_completed_at=NULL WHERE status='active' AND id IN (%s)" % placeholders, [token, now] + ids)
            audit('client.force_sync', 'client', ','.join(map(str, ids)), {'count': cursor.rowcount})
            return self.ok({'requested': cursor.rowcount}, '立即拉取指令已下发')
        return self.guard(run)

    def update_clients(self, get):
        def run():
            ids = json.loads(self.value(get, 'client_ids', '[]'))
            if not isinstance(ids, list) or not ids:
                raise CertHubError('请选择需要更新的客户端')
            ids = sorted(set(int(item) for item in ids if int(item) > 0))
            if not ids:
                raise CertHubError('请选择需要更新的客户端')
            placeholders = ','.join('?' for _ in ids)
            token = os.urandom(24).hex(); now = utcnow()
            with connect() as db:
                cursor = db.execute("UPDATE clients SET update_token=?,update_requested_at=?,update_completed_at=NULL WHERE status='active' AND id IN (%s)" % placeholders, [token, now] + ids)
            audit('client.update_agent', 'client', ','.join(map(str, ids)), {'count': cursor.rowcount})
            return self.ok({'requested': cursor.rowcount}, '客户端更新指令已下发')
        return self.guard(run)

    def save_grant(self, get):
        def run():
            client_id = int(self.value(get, 'client_id', 0)); certificate_id = int(self.value(get, 'certificate_id', 0))
            effect = 'deny' if self.value(get, 'effect', 'allow') == 'deny' else 'allow'
            profile = self.value(get, 'install_profile', 'files-only')
            if profile not in ('files-only', 'bt-nginx', 'nginx', 'apache'):
                raise CertHubError('部署 Profile 无效')
            target_cert = self.value(get, 'target_fullchain', '') or None
            target_key = self.value(get, 'target_private_key', '') or None
            with connect() as db:
                db.execute('''INSERT INTO grants(client_id,certificate_id,effect,install_profile,target_fullchain,target_private_key,updated_at) VALUES(?,?,?,?,?,?,?)
                              ON CONFLICT(client_id,certificate_id) DO UPDATE SET effect=excluded.effect,install_profile=excluded.install_profile,target_fullchain=excluded.target_fullchain,target_private_key=excluded.target_private_key,updated_at=excluded.updated_at''',
                           (client_id, certificate_id, effect, profile, target_cert, target_key, utcnow()))
            audit('grant.save', 'client', client_id, {'certificate_id': certificate_id, 'effect': effect})
            return self.ok()
        return self.guard(run)

    def grants(self, get):
        def run():
            with connect() as db:
                rows = [dict(row) for row in db.execute('SELECT g.*,c.name certificate_name FROM grants g JOIN certificates c ON c.id=g.certificate_id WHERE g.client_id=? ORDER BY c.name', (int(self.value(get, 'client_id', 0)),))]
            return self.ok(rows)
        return self.guard(run)

    def save_settings(self, get):
        def run():
            url = self.validate_panel_url(self.value(get, 'panel_base_url', ''))
            try:
                retention = int(self.value(get, 'pull_retention_days', '30'))
            except (TypeError, ValueError):
                raise CertHubError('拉取记录保存天数无效')
            if retention < 1 or retention > 3650:
                raise CertHubError('拉取记录保存时间必须在 1 到 3650 天之间')
            default_schedule = str(self.value(get, 'default_sync_schedule', '0 * * * *') or '').strip()
            validate_cron(default_schedule)
            save_setting('panel_base_url', url)
            save_setting('pull_retention_days', str(retention))
            save_setting('default_sync_schedule', default_schedule)
            audit('settings.update', 'setting', 'panel_base_url')
            return self.ok({'api_endpoint': url + '/certhub-api'}, '设置已保存')
        return self.guard(run)

    def pull_events(self, get):
        def run():
            try:
                page = max(1, int(self.value(get, 'page', 1)))
            except (TypeError, ValueError):
                page = 1
            page_size = 10
            with connect() as db:
                total = db.execute('SELECT COUNT(*) FROM pull_events').fetchone()[0]
                pages = max(1, (total + page_size - 1) // page_size)
                page = min(page, pages)
                rows = [dict(row) for row in db.execute('''SELECT p.*,c.name client_name,cert.name certificate_name FROM pull_events p
                                                           JOIN clients c ON c.id=p.client_id LEFT JOIN certificates cert ON cert.id=p.certificate_id
                                                           ORDER BY p.id DESC LIMIT ? OFFSET ?''', (page_size, (page - 1) * page_size))]
            return self.ok({'items': rows, 'page': page, 'pages': pages, 'total': total, 'page_size': page_size})
        return self.guard(run)

    def clear_pull_events(self, get):
        def run():
            with connect() as db:
                count = db.execute('SELECT COUNT(*) FROM pull_events').fetchone()[0]
                db.execute('DELETE FROM pull_events')
            audit('pull_events.clear', 'pull_events', None, {'count': count})
            return self.ok({'deleted': count}, '拉取记录已清空')
        return self.guard(run)

    def reset_database(self, get):
        def run():
            with connect() as db:
                db.execute('DELETE FROM pull_events')
                db.execute('DELETE FROM enrollments')
                db.execute('DELETE FROM grants')
                db.execute('DELETE FROM clients')
                db.execute('DELETE FROM certificates')
                db.execute('DELETE FROM audit_logs')
                db.execute('DELETE FROM settings')
                db.execute("DELETE FROM sqlite_sequence WHERE name IN ('certificates','clients','enrollments','grants','pull_events','audit_logs')")
            return self.ok(None, '数据库已完全重置')
        return self.guard(run)

    @staticmethod
    def _version_tuple(value):
        match = re.match(r'^v?(\d+)\.(\d+)\.(\d+)$', str(value or '').strip())
        if not match:
            raise CertHubError('版本号格式无效：%s' % value)
        return tuple(int(part) for part in match.groups())

    def _release_info(self):
        request = urllib.request.Request(
            self.RELEASE_API,
            headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'CertHub-Panel-Updater'}
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read(1024 * 1024).decode('utf-8'))
        except Exception as exc:
            raise CertHubError('无法连接 GitHub 检查更新：%s' % exc)
        latest = str(payload.get('tag_name') or '').lstrip('v')
        self._version_tuple(latest)
        with open(os.path.join(PLUGIN_DIR, 'info.json'), 'r', encoding='utf-8') as handle:
            current = str(json.load(handle).get('versions') or '')
        self._version_tuple(current)
        expected_zip = 'certhub-%s.zip' % latest
        assets = {str(item.get('name')): str(item.get('browser_download_url'))
                  for item in payload.get('assets', []) if item.get('name') and item.get('browser_download_url')}
        return {
            'current_version': current,
            'latest_version': latest,
            'update_available': self._version_tuple(latest) > self._version_tuple(current),
            'release_url': str(payload.get('html_url') or ''),
            'published_at': str(payload.get('published_at') or ''),
            'zip_name': expected_zip,
            'zip_url': assets.get(expected_zip, ''),
            'checksum_url': assets.get(expected_zip + '.sha256', ''),
            'signature_url': assets.get(expected_zip + '.sig', '')
        }

    def check_update(self, get):
        return self.guard(lambda: self.ok(self._release_info(), '更新检查完成'))

    @staticmethod
    def _download(url, target, limit):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or not (
                parsed.hostname in ('github.com', 'api.github.com') or
                parsed.hostname.endswith('.githubusercontent.com')):
            raise CertHubError('更新下载地址不受信任')
        request = urllib.request.Request(url, headers={'User-Agent': 'CertHub-Panel-Updater'})
        with urllib.request.urlopen(request, timeout=45) as response, open(target, 'wb') as output:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != 'https' or not final.hostname or not (
                    final.hostname == 'github.com' or final.hostname.endswith('.githubusercontent.com')):
                raise CertHubError('更新下载重定向地址不受信任')
            total = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > limit:
                    raise CertHubError('更新文件超过允许大小')
                output.write(block)

    def install_update(self, get):
        def run():
            release = self._release_info()
            if not release['update_available']:
                return self.ok(release, '当前已是最新版本')
            if not release['zip_url'] or not release['checksum_url'] or not release['signature_url']:
                raise CertHubError('Release 缺少插件包、校验文件或数字签名')
            os.makedirs(self.UPDATE_ROOT, mode=0o700, exist_ok=True)
            stage = tempfile.mkdtemp(prefix='certhub-', dir=self.UPDATE_ROOT)
            archive = os.path.join(stage, 'package.zip')
            checksum_file = os.path.join(stage, 'package.sha256')
            signature_file = os.path.join(stage, 'package.sig')
            try:
                self._download(release['zip_url'], archive, 100 * 1024 * 1024)
                self._download(release['checksum_url'], checksum_file, 4096)
                self._download(release['signature_url'], signature_file, 16384)
                expected = open(checksum_file, 'r', encoding='utf-8').read().strip().split()[0].lower()
                if not re.match(r'^[0-9a-f]{64}$', expected):
                    raise CertHubError('Release 校验文件格式无效')
                digest = hashlib.sha256()
                with open(archive, 'rb') as source:
                    for block in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(block)
                if digest.hexdigest() != expected:
                    raise CertHubError('更新包 SHA-256 校验失败')
                public_key = os.path.join(PLUGIN_DIR, 'assets', 'release-public-key.pem')
                verified = subprocess.run(
                    ['openssl', 'dgst', '-sha256', '-verify', public_key, '-signature', signature_file, archive],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False
                )
                if verified.returncode != 0:
                    raise CertHubError('更新包数字签名验证失败')
                extract_dir = os.path.join(stage, 'extracted')
                os.makedirs(extract_dir, mode=0o700)
                with zipfile.ZipFile(archive) as package:
                    total = 0
                    for item in package.infolist():
                        normalized = item.filename.replace('\\', '/')
                        parts = normalized.split('/')
                        mode = item.external_attr >> 16
                        if (not normalized or normalized.startswith('/') or '..' in parts or
                                stat.S_ISLNK(mode) or parts[0] != 'certhub'):
                            raise CertHubError('更新包包含不安全路径')
                        total += item.file_size
                        if total > 250 * 1024 * 1024:
                            raise CertHubError('更新包解压后超过允许大小')
                    package.extractall(extract_dir)
                source_dir = os.path.join(extract_dir, 'certhub')
                with open(os.path.join(source_dir, 'info.json'), 'r', encoding='utf-8') as handle:
                    packaged_version = str(json.load(handle).get('versions') or '')
                if packaged_version != release['latest_version']:
                    raise CertHubError('更新包版本与 Release 不一致')
                subprocess.Popen(
                    [os.path.join(PLUGIN_DIR, 'update.sh'), 'apply', stage],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    close_fds=True, start_new_session=True
                )
                audit('plugin.update', 'plugin', release['latest_version'])
                return self.ok(release, '更新已启动，面板即将重启')
            except Exception:
                shutil.rmtree(stage, ignore_errors=True)
                raise
        return self.guard(run)

    def download_file(self, name):
        return ''
