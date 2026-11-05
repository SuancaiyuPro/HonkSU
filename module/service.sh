#!/system/bin/sh
MODDIR=${0%/*}
"$MODDIR/scripts/honksuctl" boot >/dev/null 2>&1
