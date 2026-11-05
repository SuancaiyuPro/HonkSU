#!/system/bin/sh
[ "$KSU" = true ] || abort "HonkSU requires KernelSU."
[ "${KSU_HAS_HOT_INSTALL:-false}" = true ] || abort "Native hot installation is required. Update official KernelSU before installing this build."
[ "$(getprop ro.product.cpu.abi)" = arm64-v8a ] || abort "ARM64 devices only."
[ "$API" -ge 35 ] || abort "Android API 35 or newer is required."
[ -s "$MODPATH/bin/honk-core" ] || abort "Missing honk-core; install the built module ZIP."
(cd "$MODPATH/bin" && sha256sum -c SHA256SUMS) || abort "Core checksum verification failed."
ui_print "HonkSU 0.1.0-alpha.2"
ui_print "eBPF backend compiled; Android interception is not ready. Starting remains mock-only."
export MODULE_HOT_INSTALL_REQUEST=true
export MODULE_HOT_RUN_SCRIPT=hotinstall.sh
ui_print "Requesting native hot installation. A running test core will be replaced after activation."
set_perm_recursive "$MODPATH/scripts" 0 0 0755 0755
set_perm_recursive "$MODPATH/bin" 0 0 0755 0755
set_perm "$MODPATH/service.sh" 0 0 0755
set_perm "$MODPATH/uninstall.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
set_perm "$MODPATH/hotinstall.sh" 0 0 0755
