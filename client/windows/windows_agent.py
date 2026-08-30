#!/usr/bin/env python3
"""CertHub Windows Agent entry point, suitable for one-file EXE packaging."""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import datetime
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.3.12"
POLL_SECONDS = 300
PROGRAM_DATA = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "CertHub"
CONFIG_FILE = PROGRAM_DATA / "config.protected"
STATE_FILE = PROGRAM_DATA / "state.json"
LOG_FILE = PROGRAM_DATA / "agent.log"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def dpapi_protect(data: bytes) -> bytes:
    source, keepalive = _blob(data)
    output = DATA_BLOB()
    flags = 0x4  # CRYPTPROTECT_LOCAL_MACHINE
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, flags, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def dpapi_unprotect(data: bytes) -> bytes:
    source, keepalive = _blob(data)
    output = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def write_config(config: dict) -> None:
    PROGRAM_DATA.mkdir(parents=True, exist_ok=True)
    protected = dpapi_protect(json.dumps(config, separators=(",", ":")).encode("utf-8"))
    temporary = CONFIG_FILE.with_suffix(".new")
    temporary.write_bytes(protected)
    os.replace(temporary, CONFIG_FILE)


def read_config() -> dict:
    return json.loads(dpapi_unprotect(CONFIG_FILE.read_bytes()).decode("utf-8"))


def system_info() -> dict:
    return {
        "hostname": platform.node(),
        "os_name": "Windows",
        "os_version": platform.platform(),
        "architecture": platform.machine(),
        "agent_version": VERSION,
    }


def urlopen_with_ipv4_fallback(target, *, timeout: int):
    context = ssl.create_default_context()
    try:
        return urllib.request.urlopen(target, timeout=timeout, context=context)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as first_error:
        original_getaddrinfo = socket.getaddrinfo

        def ipv4_getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
            return original_getaddrinfo(host, port, socket.AF_INET, socktype, proto, flags)

        socket.getaddrinfo = ipv4_getaddrinfo
        try:
            logging.warning("default/IPv6 request failed; retrying over IPv4: %s", first_error)
            return urllib.request.urlopen(target, timeout=timeout, context=context)
        finally:
            socket.getaddrinfo = original_getaddrinfo


