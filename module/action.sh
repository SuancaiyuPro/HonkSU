#!/system/bin/sh
MODDIR=${0%/*}
"$MODDIR/scripts/honksuctl" status
echo "Open this module's WebUI to manage subscriptions and the core."
