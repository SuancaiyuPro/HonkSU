#!/system/bin/sh
MODDIR=${0%/*}
"$MODDIR/scripts/honksuctl" stop >/dev/null 2>&1 || true
# Keep subscriptions and configuration for a later reinstall.
