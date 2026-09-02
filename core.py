# coding: utf-8
from __future__ import absolute_import

import base64
import datetime
import hashlib
import hmac
import ipaddress
import json
import ntpath
import os
import platform
import re
import secrets
import socket
import sqlite3
import ssl
import subprocess
import tempfile
import threading
import time
import uuid

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('CERTHUB_DATA_DIR', '/www/server/certhub')
DB_PATH = os.path.join(DATA_DIR, 'certhub.db')
ROTATION_KEY_PATH = os.path.join(DATA_DIR, 'auth-rotation.key')
ALLOWED_ROOTS = ('/www/server/panel/vhost/ssl',)
MAX_CERT_BYTES = 1024 * 1024
MAX_KEY_BYTES = 128 * 1024
MAX_PULL_EVENTS = 100000
_db_lock = threading.RLock()


class CertHubError(Exception):
    pass


def enforce_rate_limit(key, limit, window_seconds):
    now = int(time.time())
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT window_started_at,request_count FROM rate_limits WHERE rate_key=?', (key,)).fetchone()
        if not row or row['window_started_at'] <= now - window_seconds:
            db.execute('INSERT INTO rate_limits(rate_key,window_started_at,request_count) VALUES(?,?,1) '
                       'ON CONFLICT(rate_key) DO UPDATE SET window_started_at=excluded.window_started_at,request_count=1', (key, now))
        elif row['request_count'] >= limit:
            raise CertHubError('请求过于频繁，请稍后重试')
        else:
            db.execute('UPDATE rate_limits SET request_count=request_count+1 WHERE rate_key=?', (key,))
        if now % 300 == 0:
            db.execute('DELETE FROM rate_limits WHERE window_started_at<?', (now - 3600,))


def utcnow():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def token_urlsafe(size=32):
    return secrets.token_urlsafe(size)


def token_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def version_at_least(value, minimum):
    def parts(item):
        match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', str(item or '').strip())
        return tuple(int(x) for x in match.groups()) if match else (0, 0, 0)
    return parts(value) >= parts(minimum)


def rotation_key():
    os.makedirs(DATA_DIR, mode=0o700, exist_ok=True)
    try:
        with open(ROTATION_KEY_PATH, 'rb') as handle:
            key = handle.read(64)
        if len(key) == 32:
            return key
    except OSError:
        pass
    key = os.urandom(32)
    temporary = ROTATION_KEY_PATH + '.new'
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, key)
    finally:
        os.close(descriptor)
    try:
        os.replace(temporary, ROTATION_KEY_PATH)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        with open(ROTATION_KEY_PATH, 'rb') as handle:
            key = handle.read(64)
    os.chmod(ROTATION_KEY_PATH, 0o600)
    return key


