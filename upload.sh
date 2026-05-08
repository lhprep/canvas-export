#!/usr/bin/env bash
set -euo pipefail

DATETIME="$(TZ='America/New_York' date +%Y-%m-%dT%H:%M:%S)"
REMOTE="canvas-drive:Spring 2026/${DATETIME}"

rclone mkdir "${REMOTE}"
rclone copy . "${REMOTE}" \
    --exclude 'env/**' \
    --include '*.csv' \
    --include '*.json' \
    --include '*.zip' \
    --progress