def request(api: str, action: str, payload: dict, config: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json", "User-Agent": f"CertHub-Windows/{VERSION}"}
    if config:
        headers["X-CertHub-Client"] = config["client_id"]
        headers["Authorization"] = "Bearer " + config["auth_token"]
    req = urllib.request.Request(
        api + "?" + urllib.parse.urlencode({"action": action}),
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"), headers=headers, method="POST"
    )
    result = None
    for attempt in range(3):
        try:
            with urlopen_with_ipv4_fallback(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            try:
                message = json.loads(exc.read().decode("utf-8")).get("error", str(exc))
            except Exception:
                message = str(exc)
            raise RuntimeError(message) from exc
        except (urllib.error.URLError, OSError) as exc:
            if attempt == 2:
                raise RuntimeError("server request failed after 3 attempts: " + str(exc)) from exc
            time.sleep(2 ** attempt)
    if not result.get("status"):
        raise RuntimeError(result.get("error") or "CertHub request failed")
    return result.get("data") or {}


def apply_client_update(update: dict, config: dict) -> None:
    token = str(update.get("command_token") or "")
    if not token:
        return
    if str(update.get("version")) == VERSION:
        request(config["api_endpoint"], "ack_update", {"command_token": token, "system": system_info()}, config)
        return
    url = str(update.get("url") or "")
    if not url.lower().startswith("https://"):
        raise ValueError("client update URL must use HTTPS")
    expected = str(update.get("sha256") or "").lower()
    target = PROGRAM_DATA / "certhub-agent.exe"
    staged = PROGRAM_DATA / "certhub-agent.update.exe"
    with urlopen_with_ipv4_fallback(url, timeout=120) as response:
        payload = response.read(64 * 1024 * 1024 + 1)
    if len(payload) > 64 * 1024 * 1024 or hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("client update checksum mismatch")
    staged.write_bytes(payload)
    updater = PROGRAM_DATA / "update-agent.ps1"
    update_log = PROGRAM_DATA / "update.log"
    quote = lambda value: str(value).replace("'", "''")
    script = """$ErrorActionPreference='Stop'
$log='%s'
try {
  Wait-Process -Id %d -ErrorAction SilentlyContinue
  $updated=$false
  for($i=0;$i -lt 30;$i++) {
    try {
      Copy-Item -LiteralPath '%s' -Destination '%s' -Force
      if((Get-FileHash -LiteralPath '%s' -Algorithm SHA256).Hash.ToLower() -eq '%s') {$updated=$true;break}
    } catch {}
    Start-Sleep -Seconds 2
  }
  if(-not $updated) {throw '无法替换或校验 Agent 程序'}
  Remove-Item -LiteralPath '%s' -Force -ErrorAction SilentlyContinue
  Add-Content -LiteralPath $log -Value ((Get-Date).ToString('s')+' update installed')
  Start-Process -FilePath '%s' -ArgumentList '--scheduled'
} catch {
  Add-Content -LiteralPath $log -Value ((Get-Date).ToString('s')+' '+$_.Exception.Message)
}
schtasks.exe /Delete /TN "CertHub Agent Updater" /F | Out-Null
""" % (quote(update_log), os.getpid(), quote(staged), quote(target), quote(target), expected, quote(staged), quote(target))
    updater.write_text(script, encoding="utf-8")
    task_command = 'powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{}"'.format(updater)
    subprocess.run(["schtasks", "/Create", "/F", "/SC", "ONSTART", "/TN", "CertHub Agent Updater", "/RU", "SYSTEM", "/RL", "HIGHEST", "/TR", task_command], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["schtasks", "/Run", "/TN", "CertHub Agent Updater"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    raise SystemExit(0)


def enroll(api: str, token: str) -> dict:
    if not api.lower().startswith("https://"):
        raise ValueError("API endpoint must use HTTPS")
    data = request(api.rstrip("/"), "enroll", {"token": token, "system": system_info()})
    default_root = Path.home() / "CertHub" / "certificates"
    config = {
        "api_endpoint": data["api_endpoint"], "client_id": data["client_id"],
        "auth_token": data["auth_token"], "user_home_download_path": str(default_root),
    }
    write_config(config)
    default_root.mkdir(parents=True, exist_ok=True)
    return config


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]", "_", value or "certificate")
    return value[:190] or "certificate"


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".new")
    temporary.write_text(data, encoding="ascii", newline="\n")
    os.replace(temporary, path)


def validate_pair(certificate: str, private_key: str) -> None:
    with tempfile.TemporaryDirectory(prefix="certhub-") as directory:
        cert_file = Path(directory) / "fullchain.pem"
        key_file = Path(directory) / "privkey.pem"
        cert_file.write_text(certificate, encoding="ascii")
        key_file.write_text(private_key, encoding="ascii")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_cert_chain(str(cert_file), str(key_file))
        decoded = ssl._ssl._test_decode_cert(str(cert_file))
        if ssl.cert_time_to_seconds(decoded["notAfter"]) <= time.time() + 86400:
            raise ValueError("certificate is expired or expires within 24 hours")


def restrict_acl(path: Path) -> None:
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", "SYSTEM:(OI)(CI)F", "Administrators:(OI)(CI)F"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )


def inherit_user_acl(path: Path) -> None:
    subprocess.run(
        ["icacls", str(path), "/inheritance:e", "/T", "/C"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )


def destination_for(name: str, server_config: dict, local_config: dict) -> Path:
    mode = server_config.get("deploy_mode") or "files-only"
    custom_destination = mode == "custom" and bool(server_config.get("download_path"))
    if custom_destination:
        destination_root = Path(server_config["download_path"])
        if not destination_root.is_absolute():
            raise ValueError("custom download path must be absolute")
    else:
        destination_root = Path(local_config["user_home_download_path"])
    return destination_root / safe_name(name)


def deploy_bundle(bundle: dict, server_config: dict, local_config: dict) -> str:
    validate_pair(bundle["fullchain_pem"], bundle["private_key_pem"])
    version_root = PROGRAM_DATA / "versions" / str(bundle["certificate_id"]) / bundle["version"]
    atomic_write(version_root / "fullchain.pem", bundle["fullchain_pem"])
    atomic_write(version_root / "privkey.pem", bundle["private_key_pem"])
    restrict_acl(version_root)

    custom_destination = (server_config.get("deploy_mode") or "files-only") == "custom" and bool(server_config.get("download_path"))
    destination = destination_for(bundle.get("name", ""), server_config, local_config)
    atomic_write(destination / "fullchain.pem", bundle["fullchain_pem"])
    atomic_write(destination / "privkey.pem", bundle["private_key_pem"])
    if custom_destination:
        restrict_acl(destination)
    else:
        inherit_user_acl(destination)
    (destination / ".certhub-managed").write_text(str(bundle["certificate_id"]), encoding="ascii")
    return str(destination)


def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_sync": 0}


def deployment_signature(server_config: dict) -> str:
    return json.dumps({"mode": server_config.get("deploy_mode") or "user-home", "path": server_config.get("download_path") or ""}, sort_keys=True, separators=(",", ":"))


def clear_managed_destination(value: str) -> None:
    path = Path(value).resolve()
    if path.parent == path or len(path.parts) < 3:
        return
    for name in ("fullchain.pem", "privkey.pem", ".certhub-managed"):
        try:
            (path / name).unlink()
        except FileNotFoundError:
            pass
    try:
        path.rmdir()
    except OSError:
        pass


def clear_managed_certificates(state: dict, include_versions: bool = True) -> None:
    for value in state.get("managed_destinations") or []:
        try:
            clear_managed_destination(value)
        except Exception:
            logging.exception("failed to remove managed certificate destination")
    if include_versions:
        shutil.rmtree(PROGRAM_DATA / "versions", ignore_errors=True)


def cron_values(field: str, minimum: int, maximum: int) -> set[int]:
    values = set()
    for part in field.split(","):
        base, _, step_text = part.partition("/")
        step = int(step_text or 1)
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start, end = map(int, base.split("-", 1))
        else:
            start = end = int(base)
        values.update(range(start, end + 1, step))
    return values


def cron_matches(expression: str, timestamp: int) -> bool:
    minute, hour, day, month, weekday = expression.split()
    current = datetime.datetime.fromtimestamp(timestamp)
    minute_match = current.minute in cron_values(minute, 0, 59)
    hour_match = current.hour in cron_values(hour, 0, 23)
    month_match = current.month in cron_values(month, 1, 12)
    day_match = current.day in cron_values(day, 1, 31)
    cron_weekday = (current.weekday() + 1) % 7
    weekdays = cron_values(weekday, 0, 7)
    weekday_match = cron_weekday in weekdays or (cron_weekday == 0 and 7 in weekdays)
    date_match = (day_match and weekday_match) if day == "*" or weekday == "*" else (day_match or weekday_match)
    return minute_match and hour_match and month_match and date_match


def cron_due(expression: str, previous: int, now: int) -> bool:
    start = max(previous // 60 + 1, now // 60 - 10080)
    return any(cron_matches(expression, minute * 60) for minute in range(start, now // 60 + 1))


def installed_command() -> tuple[Path, str]:
    target = PROGRAM_DATA / ("certhub-agent.exe" if getattr(sys, "frozen", False) else "windows_agent.py")
    if getattr(sys, "frozen", False):
        source = Path(sys.executable)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        command = f'"{target}" --scheduled'
    else:
        source = Path(__file__)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        command = f'"{sys.executable}" "{target}" --scheduled'
    return target, command


def configure_task(interval_seconds: int) -> None:
    _, command = installed_command()
    minutes = max(1, min(10080, math.ceil(interval_seconds / 60)))
    subprocess.run([
        "schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", str(minutes),
        "/TN", "CertHub Certificate Sync", "/RU", "SYSTEM", "/RL", "HIGHEST", "/TR", command,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sync_once(force: bool = False) -> None:
    config = read_config()
    pulled = request(config["api_endpoint"], "pull", {"system": system_info()}, config)
    server_config = pulled.get("config") or {}
    if server_config.get("update"):
        apply_client_update(server_config["update"], config)
    state = read_state()
    cleanup = server_config.get("cleanup") or {}
    if cleanup.get("command_token"):
        clear_managed_certificates(state, True)
        STATE_FILE.write_text(json.dumps({"last_sync": int(time.time()), "last_schedule_check": int(time.time()), "task_interval_seconds": POLL_SECONDS, "certificate_versions": {}, "managed_destinations": [], "managed_by_certificate": {}, "certificate_names": {}}), encoding="utf-8")
        request(config["api_endpoint"], "ack_cleanup", {"command_token": cleanup["command_token"], "system": system_info()}, config)
        return
    versions = {str(k): str(v) for k, v in (state.get("certificate_versions") or {}).items()}
    signature = deployment_signature(server_config)
    deployment_changed = state.get("deployment_signature") != signature
    if deployment_changed:
        clear_managed_certificates(state, False)
    assignments = pulled.get("certificates") or []
    authorized = {str(item["id"]): item for item in assignments}
    legacy_destinations = set() if deployment_changed else set(state.get("managed_destinations") or [])
    managed_by_certificate = {} if deployment_changed else {str(k): str(v) for k, v in (state.get("managed_by_certificate") or {}).items()}
    certificate_names = {} if deployment_changed else {str(k): str(v) for k, v in (state.get("certificate_names") or {}).items()}
    for certificate_id, assignment in authorized.items():
        certificate_names[certificate_id] = str(assignment.get("name") or certificate_id)
        expected = str(destination_for(certificate_names[certificate_id], server_config, config).resolve())
        if expected in legacy_destinations or Path(expected).is_dir():
            managed_by_certificate[certificate_id] = expected
    authorized_paths = {str(destination_for(str(item.get("name") or certificate_id), server_config, config).resolve()) for certificate_id, item in authorized.items()}
    for certificate_id in set(versions) - set(authorized):
        expected = str(destination_for(certificate_names[certificate_id], server_config, config).resolve()) if certificate_id in certificate_names else ""
        recorded = str(Path(managed_by_certificate[certificate_id]).resolve()) if certificate_id in managed_by_certificate else ""
        if expected and recorded == expected and recorded not in authorized_paths:
            clear_managed_destination(recorded)
        shutil.rmtree(PROGRAM_DATA / "versions" / certificate_id, ignore_errors=True)
        versions.pop(certificate_id, None)
        managed_by_certificate.pop(certificate_id, None)
        certificate_names.pop(certificate_id, None)
    now = int(time.time())
    schedule = server_config.get("sync_schedule") or "0 * * * *"
    command_token = server_config.get("force_sync_token")
    forced = force or bool(command_token) or deployment_changed
    certificate_due = forced or cron_due(schedule, int(state.get("last_schedule_check") or now - POLL_SECONDS), now)
    if certificate_due:
        for assignment in assignments:
            certificate_id = str(assignment["id"])
            if not forced and versions.get(certificate_id) == assignment.get("version"):
                continue
            bundle = request(config["api_endpoint"], "bundle", {"certificate_id": assignment["id"], "system": system_info()}, config)
            destination = deploy_bundle(bundle, server_config, config)
            managed_by_certificate[certificate_id] = destination
            certificate_names[certificate_id] = str(bundle.get("name") or certificate_id)
            versions[certificate_id] = bundle["version"]
        if command_token:
            request(config["api_endpoint"], "ack_sync", {"command_token": command_token, "system": system_info()}, config)
    PROGRAM_DATA.mkdir(parents=True, exist_ok=True)
    if state.get("task_interval_seconds") != POLL_SECONDS:
        configure_task(POLL_SECONDS)
    STATE_FILE.write_text(json.dumps({"last_sync": now if certificate_due else int(state.get("last_sync") or 0), "last_schedule_check": now, "task_interval_seconds": POLL_SECONDS, "sync_schedule": schedule, "config_version": server_config.get("config_updated_at"), "deployment_signature": signature, "certificate_versions": versions, "managed_destinations": sorted(set(managed_by_certificate.values())), "managed_by_certificate": managed_by_certificate, "certificate_names": certificate_names}), encoding="utf-8")


def daemon() -> None:
    while True:
        try:
            sync_once(False)
        except Exception:
            logging.exception("synchronization failed")
        time.sleep(POLL_SECONDS)


def enrollment_from_filename() -> tuple[str, str] | None:
    executable = Path(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])
    parts = executable.stem.split("..")
    if len(parts) != 3 or parts[0] != "certhub-setup":
        return None
    encoded, token = parts[1], parts[2]
    endpoint = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
    if not endpoint.startswith("https://") or not re.fullmatch(r"[A-Za-z0-9_-]{32,}", token):
        raise ValueError("invalid installer identity")
    return endpoint, token


def is_admin() -> bool:
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def elevate() -> None:
    executable = sys.executable
    parameters = subprocess.list2cmdline(sys.argv[1:])
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, parameters, None, 0)
    if result <= 32:
        raise ctypes.WinError()


def install(api: str, token: str) -> None:
    enroll(api, token)
    installed_command()
    sync_once(True)


def main() -> int:
    if os.name != "nt":
        raise RuntimeError("This agent only supports Windows")
    PROGRAM_DATA.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--enroll", nargs=2, metavar=("API_ENDPOINT", "ENROLLMENT_TOKEN"))
    parser.add_argument("--install", nargs=2, metavar=("API_ENDPOINT", "ENROLLMENT_TOKEN"))
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    args = parser.parse_args()
    implicit = enrollment_from_filename() if not (args.enroll or args.install or args.sync or args.scheduled or args.daemon) else None
    if (args.install or implicit) and not is_admin():
        elevate()
        return 0
    if args.install or implicit:
        install(*(args.install or implicit))
    elif args.enroll:
        enroll(args.enroll[0], args.enroll[1])
    if args.sync:
        sync_once(True)
    if args.scheduled:
        sync_once(False)
    if args.daemon:
        daemon()
    if not (args.enroll or args.install or args.sync or args.scheduled or args.daemon or implicit):
        parser.error("installer identity is missing")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logging.exception("fatal error")
        raise SystemExit(1)
