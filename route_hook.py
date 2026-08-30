# coding: utf-8
from __future__ import absolute_import

import base64
import json
import os
import sys

PLUGIN_DIR = '/www/server/panel/plugin/certhub'


def main():
    if PLUGIN_DIR not in sys.path:
        sys.path.insert(0, PLUGIN_DIR)
    from BTPanel import app
    if 'certhub_api' in app.view_functions:
        return
    from werkzeug.routing import Rule
    app.url_map.add(Rule('/certhub-api', endpoint='certhub_api', methods=['GET', 'POST']))
    app.view_functions['certhub_api'] = handle_request


def handle_request():
    if PLUGIN_DIR not in sys.path:
        sys.path.insert(0, PLUGIN_DIR)
    import public
    from flask import Response, request, session
    from core import CertHubError, ClientService, extract_bearer, setting

    def response(payload, status=200, content_type='application/json; charset=utf-8', headers=None):
        body = payload if isinstance(payload, (bytes, str)) else json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        resp = Response(body, status=status, content_type=content_type)
        resp.headers['Cache-Control'] = 'no-store'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        for key, value in (headers or {}).items():
            resp.headers[key] = value
        return resp

    try:
        action = request.args.get('action', 'health')
        service = ClientService()
        ip = public.GetClientIp()
        if request.method == 'GET' and action == 'health':
            return response({'status': True, 'data': {'service': 'CertHub', 'version': '0.9.0'}})
        if request.method == 'GET' and action == 'author_avatar':
            path = os.path.join(PLUGIN_DIR, 'assets', 'kot4ri.jpg')
            with open(path, 'rb') as handle:
                return response(handle.read(), 200, 'image/jpeg', {'Cache-Control': 'public, max-age=86400'})
        if request.method == 'GET' and action == 'plugin_icon':
            path = os.path.join(PLUGIN_DIR, 'icon.png')
            with open(path, 'rb') as handle:
                return response(handle.read(), 200, 'image/png', {'Cache-Control': 'public, max-age=86400'})
        if request.method == 'GET' and action in ('admin_css', 'admin_js'):
            if not session.get('login', False):
                return response('登录已失效，请重新登录宝塔面板。', 401, 'text/plain; charset=utf-8')
            filename = 'admin.css' if action == 'admin_css' else 'admin.js'
            content_type = 'text/css; charset=utf-8' if action == 'admin_css' else 'application/javascript; charset=utf-8'
            path = os.path.join(PLUGIN_DIR, 'assets', filename)
            with open(path, 'r', encoding='utf-8') as handle:
                return response(handle.read(), 200, content_type)
        if request.method == 'GET' and action == 'admin_ui':
            if not session.get('login', False):
                return response('登录已失效，请重新登录宝塔面板。', 401, 'text/plain; charset=utf-8')
            path = os.path.join(PLUGIN_DIR, 'admin.html')
            with open(path, 'r', encoding='utf-8') as handle:
                return response(handle.read(), 200, 'text/html; charset=utf-8')
        if request.method == 'POST' and action == 'admin_call':
            if not session.get('login', False):
                return response({'status': False, 'msg': '登录已失效'}, 401)
            method = request.args.get('method', '')
            allowed = {
                'dashboard', 'discover_local', 'complete_onboarding', 'skip_onboarding', 'import_local', 'sync_now', 'certificates',
                'remove_certificate', 'clients', 'create_client', 'update_client', 'revoke_client', 'restore_client', 'delete_client', 'reissue_enrollment',
                'save_grant', 'grants', 'save_settings', 'pull_events', 'clear_pull_events', 'reset_database', 'force_sync_clients', 'update_clients'
            }
            if method not in allowed:
                return response({'status': False, 'msg': '管理操作不存在'}, 404)
            from types import SimpleNamespace
            from certhub_main import certhub_main
            params = dict(request.form.items())
            result = getattr(certhub_main(), method)(SimpleNamespace(**params))
            return response(result)
        if request.method == 'GET' and action in ('install_linux', 'install_windows'):
            token = request.args.get('token', '')
            if len(token) < 32 or not all(ch.isalnum() or ch in '_-' for ch in token):
                raise CertHubError('安装凭据无效')
            platform_name = 'linux' if action == 'install_linux' else 'windows'
            filename = 'install.sh' if platform_name == 'linux' else 'install.bat'
            path = os.path.join(PLUGIN_DIR, 'client', platform_name, filename)
            with open(path, 'r', encoding='utf-8') as handle:
                script = handle.read()
            endpoint = setting('panel_base_url').rstrip('/') + '/certhub-api'
            script = script.replace('@@API_ENDPOINT@@', endpoint).replace('@@ENROLLMENT_TOKEN@@', token)
            content_type = 'text/x-shellscript' if platform_name == 'linux' else 'application/x-bat'
            return response(script, 200, content_type, {'Content-Disposition': 'attachment; filename="certhub-install.%s"' % ('sh' if platform_name == 'linux' else 'bat')})
        if request.method == 'GET' and action == 'install_windows_exe':
            token = request.args.get('token', '')
            if len(token) < 32 or not all(ch.isalnum() or ch in '_-' for ch in token):
                raise CertHubError('安装凭据无效')
            path = os.path.join(PLUGIN_DIR, 'client', 'windows', 'certhub-agent.exe')
            if not os.path.isfile(path):
                return response('Windows EXE 尚未上传，请先完成 windows_agent.py 打包。', 503, 'text/plain; charset=utf-8')
            endpoint = setting('panel_base_url').rstrip('/') + '/certhub-api'
            encoded = base64.urlsafe_b64encode(endpoint.encode('utf-8')).decode('ascii').rstrip('=')
            filename = 'certhub-setup..%s..%s.exe' % (encoded, token)
            with open(path, 'rb') as handle:
                return response(handle.read(), 200, 'application/vnd.microsoft.portable-executable', {'Content-Disposition': 'attachment; filename="%s"' % filename})
        if request.method == 'GET' and action == 'client_windows_binary':
            path = os.path.join(PLUGIN_DIR, 'client', 'windows', 'certhub-agent.exe')
            if not os.path.isfile(path):
                return response('Windows EXE 尚未上传。', 503, 'text/plain; charset=utf-8')
            with open(path, 'rb') as handle:
                return response(handle.read(), 200, 'application/vnd.microsoft.portable-executable', {'Content-Disposition': 'attachment; filename="certhub-agent.exe"'})
        static_clients = {
            'client_linux': ('linux/agent', 'text/x-shellscript'),
            'client_linux_service': ('linux/certhub-agent.service', 'text/plain'),
            'client_windows': ('windows/agent.ps1', 'text/plain'),
            'client_windows_python': ('windows/windows_agent.py', 'text/plain'),
        }
        if request.method == 'GET' and action in static_clients:
            relative, content_type = static_clients[action]
            path = os.path.join(PLUGIN_DIR, 'client', *relative.split('/'))
            with open(path, 'r', encoding='utf-8') as handle:
                return response(handle.read(), 200, content_type)
        data = request.get_json(silent=True) or {}
        if request.method == 'POST' and action == 'enroll':
            result = service.enroll(str(data.get('token', '')), ip, data.get('system') or {})
            return response({'status': True, 'data': result})
        client = service.authenticate(request.headers.get('X-CertHub-Client', ''), extract_bearer(request.headers), ip, data.get('system') or {}, action=action, certificate_id=int(data.get('certificate_id') or 0) or None)
        if request.method == 'POST' and action == 'pull':
            return response({'status': True, 'data': {'config': service.pull_config(client['id']), 'certificates': service.assignments(client['id'])}})
        if request.method == 'POST' and action == 'bundle':
            return response({'status': True, 'data': service.bundle(client['id'], int(data.get('certificate_id') or 0))})
        if request.method == 'POST' and action == 'ack_sync':
            service.acknowledge_force_sync(client['id'], data.get('command_token'))
            return response({'status': True, 'data': {}})
        if request.method == 'POST' and action == 'ack_update':
            service.acknowledge_update(client['id'], data.get('command_token'))
            return response({'status': True, 'data': {}})
        if request.method == 'POST' and action == 'ack_cleanup':
            service.acknowledge_cleanup(client['id'], data.get('command_token'))
            return response({'status': True, 'data': {}})
        return response({'status': False, 'error': 'not_found'}, 404)
    except CertHubError as exc:
        message = str(exc)
        status = 401 if '认证' in message else (403 if '权限' in message else 400)
        return response({'status': False, 'error': message}, status)
    except Exception:
        return response({'status': False, 'error': 'internal_error'}, 500)
