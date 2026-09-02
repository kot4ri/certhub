#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["versions"])' "$PROJECT_DIR/info.json")
RELEASE_DIR="$PROJECT_DIR/release"
OUTPUT="$RELEASE_DIR/certhub-$VERSION.zip"

if find "$PROJECT_DIR" -type f \( -name '*.db' -o -name '*.db-wal' -o -name '*.db-shm' -o -name '*.key' -o -name '*.token' \) | grep -q .; then
    echo '拒绝打包：源码目录包含运行数据库、凭据或密钥。' >&2
    exit 1
fi

mkdir -p "$RELEASE_DIR"
cd "$PROJECT_DIR/.."
zip -qr -FS "$OUTPUT" certhub \
    -x 'certhub/.git/*' 'certhub/__pycache__/*' 'certhub/**/__pycache__/*' 'certhub/release/*' 'certhub/CHANGELOG.md' 'certhub/*.db*' 'certhub/*.key' 'certhub/*.token'
sha256sum "$OUTPUT" > "$OUTPUT.sha256"
if [[ -n "${CERTHUB_SIGNING_KEY:-}" ]]; then
    [[ -f "$CERTHUB_SIGNING_KEY" ]] || { echo '发布签名私钥不存在。' >&2; exit 1; }
    openssl dgst -sha256 -sign "$CERTHUB_SIGNING_KEY" -out "$OUTPUT.sig" "$OUTPUT"
    openssl dgst -sha256 -verify "$PROJECT_DIR/assets/release-public-key.pem" -signature "$OUTPUT.sig" "$OUTPUT" >/dev/null
fi
echo "$OUTPUT"