def derived_auth_token(client_uuid, generation):
    digest = hmac.new(rotation_key(), ('%s:%s' % (client_uuid, generation)).encode('utf-8'), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')


def connect():
    os.makedirs(DATA_DIR, mode=0o700, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=15000')
    return db


SCHEMA = r'''
CREATE TABLE IF NOT EXISTS settings (
  setting_key TEXT PRIMARY KEY,
  setting_value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS certificates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  source_path TEXT NOT NULL UNIQUE,
  subject_name TEXT NOT NULL,
  sans_json TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  not_before TEXT,
  not_after TEXT,
  auto_sync INTEGER NOT NULL DEFAULT 1,
  last_checked_at TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_uuid TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  platform TEXT NOT NULL CHECK(platform IN ('linux','windows')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','revoked')),
  auth_token_hash TEXT,
  hostname TEXT,
  os_name TEXT,
  os_version TEXT,
  architecture TEXT,
  agent_version TEXT,
  allowed_ip TEXT,
  deploy_mode TEXT NOT NULL DEFAULT 'files-only',
  download_path TEXT,
  auto_deploy_sites INTEGER NOT NULL DEFAULT 0,
  sync_interval_seconds INTEGER NOT NULL DEFAULT 3600,
  sync_schedule TEXT NOT NULL DEFAULT '0 * * * *',
  config_updated_at TEXT,
  force_sync_token TEXT,
  force_sync_requested_at TEXT,
  force_sync_completed_at TEXT,
  update_token TEXT,
  update_requested_at TEXT,
  update_completed_at TEXT,
  update_completed_version TEXT,
  cleanup_token TEXT,
  cleanup_requested_at TEXT,
  cleanup_completed_at TEXT,
  revoke_after_cleanup INTEGER NOT NULL DEFAULT 0,
  last_ip TEXT,
  last_seen_at TEXT,
  created_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS enrollments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at INTEGER NOT NULL,
  used_at TEXT,
  used_ip TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS grants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  certificate_id INTEGER NOT NULL REFERENCES certificates(id) ON DELETE CASCADE,
  effect TEXT NOT NULL DEFAULT 'allow' CHECK(effect IN ('allow','deny')),
  install_profile TEXT NOT NULL DEFAULT 'files-only',
  target_fullchain TEXT,
  target_private_key TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE(client_id,certificate_id)
);
CREATE TABLE IF NOT EXISTS pull_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  certificate_id INTEGER REFERENCES certificates(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  ip_address TEXT,
  hostname TEXT,
  os_name TEXT,
  os_version TEXT,
  architecture TEXT,
  agent_version TEXT,
  success INTEGER NOT NULL,
  message TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pull_events_created ON pull_events(created_at);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS certificate_cleanup_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  san_key TEXT NOT NULL,
  sans_json TEXT NOT NULL,
  command_token TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  UNIQUE(client_id,san_key)
);
CREATE TABLE IF NOT EXISTS rate_limits (
  rate_key TEXT PRIMARY KEY,
  window_started_at INTEGER NOT NULL,
  request_count INTEGER NOT NULL
);
'''


def initialize():
    os.makedirs(DATA_DIR, mode=0o700, exist_ok=True)
    with _db_lock:
        db = connect()
        try:
            db.executescript(SCHEMA)
            columns = {row['name'] for row in db.execute('PRAGMA table_info(clients)')}
            migrations = {
                'allowed_ip': 'ALTER TABLE clients ADD COLUMN allowed_ip TEXT',
                'deploy_mode': "ALTER TABLE clients ADD COLUMN deploy_mode TEXT NOT NULL DEFAULT 'files-only'",
                'download_path': 'ALTER TABLE clients ADD COLUMN download_path TEXT',
                'auto_deploy_sites': 'ALTER TABLE clients ADD COLUMN auto_deploy_sites INTEGER NOT NULL DEFAULT 0',
                'sync_interval_seconds': 'ALTER TABLE clients ADD COLUMN sync_interval_seconds INTEGER NOT NULL DEFAULT 3600',
                'sync_schedule': "ALTER TABLE clients ADD COLUMN sync_schedule TEXT NOT NULL DEFAULT '0 * * * *'",
                'config_updated_at': 'ALTER TABLE clients ADD COLUMN config_updated_at TEXT',
                'force_sync_token': 'ALTER TABLE clients ADD COLUMN force_sync_token TEXT',
                'force_sync_requested_at': 'ALTER TABLE clients ADD COLUMN force_sync_requested_at TEXT',
                'force_sync_completed_at': 'ALTER TABLE clients ADD COLUMN force_sync_completed_at TEXT',
                'update_token': 'ALTER TABLE clients ADD COLUMN update_token TEXT',
                'update_requested_at': 'ALTER TABLE clients ADD COLUMN update_requested_at TEXT',
                'update_completed_at': 'ALTER TABLE clients ADD COLUMN update_completed_at TEXT',
                'update_completed_version': 'ALTER TABLE clients ADD COLUMN update_completed_version TEXT',
                'cleanup_token': 'ALTER TABLE clients ADD COLUMN cleanup_token TEXT',
                'cleanup_requested_at': 'ALTER TABLE clients ADD COLUMN cleanup_requested_at TEXT',
                'cleanup_completed_at': 'ALTER TABLE clients ADD COLUMN cleanup_completed_at TEXT',
                'revoke_after_cleanup': 'ALTER TABLE clients ADD COLUMN revoke_after_cleanup INTEGER NOT NULL DEFAULT 0',
                'auth_token_expires_at': 'ALTER TABLE clients ADD COLUMN auth_token_expires_at INTEGER',
                'auth_token_rotated_at': 'ALTER TABLE clients ADD COLUMN auth_token_rotated_at INTEGER',
                'auth_token_pending_hash': 'ALTER TABLE clients ADD COLUMN auth_token_pending_hash TEXT',
                'auth_token_pending_generation': 'ALTER TABLE clients ADD COLUMN auth_token_pending_generation INTEGER'
            }
            for name, sql in migrations.items():
                if name not in columns:
                    db.execute(sql)
            # Recover cleanup ownership for clients upgraded from agents which did
            # not remember the bt-panel ssl_saved record created by save_by_file.
            legacy = db.execute('''SELECT DISTINCT p.client_id,c.sans_json FROM pull_events p
                                   JOIN certificates c ON c.id=p.certificate_id
                                   WHERE p.action='bundle' AND NOT EXISTS(
                                     SELECT 1 FROM grants g WHERE g.client_id=p.client_id
                                     AND g.certificate_id=p.certificate_id AND g.effect='allow')''').fetchall()
            for item in legacy:
                sans = sorted(set(str(x).lower() for x in json.loads(item['sans_json'] or '[]')))
                key = json.dumps(sans, separators=(',', ':'))
                db.execute('''INSERT OR IGNORE INTO certificate_cleanup_tasks
                              (client_id,san_key,sans_json,command_token,created_at)
                              VALUES(?,?,?,?,?)''', (item['client_id'], key, key, token_urlsafe(24), utcnow()))
            db.commit()
        finally:
            db.close()
    os.chmod(DATA_DIR, 0o700)
    os.chmod(DB_PATH, 0o600)


def setting(key, default=''):
    with connect() as db:
        row = db.execute('SELECT setting_value FROM settings WHERE setting_key=?', (key,)).fetchone()
        return row['setting_value'] if row else default


def save_setting(key, value):
    with connect() as db:
        db.execute('INSERT INTO settings(setting_key,setting_value,updated_at) VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=excluded.updated_at', (key, value, utcnow()))


def validate_cron(expression):
    fields = str(expression or '').split()
    if len(fields) != 5:
        raise CertHubError('同步计划必须是五段 crontab 表达式')
    limits = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
    for field, (minimum, maximum) in zip(fields, limits):
        for part in field.split(','):
            base, separator, step = part.partition('/')
            if separator and (not step.isdigit() or int(step) < 1):
                raise CertHubError('同步计划步长无效')
            if base == '*':
                continue
            bounds = base.split('-')
            if len(bounds) not in (1, 2) or any(not value.isdigit() for value in bounds):
                raise CertHubError('同步计划格式无效')
            numbers = [int(value) for value in bounds]
            if any(value < minimum or value > maximum for value in numbers) or (len(numbers) == 2 and numbers[0] > numbers[1]):
                raise CertHubError('同步计划数值超出范围')


def audit(action, target_type=None, target_id=None, metadata=None):
    with connect() as db:
        db.execute('INSERT INTO audit_logs(action,target_type,target_id,metadata_json,created_at) VALUES(?,?,?,?,?)', (action, target_type, str(target_id) if target_id is not None else None, json.dumps(metadata or {}, ensure_ascii=False), utcnow()))


class CertificateScanner(object):
    CERT_NAMES = ('fullchain.pem', 'certificate.pem', 'cert.pem')
    KEY_NAMES = ('privkey.pem', 'private.key', 'key.pem')

    def discover(self):
        managed = {}
        with connect() as db:
            for row in db.execute('SELECT id,source_path FROM certificates'):
                managed[row['source_path']] = row['id']
        output = []
        seen = set()
        for root in ALLOWED_ROOTS:
            real_root = os.path.realpath(root)
            if not os.path.isdir(real_root):
                continue
            for name in sorted(os.listdir(real_root)):
                path = os.path.join(real_root, name)
                if os.path.islink(path) or not os.path.isdir(path):
                    continue
                real = os.path.realpath(path)
                if not real.startswith(real_root + os.sep) or real in seen:
                    continue
                seen.add(real)
                files = self.locate(real)
                if not files:
                    continue
                try:
                    info = self.inspect(files[0], files[1])
                    info.update({'name': name, 'path': real, 'managed': real in managed, 'certificate_id': managed.get(real)})
                except Exception as exc:
                    info = {'name': name, 'path': real, 'managed': real in managed, 'error': str(exc)}
                output.append(info)
        return output

    def import_local(self, path, name=None):
        real = self.assert_allowed(path)
        files = self.locate(real)
        if not files:
            raise CertHubError('目录中未找到证书链和私钥')
        info = self.inspect(files[0], files[1])
        now = utcnow()
        cert_name = (name or os.path.basename(real)).strip()
        if not cert_name or len(cert_name) > 190:
            raise CertHubError('证书名称无效')
        with connect() as db:
            db.execute('''INSERT INTO certificates(name,source_path,subject_name,sans_json,fingerprint,not_before,not_after,last_checked_at,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?)
                          ON CONFLICT(source_path) DO UPDATE SET name=excluded.name,subject_name=excluded.subject_name,sans_json=excluded.sans_json,fingerprint=excluded.fingerprint,not_before=excluded.not_before,not_after=excluded.not_after,last_checked_at=excluded.last_checked_at,last_error=NULL,updated_at=excluded.updated_at''',
                       (cert_name, real, info['subject'], json.dumps(info['sans'], ensure_ascii=False), info['fingerprint'], info['not_before'], info['not_after'], now, now, now))
            row = db.execute('SELECT id FROM certificates WHERE source_path=?', (real,)).fetchone()
        audit('certificate.manage', 'certificate', row['id'], {'path': real})
        return dict(info, id=row['id'], name=cert_name, path=real)

    def refresh(self, certificate_id):
        with connect() as db:
            row = db.execute('SELECT * FROM certificates WHERE id=?', (certificate_id,)).fetchone()
        if not row:
            raise CertHubError('证书不存在')
        try:
            real = self.assert_allowed(row['source_path'])
            files = self.locate(real)
            if not files:
                raise CertHubError('源证书文件缺失')
            info = self.inspect(files[0], files[1])
            with connect() as db:
                db.execute('UPDATE certificates SET subject_name=?,sans_json=?,fingerprint=?,not_before=?,not_after=?,last_checked_at=?,last_error=NULL,updated_at=? WHERE id=?', (info['subject'], json.dumps(info['sans'], ensure_ascii=False), info['fingerprint'], info['not_before'], info['not_after'], utcnow(), utcnow(), certificate_id))
            return info
        except Exception as exc:
            with connect() as db:
                db.execute('UPDATE certificates SET last_checked_at=?,last_error=? WHERE id=?', (utcnow(), str(exc)[:1000], certificate_id))
            raise

    def read_bundle(self, certificate_id):
        info = self.refresh(certificate_id)
        with connect() as db:
            row = db.execute('SELECT * FROM certificates WHERE id=?', (certificate_id,)).fetchone()
        files = self.locate(row['source_path'])
        fullchain = self.read_limited(files[0], MAX_CERT_BYTES)
        private_key = self.read_limited(files[1], MAX_KEY_BYTES)
        version = hashlib.sha256(fullchain + b'\0' + private_key).hexdigest()
        return {
            'certificate_id': certificate_id, 'name': row['name'], 'version': version,
            'subject': info['subject'], 'sans': info['sans'], 'not_after': info['not_after'],
            'fullchain_pem': fullchain.decode('ascii'), 'private_key_pem': private_key.decode('ascii')
        }

    def locate(self, path):
        cert = next((os.path.join(path, n) for n in self.CERT_NAMES if os.path.isfile(os.path.join(path, n)) and not os.path.islink(os.path.join(path, n))), None)
        key = next((os.path.join(path, n) for n in self.KEY_NAMES if os.path.isfile(os.path.join(path, n)) and not os.path.islink(os.path.join(path, n))), None)
        return (cert, key) if cert and key else None

    def inspect(self, cert_path, key_path):
        cert_bytes = self.read_limited(cert_path, MAX_CERT_BYTES)
        self.read_limited(key_path, MAX_KEY_BYTES)
        with tempfile.NamedTemporaryFile(prefix='certhub-cert-', suffix='.pem', delete=True) as tmp:
            tmp.write(cert_bytes); tmp.flush()
            decoded = ssl._ssl._test_decode_cert(tmp.name)
        self.verify_pair(cert_path, key_path)
        sans = [value for kind, value in decoded.get('subjectAltName', []) if kind == 'DNS']
        subject = ''
        for group in decoded.get('subject', []):
            for key, value in group:
                if key == 'commonName': subject = value
        not_after_epoch = ssl.cert_time_to_seconds(decoded['notAfter'])
        if not_after_epoch <= time.time():
            raise CertHubError('证书已经过期')
        issuer_values = {}
        for group in decoded.get('issuer', []):
            for key, value in group:
                issuer_values[key] = value
        subject_values = {}
        for group in decoded.get('subject', []):
            for key, value in group:
                subject_values[key] = value
        issuer_text = ' '.join(str(value) for value in issuer_values.values())
        brands = (
            ('Let\'s Encrypt', "Let's Encrypt"), ('DigiCert', 'DigiCert'), ('Sectigo', 'Sectigo'),
            ('GlobalSign', 'GlobalSign'), ('ZeroSSL', 'ZeroSSL'), ('Google Trust Services', 'Google Trust Services'),
            ('Buypass', 'Buypass'), ('SSL.com', 'SSL.com'), ('Entrust', 'Entrust'),
            ('GoDaddy', 'GoDaddy'), ('Actalis', 'Actalis'), ('TrustAsia', 'TrustAsia'),
        )
        issuer_brand = next((label for needle, label in brands if needle.lower() in issuer_text.lower()),
                            issuer_values.get('organizationName') or issuer_values.get('commonName') or '未知')
        policy = subprocess.run(['openssl', 'x509', '-in', cert_path, '-noout', '-text'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        policy_text = policy.stdout.decode('utf-8', 'ignore') if policy.returncode == 0 else ''
        if '2.23.140.1.1' in policy_text:
            validation_type = 'EV'
        elif '2.23.140.1.2.2' in policy_text:
            validation_type = 'OV'
        elif '2.23.140.1.2.1' in policy_text:
            validation_type = 'DV'
        elif '2.23.140.1.2.3' in policy_text:
            validation_type = 'IV'
        elif subject_values.get('organizationName'):
            validation_type = 'OV'
        else:
            validation_type = 'DV'
        return {
            'subject': subject or (sans[0] if sans else 'unknown'), 'sans': sans,
            'not_before': decoded.get('notBefore'), 'not_after': decoded.get('notAfter'),
            'issuer_brand': issuer_brand, 'validation_type': validation_type,
            'fingerprint': hashlib.sha256(cert_bytes).hexdigest()
        }

    def verify_pair(self, cert_path, key_path):
        cert_cmd = ['openssl', 'x509', '-in', cert_path, '-pubkey', '-noout']
        key_cmd = ['openssl', 'pkey', '-in', key_path, '-pubout']
        cert_pub = subprocess.run(cert_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        key_pub = subprocess.run(key_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        if cert_pub.returncode or key_pub.returncode:
            raise CertHubError('证书或私钥无法由 OpenSSL 解析')
        if not secrets.compare_digest(hashlib.sha256(cert_pub.stdout).digest(), hashlib.sha256(key_pub.stdout).digest()):
            raise CertHubError('证书与私钥不匹配')

    def assert_allowed(self, path):
        if not path or os.path.islink(path):
            raise CertHubError('证书目录无效或不允许符号链接')
        real = os.path.realpath(path)
        if not os.path.isdir(real):
            raise CertHubError('证书目录不存在')
        for root in ALLOWED_ROOTS:
            root_real = os.path.realpath(root)
            if real.startswith(root_real + os.sep):
                return real
        raise CertHubError('目录不在宝塔证书根目录内')

    @staticmethod
    def read_limited(path, limit):
        size = os.path.getsize(path)
        if size <= 0 or size > limit:
            raise CertHubError('证书文件为空或超过大小限制')
        with open(path, 'rb') as handle:
            return handle.read(limit + 1)


class ClientService(object):
    def create(self, name, client_platform, certificate_ids, options=None):
        name = (name or '').strip()
        if not name or len(name) > 190:
            raise CertHubError('客户端名称无效')
        if client_platform not in ('linux', 'windows'):
            raise CertHubError('客户端平台无效')
        panel_url = setting('panel_base_url').strip().rstrip('/')
        if not panel_url:
            raise CertHubError('请先在“设置”中保存宝塔面板公开地址')
        client_uuid = str(uuid.uuid4())
        enrollment = token_urlsafe(32)
        now = utcnow()
        config = self.validate_config(client_platform, options or {})
        with connect() as db:
            cur = db.execute('''INSERT INTO clients(client_uuid,name,platform,allowed_ip,deploy_mode,download_path,auto_deploy_sites,sync_interval_seconds,sync_schedule,config_updated_at,created_at)
                                VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (client_uuid, name, client_platform, config['allowed_ip'], config['deploy_mode'], config['download_path'], config['auto_deploy_sites'], config['sync_interval_seconds'], config['sync_schedule'], now, now))
            client_id = cur.lastrowid
            db.execute('INSERT INTO enrollments(client_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)', (client_id, token_hash(enrollment), int(time.time()) + 1800, now))
            for certificate_id in sorted(set(int(x) for x in certificate_ids if int(x) > 0)):
                db.execute("INSERT INTO grants(client_id,certificate_id,effect,updated_at) VALUES(?,?, 'allow',?) ON CONFLICT(client_id,certificate_id) DO UPDATE SET effect='allow',updated_at=excluded.updated_at", (client_id, certificate_id, now))
        audit('client.create', 'client', client_id, {'platform': client_platform})
        return self.installation(client_id, client_uuid, client_platform, enrollment, panel_url)

    def update(self, client_id, name, certificate_ids, options=None):
        name = (name or '').strip()
        if not name or len(name) > 190:
            raise CertHubError('客户端名称无效')
        now = utcnow()
        with connect() as db:
            row = db.execute('SELECT platform,status FROM clients WHERE id=?', (client_id,)).fetchone()
            if not row:
                raise CertHubError('客户端不存在')
            config = self.validate_config(row['platform'], options or {})
            selected_ids = sorted(set(int(x) for x in certificate_ids if int(x) > 0))
            old_rows = db.execute('''SELECT c.id,c.sans_json FROM grants g JOIN certificates c ON c.id=g.certificate_id
                                     WHERE g.client_id=? AND g.effect='allow' ''', (client_id,)).fetchall()
            selected_sans = set()
            if selected_ids:
                marks = ','.join('?' for _ in selected_ids)
                for item in db.execute('SELECT sans_json FROM certificates WHERE id IN (%s)' % marks, selected_ids):
                    selected_sans.add(json.dumps(sorted(set(str(x).lower() for x in json.loads(item['sans_json'] or '[]'))), separators=(',', ':')))
            for item in old_rows:
                key = json.dumps(sorted(set(str(x).lower() for x in json.loads(item['sans_json'] or '[]'))), separators=(',', ':'))
                if item['id'] not in selected_ids and key not in selected_sans:
                    db.execute('''INSERT INTO certificate_cleanup_tasks(client_id,san_key,sans_json,command_token,created_at,completed_at)
                                  VALUES(?,?,?,?,?,NULL) ON CONFLICT(client_id,san_key) DO UPDATE SET
                                  sans_json=excluded.sans_json,command_token=excluded.command_token,
                                  created_at=excluded.created_at,completed_at=NULL''',
                               (client_id, key, key, token_urlsafe(24), now))
                elif key in selected_sans:
                    db.execute('DELETE FROM certificate_cleanup_tasks WHERE client_id=? AND san_key=?', (client_id, key))
            db.execute('''UPDATE clients SET name=?,allowed_ip=?,deploy_mode=?,download_path=?,auto_deploy_sites=?,sync_interval_seconds=?,sync_schedule=?,config_updated_at=? WHERE id=?''',
                       (name, config['allowed_ip'], config['deploy_mode'], config['download_path'], config['auto_deploy_sites'], config['sync_interval_seconds'], config['sync_schedule'], now, client_id))
            db.execute('DELETE FROM grants WHERE client_id=?', (client_id,))
            for certificate_id in selected_ids:
                db.execute("INSERT INTO grants(client_id,certificate_id,effect,updated_at) VALUES(?,?, 'allow',?)", (client_id, certificate_id, now))
        audit('client.update', 'client', client_id, {'certificate_ids': certificate_ids})

    @staticmethod
    def validate_config(client_platform, options):
        allowed_ip = str(options.get('allowed_ip') or '').strip()
        if allowed_ip:
            try:
                allowed_ip = str(ipaddress.ip_address(allowed_ip))
            except ValueError:
                try:
                    allowed_ip = allowed_ip.rstrip('.').encode('idna').decode('ascii').lower()
                except (UnicodeError, ValueError):
                    raise CertHubError('限制请求来源域名格式无效')
                if len(allowed_ip) > 253 or not re.match(r'^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$', allowed_ip):
                    raise CertHubError('限制请求来源必须是有效 IP 或域名')
        deploy_mode = str(options.get('deploy_mode') or ('user-home' if client_platform == 'windows' else 'files-only'))
        if deploy_mode not in ('files-only', 'custom', 'bt-panel', 'user-home'):
            raise CertHubError('证书部署方式无效')
        if client_platform != 'linux' and deploy_mode == 'bt-panel':
            raise CertHubError('宝塔面板部署方式仅支持 Linux 客户端')
        if client_platform != 'windows' and deploy_mode == 'user-home':
            raise CertHubError('用户目录部署方式仅支持 Windows 客户端')
        download_path = str(options.get('download_path') or '').strip() or None
        if deploy_mode == 'custom':
            normalized = (download_path or '').replace('\\', '/')
            absolute = ntpath.isabs(download_path or '') if client_platform == 'windows' else bool(download_path and download_path.startswith('/'))
            if (not absolute or '..' in normalized.split('/') or
                    any(ord(char) < 32 for char in (download_path or ''))):
                raise CertHubError('自定义下载目录必须是安全的绝对路径')
            if client_platform == 'windows':
                safe_path = ntpath.normcase(ntpath.normpath(download_path))
                drive, tail = ntpath.splitdrive(safe_path)
                blocked = {ntpath.normcase(drive + '\\' + name) for name in
                           ('windows', 'program files', 'program files (x86)', 'programdata', 'users')}
                if not drive or tail in ('', '\\', '/') or safe_path in blocked:
                    raise CertHubError('自定义下载目录不能使用 Windows 系统根目录')
            else:
                safe_path = os.path.normpath(download_path)
                blocked = {'/', '/bin', '/boot', '/dev', '/etc', '/lib', '/lib64', '/proc',
                           '/root', '/run', '/sbin', '/sys', '/usr', '/var'}
                if safe_path in blocked:
                    raise CertHubError('自定义下载目录不能使用 Linux 系统根目录')
        schedule = str(options.get('sync_schedule') or '0 * * * *').strip()
        validate_cron(schedule)
        return {'allowed_ip': allowed_ip or None, 'deploy_mode': deploy_mode, 'download_path': download_path,
                'auto_deploy_sites': 1 if str(options.get('auto_deploy_sites', '0')).lower() in ('1', 'true', 'yes') else 0,
                'sync_interval_seconds': 3600, 'sync_schedule': schedule}

    def reissue_enrollment(self, client_id):
        panel_url = setting('panel_base_url').strip().rstrip('/')
        if not panel_url:
            raise CertHubError('请先在“设置”中保存宝塔面板公开地址')
        enrollment = token_urlsafe(32)
        now = utcnow()
        with connect() as db:
            row = db.execute("SELECT id,client_uuid,platform,status FROM clients WHERE id=?", (client_id,)).fetchone()
            if not row:
                raise CertHubError('客户端不存在')
            if row['status'] != 'pending':
                raise CertHubError('只能为待注册客户端重新生成安装命令')
            db.execute('DELETE FROM enrollments WHERE client_id=? AND used_at IS NULL', (client_id,))
            db.execute('INSERT INTO enrollments(client_id,token_hash,expires_at,created_at) VALUES(?,?,?,?)', (client_id, token_hash(enrollment), int(time.time()) + 1800, now))
        audit('client.enrollment.reissue', 'client', client_id)
        return self.installation(client_id, row['client_uuid'], row['platform'], enrollment, panel_url)

    @staticmethod
    def installation(client_id, client_uuid, client_platform, enrollment, panel_url):
        endpoint = panel_url + '/certhub-api'
        if client_platform == 'windows':
            install_url = '%s?action=install_windows_exe' % endpoint
            encoded = base64.urlsafe_b64encode(endpoint.encode('utf-8')).decode('ascii').rstrip('=')
            filename = 'certhub-setup..%s..%s.exe' % (encoded, enrollment)
            command = "$u='%s';$t='%s';$p=Join-Path $env:TEMP '%s';try{Invoke-WebRequest -UseBasicParsing -Method Post -Uri $u -Body @{token=$t} -OutFile $p}catch{& curl.exe -4 -fSL -X POST --data-urlencode \"token=$t\" $u -o $p;if($LASTEXITCODE -ne 0){throw}};Start-Process -FilePath $p -Verb RunAs" % (install_url.replace("'", "''"), enrollment, filename)
        else:
            install_url = None
            url = "%s?action=install_linux" % endpoint
            command = "{ curl -fsS -X POST --data-urlencode 'token=%s' '%s' -o /tmp/certhub-install.sh || curl -4 -fsS -X POST --data-urlencode 'token=%s' '%s' -o /tmp/certhub-install.sh; } && sudo bash /tmp/certhub-install.sh" % (enrollment, url, enrollment, url)
        return {'id': client_id, 'client_uuid': client_uuid, 'platform': client_platform, 'enrollment_token': enrollment, 'expires_at': int(time.time()) + 1800, 'install_command': command, 'install_url': install_url}

    def enroll(self, enrollment, ip, system_info):
        enforce_rate_limit('enroll:%s' % ip, 20, 300)
        if len(enrollment or '') < 32:
            raise CertHubError('注册凭据无效')
        now = utcnow()
        with _db_lock:
            db = connect()
            try:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT e.*,c.client_uuid,c.name,c.platform,c.status,c.allowed_ip FROM enrollments e JOIN clients c ON c.id=e.client_id WHERE e.token_hash=?', (token_hash(enrollment),)).fetchone()
                if not row or row['used_at'] or row['expires_at'] < int(time.time()) or row['status'] == 'revoked':
                    raise CertHubError('注册凭据已使用、已过期或无效')
                self.assert_ip(row['allowed_ip'], ip)
                auth_token = token_urlsafe(48)
                db.execute('UPDATE enrollments SET used_at=?,used_ip=? WHERE id=?', (now, ip, row['id']))
                db.execute("UPDATE clients SET status='active',auth_token_hash=?,hostname=?,os_name=?,os_version=?,architecture=?,agent_version=?,last_ip=?,last_seen_at=? WHERE id=?", (token_hash(auth_token), self.field(system_info, 'hostname'), self.field(system_info, 'os_name'), self.field(system_info, 'os_version'), self.field(system_info, 'architecture'), self.field(system_info, 'agent_version'), ip, now, row['client_id']))
                db.commit()
                return {'client_id': row['client_uuid'], 'name': row['name'], 'platform': row['platform'], 'auth_token': auth_token, 'api_endpoint': setting('panel_base_url').rstrip('/') + '/certhub-api'}
            except Exception:
                db.rollback(); raise
            finally:
                db.close()

    def authenticate(self, client_uuid, auth_token, ip, system_info=None, action='pull', certificate_id=None):
        enforce_rate_limit('auth-ip:%s' % ip, 300, 300)
        try:
            retention_days = max(1, min(3650, int(setting('pull_retention_days', '30') or 30)))
        except (TypeError, ValueError):
            retention_days = 30
        retention_cutoff = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - retention_days * 86400))
        with connect() as db:
            row = db.execute("SELECT * FROM clients WHERE client_uuid=? AND status='active'", (client_uuid or '',)).fetchone()
            supplied_hash = token_hash(auth_token) if auth_token else ''
            current_match = bool(row and auth_token and secrets.compare_digest(row['auth_token_hash'] or '', supplied_hash))
            pending_match = bool(row and auth_token and row['auth_token_pending_hash'] and
                                 secrets.compare_digest(row['auth_token_pending_hash'], supplied_hash))
            if not row or not (current_match or pending_match):
                raise CertHubError('客户端认证失败')
            self.assert_ip(row['allowed_ip'], ip)
            enforce_rate_limit('client:%s' % row['client_uuid'], 180, 300)
            if row['revoke_after_cleanup'] and action not in ('pull', 'ack_cleanup'):
                raise CertHubError('客户端正在撤销，仅允许执行清理')
            info = system_info or {}
            now = utcnow()
            now_epoch = int(time.time())
            supports_rotation = version_at_least(self.field(info, 'agent_version', row['agent_version']),
                                                 '0.3.15' if row['platform'] == 'linux' else '0.3.13')
            expired = bool(current_match and row['auth_token_expires_at'] and row['auth_token_expires_at'] <= now_epoch)
            if expired and (action != 'pull' or not supports_rotation):
                raise CertHubError('客户端认证凭据已过期')
            if pending_match:
                db.execute('''UPDATE clients SET auth_token_hash=auth_token_pending_hash,auth_token_pending_hash=NULL,
                              auth_token_pending_generation=NULL,auth_token_rotated_at=?,auth_token_expires_at=? WHERE id=?''',
                           (now_epoch, now_epoch + 90 * 86400, row['id']))
                expired = False
            db.execute('UPDATE clients SET hostname=?,os_name=?,os_version=?,architecture=?,agent_version=?,last_ip=?,last_seen_at=? WHERE id=?', (self.field(info, 'hostname', row['hostname']), self.field(info, 'os_name', row['os_name']), self.field(info, 'os_version', row['os_version']), self.field(info, 'architecture', row['architecture']), self.field(info, 'agent_version', row['agent_version']), ip, now, row['id']))
            if action in ('pull', 'bundle'):
                cursor = db.execute('INSERT INTO pull_events(client_id,certificate_id,action,ip_address,hostname,os_name,os_version,architecture,agent_version,success,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (row['id'], certificate_id, action, ip, self.field(info, 'hostname'), self.field(info, 'os_name'), self.field(info, 'os_version'), self.field(info, 'architecture'), self.field(info, 'agent_version'), 1, now))
                if cursor.lastrowid and cursor.lastrowid % 100 == 0:
                    db.execute('DELETE FROM pull_events WHERE id <= COALESCE((SELECT id FROM pull_events ORDER BY id DESC LIMIT 1 OFFSET ?), 0)', (MAX_PULL_EVENTS,))
            db.execute('DELETE FROM pull_events WHERE created_at<?', (retention_cutoff,))
            result = dict(row)
            result['_auth_expired'] = expired
            result['_supports_auth_rotation'] = supports_rotation
            return result

    def issue_auth_rotation(self, client):
        if not client.get('_supports_auth_rotation') or client.get('revoke_after_cleanup'):
            return None
        now = int(time.time())
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT client_uuid,auth_token_expires_at,auth_token_rotated_at,
                                auth_token_pending_hash,auth_token_pending_generation
                                FROM clients WHERE id=? AND status='active' AND revoke_after_cleanup=0''',
                             (client['id'],)).fetchone()
            if not row:
                return None
            if row['auth_token_pending_hash'] and row['auth_token_pending_generation']:
                token = derived_auth_token(row['client_uuid'], row['auth_token_pending_generation'])
                if secrets.compare_digest(token_hash(token), row['auth_token_pending_hash']):
                    return {'token': token, 'expires_at': now + 90 * 86400}
                raise CertHubError('客户端轮换凭据状态无效')
            if not row['auth_token_expires_at'] or not row['auth_token_rotated_at']:
                db.execute('UPDATE clients SET auth_token_rotated_at=?,auth_token_expires_at=? WHERE id=?',
                           (now, now + 90 * 86400, client['id']))
                return None
            if not client.get('_auth_expired') and row['auth_token_rotated_at'] > now - 30 * 86400:
                return None
            generation = int(now * 1000) ^ secrets.randbits(31)
            token = derived_auth_token(row['client_uuid'], generation)
            db.execute('UPDATE clients SET auth_token_pending_hash=?,auth_token_pending_generation=? WHERE id=?',
                       (token_hash(token), generation, client['id']))
            return {'token': token, 'expires_at': now + 90 * 86400}

    def assignments(self, client_id):
        with connect() as db:
            rows = db.execute('''SELECT cert.id,cert.name,cert.source_path,cert.subject_name,cert.sans_json,cert.fingerprint,cert.not_after,
                                        g.effect,g.install_profile,g.target_fullchain,g.target_private_key
                                 FROM grants g JOIN certificates cert ON cert.id=g.certificate_id
                                 JOIN clients client ON client.id=g.client_id
                                 WHERE g.client_id=? AND g.effect='allow' AND client.status='active'
                                 AND client.revoke_after_cleanup=0 ORDER BY cert.name''', (client_id,)).fetchall()
        result = []
        scanner = CertificateScanner()
        for row in rows:
            item = dict(row, sans=json.loads(row['sans_json']))
            files = scanner.locate(scanner.assert_allowed(row['source_path']))
            if not files:
                continue
            fullchain = scanner.read_limited(files[0], MAX_CERT_BYTES)
            private_key = scanner.read_limited(files[1], MAX_KEY_BYTES)
            item['version'] = hashlib.sha256(fullchain + b'\0' + private_key).hexdigest()
            item.pop('source_path', None)
            result.append(item)
        return result

    def pull_config(self, client_id):
        with connect() as db:
            row = db.execute('''SELECT platform,deploy_mode,download_path,auto_deploy_sites,sync_schedule,config_updated_at,force_sync_token,update_token,cleanup_token FROM clients WHERE id=?''', (client_id,)).fetchone()
            cleanup_rows = db.execute('''SELECT command_token,sans_json FROM certificate_cleanup_tasks
                                         WHERE client_id=? AND completed_at IS NULL ORDER BY id''', (client_id,)).fetchall()
        if not row:
            return {}
        if row['cleanup_token']:
            return {'cleanup': {'command_token': row['cleanup_token']}}
        result = dict(row)
        result['certificate_cleanup'] = [{'command_token': x['command_token'], 'sans': json.loads(x['sans_json'])} for x in cleanup_rows]
        if row['update_token']:
            info_path = os.path.join(PLUGIN_DIR, 'info.json')
            with open(info_path, 'r', encoding='utf-8') as handle:
                info = json.load(handle)
                version = info.get(row['platform'] + '_agent_version') or info.get('versions') or ''
            relative = ('windows/certhub-agent.exe' if row['platform'] == 'windows' else 'linux/agent')
            binary_path = os.path.join(PLUGIN_DIR, 'client', *relative.split('/'))
            with open(binary_path, 'rb') as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
            action = 'client_windows_binary' if row['platform'] == 'windows' else 'client_linux'
            result['update'] = {'command_token': row['update_token'], 'version': version, 'sha256': digest,
                                'url': setting('panel_base_url').rstrip('/') + '/certhub-api?action=' + action}
        result.pop('platform', None); result.pop('update_token', None); result.pop('cleanup_token', None)
        return result

    def acknowledge_certificate_cleanup(self, client_id, command_tokens):
        tokens = [str(x) for x in (command_tokens or []) if isinstance(x, str) and x]
        if not tokens:
            return
        marks = ','.join('?' for _ in tokens)
        with connect() as db:
            db.execute('''UPDATE certificate_cleanup_tasks SET completed_at=?
                          WHERE client_id=? AND completed_at IS NULL AND command_token IN (%s)''' % marks,
                       [utcnow(), client_id] + tokens)

    def acknowledge_force_sync(self, client_id, command_token):
        with connect() as db:
            row = db.execute('SELECT force_sync_token FROM clients WHERE id=?', (client_id,)).fetchone()
            if row and row['force_sync_token'] and secrets.compare_digest(row['force_sync_token'], str(command_token or '')):
                db.execute('UPDATE clients SET force_sync_token=NULL,force_sync_completed_at=? WHERE id=?', (utcnow(), client_id))

    def acknowledge_update(self, client_id, command_token):
        with connect() as db:
            row = db.execute('SELECT update_token,platform,agent_version FROM clients WHERE id=?', (client_id,)).fetchone()
            if row and row['update_token'] and secrets.compare_digest(row['update_token'], str(command_token or '')):
                target_version = row['agent_version']
                try:
                    with open(os.path.join(PLUGIN_DIR, 'info.json'), 'r', encoding='utf-8') as handle:
                        info = json.load(handle)
                    target_version = info.get(str(row['platform']) + '_agent_version') or target_version
                except (OSError, ValueError, TypeError):
                    pass
                db.execute('UPDATE clients SET update_token=NULL,update_completed_at=?,update_completed_version=? WHERE id=?', (utcnow(), target_version, client_id))

    def acknowledge_cleanup(self, client_id, command_token):
        with connect() as db:
            row = db.execute('SELECT cleanup_token,revoke_after_cleanup FROM clients WHERE id=?', (client_id,)).fetchone()
            if row and row['cleanup_token'] and secrets.compare_digest(row['cleanup_token'], str(command_token or '')):
                if row['revoke_after_cleanup']:
                    db.execute("""UPDATE clients SET cleanup_token=NULL,cleanup_completed_at=?,revoke_after_cleanup=0,status='revoked',
                               auth_token_hash=NULL,auth_token_pending_hash=NULL,auth_token_pending_generation=NULL,
                               auth_token_expires_at=NULL,revoked_at=? WHERE id=?""", (utcnow(), utcnow(), client_id))
                else:
                    db.execute('UPDATE clients SET cleanup_token=NULL,cleanup_completed_at=? WHERE id=?', (utcnow(), client_id))

    @staticmethod
    def assert_ip(allowed_ip, actual_ip):
        if not allowed_ip:
            return
        try:
            actual = str(ipaddress.ip_address(str(actual_ip).strip()))
        except ValueError:
            raise CertHubError('客户端来源 IP 无效')
        try:
            expected = str(ipaddress.ip_address(str(allowed_ip).strip()))
            matched = secrets.compare_digest(expected, actual)
        except ValueError:
            try:
                addresses = {str(ipaddress.ip_address(item[4][0])) for item in socket.getaddrinfo(str(allowed_ip), None, socket.AF_UNSPEC, socket.SOCK_STREAM)}
            except (socket.gaierror, OSError, ValueError):
                raise CertHubError('限制请求来源域名解析失败')
            matched = any(secrets.compare_digest(address, actual) for address in addresses)
        if not matched:
            raise CertHubError('客户端来源 IP 与允许的 IP/域名解析结果不匹配')

    def bundle(self, client_id, certificate_id):
        with connect() as db:
            grant = db.execute("""SELECT g.* FROM grants g JOIN clients c ON c.id=g.client_id
                                WHERE g.client_id=? AND g.certificate_id=? AND g.effect='allow'
                                AND c.status='active' AND c.revoke_after_cleanup=0""", (client_id, certificate_id)).fetchone()
        if not grant:
            raise CertHubError('客户端没有此证书权限')
        bundle = CertificateScanner().read_bundle(certificate_id)
        bundle.update({'install_profile': grant['install_profile'], 'target_fullchain': grant['target_fullchain'], 'target_private_key': grant['target_private_key']})
        return bundle

    @staticmethod
    def field(info, key, fallback=None):
        value = info.get(key, fallback) if isinstance(info, dict) else fallback
        if value is None:
            return None
        return str(value)[:512]


def extract_bearer(headers):
    value = headers.get('Authorization', '')
    match = re.match(r'^Bearer\s+(.+)$', value, re.I)
    return match.group(1).strip() if match else ''


def client_system_info():
    return {'hostname': platform.node(), 'os_name': platform.system(), 'os_version': platform.platform(), 'architecture': platform.machine(), 'agent_version': '0.3.10'}
